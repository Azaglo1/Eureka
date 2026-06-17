import psycopg2
import os

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

dsn = f"dbname={POSTGRES_DB} user={POSTGRES_USER} host={POSTGRES_HOST} port={POSTGRES_PORT}"
if POSTGRES_PASSWORD:
    dsn += f" password={POSTGRES_PASSWORD}"

conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE student_reports ADD COLUMN teacher_remarks TEXT")
    print("Added column 'teacher_remarks' to student_reports")
except Exception as e:
    print(f"teacher_remarks column already exists or error: {e}")

cur.close()
conn.close()
print("Done")
