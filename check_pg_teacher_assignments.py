#!/usr/bin/env python3
"""
Check the PostgreSQL teacher_assignments table schema.
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

def check_teacher_assignments_table():
    conn = psycopg2.connect(get_database_url())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'teacher_assignments'
            ) AS table_exists;
        """)
        row = cur.fetchone()
        table_exists = row['table_exists']
        print(f"Teacher assignments table exists: {table_exists}")

        if table_exists:
            # Get columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'teacher_assignments'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print("Columns in teacher_assignments table:")
            for col in columns:
                print(f"  {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']}, default: {col['column_default']})")
        else:
            print("Table does not exist.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_teacher_assignments_table()