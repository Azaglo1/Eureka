import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2 is not installed. Please install it first.")
    sys.exit(1)

def load_env_file():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
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

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "school")

if not POSTGRES_DB:
    print("POSTGRES_DB is not configured. Set POSTGRES_DB in your environment or .env file.")
    sys.exit(1)

dsn = f"dbname={POSTGRES_DB} user={POSTGRES_USER} host={POSTGRES_HOST} port={POSTGRES_PORT}"
if POSTGRES_PASSWORD:
    dsn += f" password={POSTGRES_PASSWORD}"

try:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Add grade and section columns to assignments table
    try:
        cur.execute("ALTER TABLE assignments ADD COLUMN grade TEXT")
        print("Added column 'grade' to assignments table")
    except Exception as e:
        print(f"grade column already exists or error: {e}")

    try:
        cur.execute("ALTER TABLE assignments ADD COLUMN section TEXT")
        print("Added column 'section' to assignments table")
    except Exception as e:
        print(f"section column already exists or error: {e}")
    
    cur.close()
    conn.close()
    print("Done!")
except Exception as exc:
    print("Failed to connect to database:", exc)
    sys.exit(1)