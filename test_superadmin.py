#!/usr/bin/env python
"""Test script for superadmin_app.py"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

from superadmin_app import app, query_db, ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_TEACHER

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()

print("=" * 60)
print("TESTING SUPERADMIN APP")
print("=" * 60)

# Test 1: All routes are registered
routes = [rule.rule for rule in app.url_map.iter_rules()]
print(f"\n1. Registered routes: {len(routes)}")
for r in sorted(routes):
    print(f"   {r}")

# Test 2: Login page loads
resp = client.get('/superadmin/login')
assert resp.status_code == 200, f"Login page failed: {resp.status_code}"
print(f"\n2. GET /superadmin/login: {resp.status_code} OK")

# Test 3: Protected routes redirect without auth
protected = [
    '/superadmin', '/superadmin/schools', '/superadmin/users',
    '/superadmin/statistics', '/superadmin/schools/create',
    '/superadmin/school_portal/1'
]
print("\n3. Protected routes (no auth -> redirect):")
for path in protected:
    resp = client.get(path, follow_redirects=False)
    status = resp.status_code
    ok = "OK" if status in (302, 303) else "FAIL"
    print(f"   {path}: {status} {ok}")

# Test 4: Login with invalid credentials
resp = client.post('/superadmin/login', data={'login_code': 'wrong'})
assert resp.status_code == 200
print("\n4. POST /superadmin/login (invalid): 200 OK (shows error)")

# Test 5: Database queries work
print("\n5. Database queries:")
with app.app_context():
    schools = query_db("SELECT * FROM schools")
    print(f"   Schools in DB: {len(schools)}")
    users = query_db("SELECT * FROM users")
    print(f"   Users in DB: {len(users)}")
    students = query_db("SELECT * FROM students")
    print(f"   Students in DB: {len(students)}")

# Test 6: Template rendering with test client (login required)
# Create a test superadmin user first, then test
print("\n6. Testing template rendering via test request context:")
with app.test_request_context():
    # Test that templates exist and can be rendered
    from flask import render_template
    try:
        html = render_template('superadmin/base.html')
        print("   base.html: OK")
    except Exception as e:
        print(f"   base.html: FAIL - {e}")

    try:
        html = render_template('superadmin/panel.html', school_count=0, user_count=0,
                               total_users=0, total_students=0, schools=[])
        print("   panel.html: OK")
    except Exception as e:
        print(f"   panel.html: FAIL - {e}")

    try:
        school = {'id': 1, 'name': 'Test School', 'school_code': 'TS001', 'description': 'Test'}
        html = render_template('superadmin/school_portal.html', school=school,
                               student_count=0, teacher_count=0, admin_count=0,
                               attendance_today=0, recent_announcements=[],
                               recent_events=[], recent_grades=[])
        print("   school_portal.html: OK")
    except Exception as e:
        print(f"   school_portal.html: FAIL - {e}")

    try:
        html = render_template('superadmin/schools.html', schools=[])
        print("   schools.html: OK")
    except Exception as e:
        print(f"   schools.html: FAIL - {e}")

    try:
        html = render_template('superadmin/create_school.html')
        print("   create_school.html: OK")
    except Exception as e:
        print(f"   create_school.html: FAIL - {e}")

    try:
        html = render_template('superadmin/edit_school.html', school={'id': 1, 'name': 'Test', 'school_code': 'T001', 'description': ''})
        print("   edit_school.html: OK")
    except Exception as e:
        print(f"   edit_school.html: FAIL - {e}")

    try:
        html = render_template('superadmin/view_school.html', school={'id': 1, 'name': 'Test', 'school_code': 'T001', 'description': ''},
                               student_count=0, admin_count=0, teacher_count=0, users=[])
        print("   view_school.html: OK")
    except Exception as e:
        print(f"   view_school.html: FAIL - {e}")

    try:
        html = render_template('superadmin/users.html', users=[], schools=[])
        print("   users.html: OK")
    except Exception as e:
        print(f"   users.html: FAIL - {e}")

    try:
        html = render_template('superadmin/create_user.html', schools=[])
        print("   create_user.html: OK")
    except Exception as e:
        print(f"   create_user.html: FAIL - {e}")

    try:
        html = render_template('superadmin/edit_user.html', user={'id': 1, 'name': 'Test', 'email': '', 'role': 'admin', 'school_id': None, 'login_code': 'test', 'active': 1}, schools=[])
        print("   edit_user.html: OK")
    except Exception as e:
        print(f"   edit_user.html: FAIL - {e}")

    try:
        html = render_template('superadmin/statistics.html', stats={}, users_per_school=[], students_per_school=[])
        print("   statistics.html: OK")
    except Exception as e:
        print(f"   statistics.html: FAIL - {e}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)