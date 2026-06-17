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
    ("passing_marks", "INTEGER DEFAULT 50"),
    ("academic_term", "TEXT DEFAULT 'Term 1'"),
    ("smtp_server", "TEXT DEFAULT 'smtp.gmail.com'"),
    ("smtp_port", "INTEGER DEFAULT 587"),
    ("smtp_email", "TEXT"),
    ("smtp_password", "TEXT"),
    ("sender_name", "TEXT DEFAULT 'School Administration'"),
    ("twilio_account_sid", "TEXT"),
    ("twilio_auth_token", "TEXT"),
    ("twilio_from_number", "TEXT"),
    ("twilio_messaging_service_sid", "TEXT"),
    ("whatsapp_access_token", "TEXT"),
    ("whatsapp_phone_number_id", "TEXT"),
    ("school_email", "TEXT"),
    ("school_phone", "TEXT"),
    ("school_address", "TEXT"),
    ("school_website", "TEXT"),
]

conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'schools'")
if not cur.fetchone():
    print("Table 'schools' not found. Make sure your database was initialized.")
    sys.exit(1)

for col_name, col_def in COLUMNS:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'schools' AND column_name = %s",
        (col_name,),
    )
    if cur.fetchone():
        print(f"Column '{col_name}' already exists.")
    else:
        cur.execute(sql.SQL("ALTER TABLE schools ADD COLUMN {} {}").format(
            sql.Identifier(col_name), sql.SQL(col_def)
        ))
        print(f"Added column '{col_name}'.")

cur.close()
conn.close()
print("Done.")
