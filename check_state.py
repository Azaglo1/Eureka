import sqlite3
conn = sqlite3.connect('school.db')
cur = conn.cursor()
cur.execute('SELECT id, name, active FROM schools')
print('Schools:', cur.fetchall())
conn.close()
