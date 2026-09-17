import asyncio
import json
import websockets
import logging
from auth_logic import WS_REGISTER_TOKEN, decrypt_payload, encrypt_payload
import database

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def auth_handler(websocket):
    """
    Xử lý các kết nối WebSocket từ bản mod Android.
    Quy trình: 
    1. Nhận JSON register -> Kiểm tra token.
    2. Nhận JSON auth (chứa data đã mã hóa) -> Giải mã -> Check DB -> Trả về JSON mã hóa.
    """
    client_ip = websocket.remote_address[0]
    logging.info(f"Kết nối mới từ: {client_ip}")
    
    registered = False
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Bước 1: Xác thực Token đăng ký ban đầu
                if not registered:
                    if data.get("register") is True and data.get("token") == WS_REGISTER_TOKEN:
                        registered = True
                        logging.info(f"[{client_ip}] Đã đăng ký WebSocket thành công.")
                        await websocket.send(json.dumps({"success": True}))
                        continue
                    else:
                        logging.warning(f"[{client_ip}] Gửi sai token đăng ký.")
                        await websocket.send(json.dumps({"success": False, "error": "Sai Token đăng ký!"}))
                        await websocket.close()
                        return

                # Bước 2: Xử lý yêu cầu đăng nhập bằng Key
                if registered:
                    if data.get("token") == WS_REGISTER_TOKEN and "data" in data:
                        # Giải mã dữ liệu từ Client
                        encrypted_str = data["data"]
                        decrypted_json_str = decrypt_payload(encrypted_str)
                        
                        if not decrypted_json_str:
                            logging.error(f"[{client_ip}] Không thể giải mã dữ liệu.")
                            continue
                        
                        auth_info = json.loads(decrypted_json_str)
                        key = auth_info.get("license_key")
                        hwid = auth_info.get("hwid")
                        logging.info(f"[{client_ip}] Đang xác thực Key: {key} (HWID: {hwid})")

                        # Tra cứu trong Database
                        success, result = database.validate_key(key, hwid)
                        
                        if success:
                            # result là tuple (expiry_date, max_devices, active_devices)
                            expiry, max_dev, act_dev = result
                            response_body = {
                                "status": "success",
                                "data": {
                                    "expiry_date": expiry,
                                    "version": "1.0",
                                    "auth_token": "session_active_" + key[:4],
                                    "license_key": key,
                                    "max_devices": str(max_dev),
                                    "active_devices": str(act_dev)
                                }
                            }
                            logging.info(f"[{client_ip}] Xác thực THÀNH CÔNG cho Key: {key}")
                        else:
                            # result là lỗi
                            response_body = {
                                "status": "error",
                                "message": result
                            }
                            logging.warning(f"[{client_ip}] Xác thực THẤT BẠI: {result}")

                        # Mã hóa phản hồi trước khi gửi về máy khách
                        encrypted_resp = encrypt_payload(json.dumps(response_body))
                        await websocket.send(json.dumps({"data": encrypted_resp}))
                
            except json.JSONDecodeError:
                logging.error(f"[{client_ip}] Nhận dữ liệu không phải JSON.")
            except Exception as e:
                logging.error(f"[{client_ip}] Lỗi không xác định: {e}")

    except websockets.exceptions.ConnectionClosed:
        logging.info(f"[{client_ip}] Đã ngắt kết nối.")
    except Exception as e:
        logging.error(f"[{client_ip}] Lỗi kết nối: {e}")

async def process_request(*args):
    # args có thể là (path, headers) ở bản cũ hoặc (connection, request) ở bản mới
    if len(args) == 2:
        req = args[1]
        headers = req.headers if hasattr(req, "headers") else req
        
        if "Upgrade" not in headers.get("Connection", ""):
            # Trả về Response cho bản websockets mới (14.0+)
            try:
                from websockets.http11 import Response
                try:
                    from websockets.datastructures import Headers
                    headers_obj = Headers()
                except ImportError:
                    headers_obj = [] # Fallback
                return Response(status_code=200, reason_phrase="OK", headers=headers_obj, body=b"Server is running! Uptime Robot can see this.")
            except ImportError:
                # Trả về tuple cho bản cũ
                import http
                return (http.HTTPStatus.OK, [], b"Server is running! Uptime Robot can see this.")
    return None

async def run_ws_server(host="0.0.0.0", port=None):
    if port is None:
        import os
        port = int(os.environ.get("PORT", 8080))
    logging.info(f"Đang khởi tạo WebSocket Server tại {host}:{port}...")
    async with websockets.serve(auth_handler, host, port, process_request=process_request):
        await asyncio.Future()  # Chạy mãi mãi

if __name__ == "__main__":
    asyncio.run(run_ws_server())
