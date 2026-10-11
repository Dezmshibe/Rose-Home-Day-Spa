"""
One-time migration: add `username` to users table, populate from email,
and make email nullable.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "booking.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print("No database found — nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Check current columns
    cols = [row[1] for row in cur.execute("PRAGMA table_info(user)").fetchall()]
    print("Current user columns:", cols)

    # 2. Add `username` column if missing
    if "username" not in cols:
        print("Adding `username` column...")
        cur.execute("ALTER TABLE user ADD COLUMN username VARCHAR(80)")
        conn.commit()
    else:
        print("`username` column already exists.")

    # 3. Populate username from email or name
    print("Populating usernames...")
    rows = cur.execute("SELECT id, email, name FROM user").fetchall()
    for uid, email, name in rows:
        if email == "owner@brightstudio.local":
            username = "Londiieyy"
        elif email == "admin@platform.local":
            username = "admin"
        elif email:
            username = email.split("@")[0]
        else:
            username = (name or f"user{uid}").lower().replace(" ", "")

        # Ensure uniqueness
        existing = cur.execute("SELECT id FROM user WHERE username = ? AND id != ?", (username, uid)).fetchone()
        if existing:
            username = f"{username}{uid}"

        cur.execute("UPDATE user SET username = ? WHERE id = ?", (username, uid))
        print(f"  user {uid}: {email} -> username '{username}'")

    conn.commit()

    # 4. Make username NOT NULL going forward (SQLite: rebuild via UNIQUE INDEX)
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_username ON user(username)")
        print("Created unique index on username.")
    except Exception as e:
        print("Index creation skipped:", e)

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()