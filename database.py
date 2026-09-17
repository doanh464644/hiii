import os
import sqlite3
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES = DATABASE_URL is not None

if IS_POSTGRES:
    import psycopg2
    import psycopg2.errors

def get_db_connection():
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        db_path = os.path.join(os.path.dirname(__file__), "keys.db")
        return sqlite3.connect(db_path)

def format_query(query):
    if IS_POSTGRES:
        # Postgres sử dụng %s cho tham số thay vì ?
        query = query.replace("?", "%s")
        # Thay thế các từ khóa SQLite sang Postgres
        query = query.replace("AUTOINCREMENT", "SERIAL")
        query = query.replace("INTEGER PRIMARY KEY SERIAL", "SERIAL PRIMARY KEY")
    return query

def is_duplicate_error(e):
    if IS_POSTGRES:
        return isinstance(e, psycopg2.errors.UniqueViolation)
    else:
        return isinstance(e, sqlite3.IntegrityError)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Bảng keys chính
    c.execute(format_query('''CREATE TABLE IF NOT EXISTS keys
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key_str TEXT UNIQUE,
                  expiry_date TEXT,
                  total_days INTEGER,
                  max_devices INTEGER DEFAULT 1,
                  created_at TEXT)'''))
                  
    # Bảng devices: lưu từng HWID đã đăng ký cho mỗi key
    c.execute(format_query('''CREATE TABLE IF NOT EXISTS devices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key_str TEXT,
                  hwid TEXT,
                  registered_at TEXT,
                  UNIQUE(key_str, hwid))'''))
                  
    conn.commit()
    c.close()
    conn.close()

def add_key(key_str, days, max_devices=1):
    conn = get_db_connection()
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        q = format_query("INSERT INTO keys (key_str, expiry_date, total_days, max_devices, created_at) VALUES (?, ?, ?, ?, ?)")
        c.execute(q, (key_str, expiry, days, max_devices, created))
        conn.commit()
        return True
    except Exception as e:
        if is_duplicate_error(e):
            return False
        raise e
    finally:
        c.close()
        conn.close()

def validate_key(key_str, hwid):
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute(format_query("SELECT expiry_date, max_devices FROM keys WHERE key_str = ?"), (key_str,))
    row = c.fetchone()
    
    if not row:
        c.close()
        conn.close()
        return False, "Key không tồn tại trong hệ thống"

    expiry_str, max_devices = row
    
    # Kiểm tra hạn dùng
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        c.close()
        conn.close()
        return False, f"Key đã hết hạn vào lúc {expiry_str}"

    # Kiểm tra xem HWID này đã đăng ký chưa
    c.execute(format_query("SELECT hwid FROM devices WHERE key_str = ? AND hwid = ?"), (key_str, hwid))
    existing = c.fetchone()

    c.execute(format_query("SELECT COUNT(*) FROM devices WHERE key_str = ?"), (key_str,))
    current_count = c.fetchone()[0]

    if existing:
        c.close()
        conn.close()
        return True, (expiry_str, max_devices, current_count)

    if current_count >= max_devices:
        c.close()
        conn.close()
        return False, f"Key đã đạt giới hạn {max_devices} thiết bị. Liên hệ Admin để Reset HWID."

    # Đăng ký HWID mới
    registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(format_query("INSERT INTO devices (key_str, hwid, registered_at) VALUES (?, ?, ?)"),
              (key_str, hwid, registered_at))
    conn.commit()
    c.close()
    conn.close()
    
    return True, (expiry_str, max_devices, current_count + 1)

def get_key_info(key_str):
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute(format_query("SELECT key_str, expiry_date, total_days, max_devices, created_at FROM keys WHERE key_str = ?"), (key_str,))
    key_row = c.fetchone()
    
    if not key_row:
        c.close()
        conn.close()
        return None

    c.execute(format_query("SELECT hwid, registered_at FROM devices WHERE key_str = ?"), (key_str,))
    devices = c.fetchall()
    
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(format_query("DELETE FROM devices WHERE key_str = ?"), (key_str,))
    affected = c.rowcount
    conn.commit()
    c.close()
    conn.close()
    return affected >= 0

def list_keys():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(format_query("""
        SELECT k.key_str, COUNT(d.hwid), k.max_devices, k.expiry_date
        FROM keys k
        LEFT JOIN devices d ON k.key_str = d.key_str
        GROUP BY k.key_str, k.max_devices, k.expiry_date, k.id
        ORDER BY k.id DESC LIMIT 20
    """))
    rows = c.fetchall()
    c.close()
    conn.close()
    return rows

def delete_key(key_str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(format_query("DELETE FROM devices WHERE key_str = ?"), (key_str,))
    c.execute(format_query("DELETE FROM keys WHERE key_str = ?"), (key_str,))
    affected = c.rowcount
    conn.commit()
    c.close()
    conn.close()
    return affected > 0

init_db()
