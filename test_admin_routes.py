"""Test admin routes to find errors."""
import sys
import sqlite3
from app import app

conn = sqlite3.connect('school.db')
cur = conn.cursor()

# Get an admin user
cur.execute('SELECT id, login_code, school_id FROM users WHERE role = ? LIMIT 1', ('admin',))
row = cur.fetchone()
if not row:
    print("No admin found!")
    sys.exit(1)
aid, code, sid = row
cur.execute('SELECT school_code FROM schools WHERE id = ?', (sid,))
sc = cur.fetchone()
school_code = sc[0] if sc else ''
print(f"Admin: id={aid}, code={code}, school_code={school_code}")
conn.close()

admin_routes = [
    ('GET', '/admin_panel'),
    ('GET', '/admin/create_user'),
    ('GET', '/students'),
    ('GET', '/announcements'),
    ('GET', '/events'),
    ('GET', '/library'),
    ('GET', '/messages'),
    ('GET', '/timetable'),
    ('GET', '/teaching_plans'),
    ('GET', '/attendance'),
    ('GET', '/assignments'),
    ('GET', '/grades'),
    ('GET', '/finance'),
]

with app.test_client() as c:
    resp = c.post('/', data={'school_code': school_code, 'login_code': code}, follow_redirects=True)
    print(f"\nLogin: {resp.status_code}")

    for method, route in admin_routes:
        try:
            if method == 'GET':
                resp = c.get(route, follow_redirects=False)
            else:
                resp = c.post(route, follow_redirects=False)
            if resp.status_code >= 400:
                print(f"  ERROR {method} {route}: {resp.status_code}")
            else:
                print(f"  OK {method} {route}: {resp.status_code}")
        except Exception as e:
            print(f"  EXCEPTION {method} {route}: {e}")
