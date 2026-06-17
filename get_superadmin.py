import sqlite3
conn = sqlite3.connect('school.db')
c = conn.cursor()
c.execute("SELECT login_code, name FROM users WHERE role='superadmin'")
rows = c.fetchall()
print('Superadmin users:')
for row in rows:
    print(f'Name: {row[1]}, Login Code: {row[0]}')
conn.close()