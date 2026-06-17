#!/usr/bin/env python3
"""
Fix the PostgreSQL messages table by adding missing subject column.
"""
import os
import sys
from urllib.parse import quote_plus
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env_file()

def get_database_url():
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if database_url:
        return database_url

    host = os.environ.get("POSTGRES_HOST")
    if not host:
        raise RuntimeError(
            "PostgreSQL connection settings are not configured. "
            "Set DATABASE_URL or POSTGRES_HOST/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD."
        )

    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "school")
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{dbname}"

def fix_messages_table():
    conn = psycopg2.connect(get_database_url())
    cur = conn.cursor()
    try:
        # Check if subject column exists
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'messages' AND column_name = 'subject';
        """)
        if cur.fetchone():
            print("Subject column already exists.")
            return

        # Check row count
        cur.execute("SELECT COUNT(*) FROM messages;")
        row_count = cur.fetchone()[0]
        print(f"Messages table has {row_count} rows.")

        # Add subject column with default empty string, then set NOT NULL
        # We'll add as nullable first, update existing rows to empty string, then alter to NOT NULL.
        print("Adding subject column as nullable...")
        cur.execute("ALTER TABLE messages ADD COLUMN subject TEXT;")
        print("Setting existing rows to empty string...")
        cur.execute("UPDATE messages SET subject = '' WHERE subject IS NULL;")
        print("Making subject column NOT NULL...")
        cur.execute("ALTER TABLE messages ALTER COLUMN subject SET NOT NULL;")
        conn.commit()
        print("[OK] Successfully added subject column to messages table.")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_messages_table()