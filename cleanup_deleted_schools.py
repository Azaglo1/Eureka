import sqlite3

conn = sqlite3.connect('school.db')
cur = conn.cursor()

# Find all tables with school_id column
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

deleted_school_ids = [1, 2, 3]  # all schools are deleted in this DB

for t in tables:
    cur.execute(f'PRAGMA table_info({t})')
    cols = [c[1] for c in cur.fetchall()]
    if 'school_id' in cols:
        placeholders = ','.join('?' * len(deleted_school_ids))
        cur.execute(f'SELECT COUNT(*) FROM {t} WHERE school_id IN ({placeholders})', deleted_school_ids)
        orphaned = cur.fetchone()[0]
        if orphaned > 0:
            cur.execute(f'DELETE FROM {t} WHERE school_id IN ({placeholders})', deleted_school_ids)
            print(f'Deleted {orphaned} rows from {t}')

conn.commit()

# Verify
print('\n=== After cleanup ===')
cur.execute('SELECT COUNT(*) FROM students')
print(f'Students: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM grades')
print(f'Grades: {cur.fetchone()[0]}')
cur.execute('SELECT id, name, active FROM schools')
print('Schools:', cur.fetchall())

conn.close()
