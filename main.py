import subprocess
import sys
import time

def start_services():
    print("Khởi động Telegram Bot...")
    bot_process = subprocess.Popen([sys.executable, "telegram_bot.py"])
    
    print("Khởi động WebSocket Server...")
    ws_process = subprocess.Popen([sys.executable, "websocket_server.py"])
    
    try:
        while True:
            # Check if any process has exited unexpectedly
            if bot_process.poll() is not None:
                print("Telegram Bot đã dừng đột ngột.")
                break
            if ws_process.poll() is not None:
                print("WebSocket Server đã dừng đột ngột.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Đang tắt các dịch vụ...")
    finally:
        bot_process.terminate()
        ws_process.terminate()
        bot_process.wait()
        ws_process.wait()
        print("Tất cả dịch vụ đã dừng.")

if __name__ == "__main__":
    start_services()
