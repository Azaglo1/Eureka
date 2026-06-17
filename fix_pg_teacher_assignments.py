#!/usr/bin/env python3
"""
Check and create the teacher_assignments table in PostgreSQL if it doesn't exist.
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

def check_and_create_teacher_assignments_table():
    conn = psycopg2.connect(get_database_url())
    cur = conn.cursor()
    try:
        # Check if teacher_assignments table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'teacher_assignments'
            );
        """)
        table_exists = cur.fetchone()[0]
        if table_exists:
            print("Teacher assignments table already exists.")
            return

        # Create the table
        print("Creating teacher_assignments table...")
        cur.execute("""
            CREATE TABLE teacher_assignments (
                teacher_id INTEGER NOT NULL,
                school_id INTEGER NOT NULL,
                grade TEXT NOT NULL,
                section TEXT NOT NULL,
                subject TEXT NOT NULL,
                responsibility TEXT NOT NULL DEFAULT 'Class teacher',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(teacher_id) REFERENCES users(id),
                FOREIGN KEY(school_id) REFERENCES schools(id)
            );
        """)
        conn.commit()
        print("[OK] Successfully created teacher_assignments table.")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_and_create_teacher_assignments_table()