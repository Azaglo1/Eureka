import os
import sys
import psycopg2
from psycopg2 import sql

try:
    import dotenv
    dotenv.load_dotenv()
except Exception:
    pass

HOST = os.environ.get("POSTGRES_HOST", "localhost")
PORT = os.environ.get("POSTGRES_PORT", "5432")
USER = os.environ.get("POSTGRES_USER", "postgres")
PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
DBNAME = os.environ.get("POSTGRES_DB", "school")

if not DBNAME:
    print("Set POSTGRES_DB in your environment or .env file.")
    sys.exit(1)

dsn = f"dbname={DBNAME} user={USER} host={HOST} port={PORT}"
if PASSWORD:
    dsn += f" password={PASSWORD}"

COLUMNS = [
    ("attachment_path", "TEXT"),
    ("attachment_name", "TEXT"),
]

conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'teaching_plans'")
if not cur.fetchone():
    print("Table 'teaching_plans' not found.")
    sys.exit(1)

for col_name, col_def in COLUMNS:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = %s",
        (col_name,),
    )
    if cur.fetchone():
        print(f"Column '{col_name}' already exists.")
    else:
        cur.execute(sql.SQL("ALTER TABLE teaching_plans ADD COLUMN {} {}").format(
            sql.Identifier(col_name), sql.SQL(col_def)
        ))
        print(f"Added column '{col_name}' to teaching_plans.")

cur.close()
conn.close()
print("Done.")
