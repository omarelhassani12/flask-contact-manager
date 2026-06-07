import bcrypt
from database.db import get_connection


def verify_login(username: str, password: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password_hash FROM admins WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    conn.close()

    if result is None:
        return False

    return bcrypt.checkpw(password.encode(), result["password_hash"].encode())
