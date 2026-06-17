#!/usr/bin/env python3
"""
Add is_primary column to teacher_assignments table if it doesn't exist.
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

def add_is_primary_column_if_missing():
    conn = psycopg2.connect(get_database_url())
    cur = conn.cursor()
    try:
        # Check if is_primary column exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'teacher_assignments' AND column_name = 'is_primary'
            ) AS column_exists;
        """)
        column_exists = cur.fetchone()[0]
        if column_exists:
            print("is_primary column already exists in teacher_assignments table.")
            return

        # Add the is_primary column with default 0
        print("Adding is_primary column to teacher_assignments table...")
        cur.execute("""
            ALTER TABLE teacher_assignments 
            ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0;
        """)
        conn.commit()
        print("[OK] Successfully added is_primary column to teacher_assignments table.")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_is_primary_column_if_missing()