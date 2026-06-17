import os
import sys

try:
    import psycopg2
    from psycopg2 import sql
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

# Connect to the default maintenance database.
maintenance_db = os.environ.get("POSTGRES_MAINTENANCE_DB", "postgres")

dsn = (
    f"dbname={maintenance_db} user={POSTGRES_USER} host={POSTGRES_HOST} port={POSTGRES_PORT}"
)
if POSTGRES_PASSWORD:
    dsn += f" password={POSTGRES_PASSWORD}"

try:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DB,))
    exists = cur.fetchone() is not None
    if exists:
        print(f"Database '{POSTGRES_DB}' already exists.")
    else:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(POSTGRES_DB)))
        print(f"Created database '{POSTGRES_DB}'.")
    cur.close()
    conn.close()
except Exception as exc:
    print("Failed to create or verify the database:", exc)
    sys.exit(1)
