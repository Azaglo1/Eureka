import sys
sys.path.insert(0, r"C:\Users\LENOVO\OneDrive\Desktop\school")

from db_utils import connect_db
from dotenv import load_dotenv
import os

BASE_DIR = r"C:\Users\LENOVO\OneDrive\Desktop\school"
os.chdir(BASE_DIR)
load_dotenv()

db = connect_db()
cur = db.cursor()

# Reactivate SYSADMIN001 user and upgrade to superadmin
cur.execute("UPDATE users SET active = 1, role = 'superadmin' WHERE id = 1")
print(f"Updated {cur.rowcount} users")

cur.execute("SELECT id, name, login_code, role, active, school_id FROM users WHERE id = 1")
row = cur.fetchone()
print(f"User 1: id={row['id']}, name={row['name']}, login_code={row['login_code']}, role={row['role']}, active={row['active']}, school_id={row['school_id']}")

# Also reactivate all users in deactivated schools
cur.execute("UPDATE users SET active = 1 WHERE school_id IN (SELECT id FROM schools WHERE active = 1) AND active = 0")
print(f"Reactivated {cur.rowcount} users in active schools")

db.commit()
cur.close()
db.close()
print("Done! You can now log in with:")
print("  Superadmin portal (port 8080): SYSADMIN001")
print("  School portal (port 5000): any admin user in your school")
