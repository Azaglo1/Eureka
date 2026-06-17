"""Test all major routes to find errors."""
import sys
import sqlite3
from app import app

conn = sqlite3.connect('school.db')
cur = conn.cursor()

# Get a teacher
cur.execute('SELECT id, login_code, school_id FROM users WHERE role = ? LIMIT 1', ('teacher',))
row = cur.fetchone()
if not row:
    print("No teacher found!")
    sys.exit(1)
tid, code, sid = row
cur.execute('SELECT school_code FROM schools WHERE id = ?', (sid,))
sc = cur.fetchone()
school_code = sc[0] if sc else ''
print(f"Teacher: id={tid}, code={code}, school_code={school_code}")
conn.close()

routes_to_test = [
    ('GET', '/'),
    ('GET', '/dashboard'),
    ('GET', '/attendance'),
    ('GET', '/assignments'),
    ('GET', '/grades'),
    ('GET', '/students'),
    ('GET', '/announcements'),
    ('GET', '/events'),
    ('GET', '/library'),
    ('GET', '/finance'),
    ('GET', '/messages'),
    ('GET', '/timetable'),
    ('GET', '/teaching_plans'),
    ('GET', '/teacher_dashboard'),
]

with app.test_client() as c:
    # Login
    resp = c.post('/', data={'school_code': school_code, 'login_code': code}, follow_redirects=True)
    print(f"\nLogin: {resp.status_code}")

    for method, route in routes_to_test:
        try:
            if method == 'GET':
                resp = c.get(route, follow_redirects=False)
            else:
                resp = c.post(route, follow_redirects=False)
            if resp.status_code >= 400:
                print(f"  ERROR {method} {route}: {resp.status_code}")
                # Try with follow_redirects to see the actual error
                resp2 = c.get(route, follow_redirects=True)
                print(f"    Followed: {resp2.status_code}")
            else:
                print(f"  OK {method} {route}: {resp.status_code}")
        except Exception as e:
            print(f"  EXCEPTION {method} {route}: {e}")
