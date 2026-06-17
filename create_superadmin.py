import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('school.db')
c = conn.cursor()

# Check if superadmin already exists
c.execute("SELECT id FROM users WHERE role = 'superadmin'")
existing = c.fetchone()
if existing:
    print("Superadmin already exists with id:", existing[0])
else:
    # Create a superadmin user
    login_code = 'superadmin123'  # You can change this
    name = 'Super Admin'
    role = 'superadmin'
    # Password hash is not used for login, but we set a dummy one
    password_hash = generate_password_hash('temporary123')  # Or any password
    school_id = None  # Superadmin doesn't belong to a school
    active = 1
    privileges = ''  # Not used

    c.execute("""
        INSERT INTO users (name, email, role, school_id, login_code, password_hash, privileges, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, None, role, school_id, login_code, password_hash, privileges, active))
    conn.commit()
    print("Superadmin created with login_code:", login_code)
    print("Please remember this login_code for superadmin login.")

conn.close()