import sqlite3
import bcrypt
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contacts.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT DEFAULT '',
            address TEXT DEFAULT '',
            fonction TEXT DEFAULT '',
            company TEXT DEFAULT ''
        )
    """)

    # Migrate: add new columns if they don't exist yet
    for col, default in [("category", "''"), ("address", "''"), ("fonction", "''"), ("company", "''")]:
        try:
            cursor.execute(f"ALTER TABLE contacts ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass  # column already exists

    # Migrate: enforce unique email and phone at DB level
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email ON contacts (LOWER(email))")
    except Exception:
        pass
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_phone ON contacts (phone)")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            title TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            reminder_email INTEGER DEFAULT 0,
            reminder_sms INTEGER DEFAULT 0,
            google_event_id TEXT DEFAULT '',
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
            UNIQUE(date, time_slot)
        )
    """)

    # Migrate appointments: add reminder and google columns if not exist
    for col, default in [
        ("reminder_email", "0"),
        ("reminder_sms", "0"),
        ("google_event_id", "''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE appointments ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass

    # Labels / groups table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#6366f1'
        )
    """)

    # Contact <-> Label junction
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_labels (
            contact_id INTEGER NOT NULL,
            label_id INTEGER NOT NULL,
            PRIMARY KEY (contact_id, label_id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
            FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
        )
    """)

    # Migrate contacts: add labels column (denormalized for quick display)
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN labels TEXT DEFAULT ''")
    except Exception:
        pass

    cursor.execute("SELECT COUNT(*) FROM admins")
    admin_count = cursor.fetchone()[0]

    if admin_count == 0:
        password_hash = bcrypt.hashpw(
            "admin123".encode(),
            bcrypt.gensalt()
        ).decode()
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", password_hash)
        )

    conn.commit()
    conn.close()
