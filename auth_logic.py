import base64

# Key mã hóa được lấy chính xác từ keylogin.h
XOR_KEY = "JiM21rNU12eERlNmpqa3FuQks"
WS_REGISTER_TOKEN = "KJGMDKFJDHG34KD"

def xor_cipher(data: str, key: str = XOR_KEY) -> str:
    """Áp dụng thuật toán XOR lặp lại giống như xor_encrypt trong C++"""
    return "".join(chr(ord(data[i]) ^ ord(key[i % len(key)])) for i in range(len(data)))

def encrypt_payload(data: str) -> str:
    """Dữ liệu -> XOR -> Base64"""
    xored = xor_cipher(data)
    # Dùng latin-1 để bảo toàn bytes khi chuyển thành string trong Python
    return base64.b64encode(xored.encode('latin-1')).decode('utf-8')

def decrypt_payload(data: str) -> str:
    """Base64 -> XOR -> Dữ liệu"""
    try:
        decoded = base64.b64decode(data).decode('latin-1')
        return xor_cipher(decoded)
    except Exception as e:
        print(f"Lỗi giải mã: {e}")
        return ""
