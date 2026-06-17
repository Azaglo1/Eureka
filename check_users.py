import sqlite3
conn = sqlite3.connect('school.db')
c = conn.cursor()
c.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
rows = c.fetchall()
print('Role counts:')
for r in rows:
    print(r)
c.execute("SELECT login_code, name, role, active FROM users")
rows = c.fetchall()
print('All users:')
for r in rows:
    print(r)
conn.close()