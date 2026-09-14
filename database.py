import sqlite3
from datetime import datetime, timedelta
import os

# Đường dẫn DB nằm cùng thư mục với script
DB_PATH = os.path.join(os.path.dirname(__file__), "keys.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Bảng keys chính
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key_str TEXT UNIQUE,
                  expiry_date TEXT,
                  total_days INTEGER,
                  max_devices INTEGER DEFAULT 1,
                  created_at TEXT)''')
    # Bảng devices: lưu từng HWID đã đăng ký cho mỗi key
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key_str TEXT,
                  hwid TEXT,
                  registered_at TEXT,
                  UNIQUE(key_str, hwid))''')
    conn.commit()
    conn.close()

def add_key(key_str, days, max_devices=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        c.execute("INSERT INTO keys (key_str, expiry_date, total_days, max_devices, created_at) VALUES (?, ?, ?, ?, ?)",
                  (key_str, expiry, days, max_devices, created))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def validate_key(key_str, hwid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT expiry_date, max_devices FROM keys WHERE key_str = ?", (key_str,))
    row = c.fetchone()

    if not row:
        conn.close()
        return False, "Key không tồn tại trong hệ thống"

    expiry_str, max_devices = row

    # Kiểm tra hạn dùng
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        conn.close()
        return False, f"Key đã hết hạn vào lúc {expiry_str}"

    # Kiểm tra xem HWID này đã đăng ký chưa
    c.execute("SELECT hwid FROM devices WHERE key_str = ? AND hwid = ?", (key_str, hwid))
    existing = c.fetchone()

    c.execute("SELECT COUNT(*) FROM devices WHERE key_str = ?", (key_str,))
    current_count = c.fetchone()[0]

    if existing:
        # HWID đã đăng ký -> cho vào luôn
        conn.close()
        return True, (expiry_str, max_devices, current_count)

    if current_count >= max_devices:
        conn.close()
        return False, f"Key đã đạt giới hạn {max_devices} thiết bị. Liên hệ Admin để Reset HWID."

    # Đăng ký HWID mới
    registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO devices (key_str, hwid, registered_at) VALUES (?, ?, ?)",
              (key_str, hwid, registered_at))
    conn.commit()
    conn.close()
    return True, (expiry_str, max_devices, current_count + 1)

def get_key_info(key_str):
    """Lấy thông tin chi tiết của một key"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key_str, expiry_date, total_days, max_devices, created_at FROM keys WHERE key_str = ?", (key_str,))
    key_row = c.fetchone()
    if not key_row:
        conn.close()
        return None

    c.execute("SELECT hwid, registered_at FROM devices WHERE key_str = ?", (key_str,))
    devices = c.fetchall()
    conn.close()
    return {
        "key": key_row[0],
        "expiry": key_row[1],
        "days": key_row[2],
        "max_devices": key_row[3],
        "created_at": key_row[4],
        "devices": devices
    }

def reset_hwid(key_str):
    """Xóa tất cả HWID đã đăng ký, cho phép đăng ký lại"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM devices WHERE key_str = ?", (key_str,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected >= 0  # Trả về True dù không có device nào cũng ok

def list_keys():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT k.key_str, COUNT(d.hwid), k.max_devices, k.expiry_date
        FROM keys k
        LEFT JOIN devices d ON k.key_str = d.key_str
        GROUP BY k.key_str
        ORDER BY k.id DESC LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()
    return rows  # (key_str, active_devices, max_devices, expiry_date)

def delete_key(key_str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Xóa cả devices liên quan trước
    c.execute("DELETE FROM devices WHERE key_str = ?", (key_str,))
    c.execute("DELETE FROM keys WHERE key_str = ?", (key_str,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# Khởi tạo DB khi load module
init_db()
