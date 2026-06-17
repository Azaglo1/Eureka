"""
Emergency fix: Reactivate superadmin user and/or deactivated schools.
Run this script if you got locked out of superadmin or school portal.
"""
import sys
sys.path.insert(0, r"C:\Users\LENOVO\OneDrive\Desktop\school")

from db_utils import connect_db, get_database_url
from dotenv import load_dotenv
import os

BASE_DIR = r"C:\Users\LENOVO\OneDrive\Desktop\school"
os.chdir(BASE_DIR)
load_dotenv()

db = connect_db()
cur = db.cursor()

# 1. Show current state
print("=== Current Schools ===")
cur.execute("SELECT id, name, school_code, active FROM schools ORDER BY id")
for row in cur.fetchall():
    print(f"  id={row['id']}, name={row['name']}, code={row['school_code']}, active={row['active']}")

print("\n=== Current Superadmins ===")
cur.execute("SELECT id, name, login_code, active, school_id FROM users WHERE role = 'superadmin' ORDER BY id")
for row in cur.fetchall():
    print(f"  id={row['id']}, name={row['name']}, login_code={row['login_code']}, active={row['active']}, school_id={row['school_id']}")

print("\n=== Current Admins (non-superadmin) ===")
cur.execute("SELECT id, name, login_code, active, school_id FROM users WHERE role = 'admin' ORDER BY id")
for row in cur.fetchall():
    print(f"  id={row['id']}, name={row['name']}, login_code={row['login_code']}, active={row['active']}, school_id={row['school_id']}")

# 2. Reactivate all schools
print("\n=== Reactivating all schools ===")
cur.execute("UPDATE schools SET active = 1 WHERE active = 0")
print(f"  Reactivated {cur.rowcount} schools")

# 3. Reactivate superadmin accounts
print("\n=== Reactivating superadmin users ===")
cur.execute("UPDATE users SET active = 1 WHERE role = 'superadmin' AND active = 0")
print(f"  Reactivated {cur.rowcount} superadmin users")

# 4. Ensure superusers have no school_id (superadmin should be global)
cur.execute("UPDATE users SET school_id = NULL WHERE role = 'superadmin' AND school_id IS NOT NULL")
print(f"  Cleared school_id from {cur.rowcount} superadmin users")

db.commit()
cur.close()
db.close()

print("\nDone! All schools and superadmin users reactivated.")
print("You can now log in to superadmin portal with SYSADMIN001")
print("and to school portal with the previously locked accounts.")
