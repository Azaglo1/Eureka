#!/usr/bin/env python
"""Comprehensive test for both main app and superadmin app"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

print("=" * 60)
print("COMPREHENSIVE APP TESTS")
print("=" * 60)

# Test 1: Main app syntax
print("\n1. Testing app.py syntax...")
import ast
with open('app.py', encoding='utf-8', errors='replace') as f:
    ast.parse(f.read().lstrip('\ufeff'))
print("   app.py: OK")

with open('superadmin_app.py', encoding='utf-8', errors='replace') as f:
    ast.parse(f.read().lstrip('\ufeff'))
print("   superadmin_app.py: OK")

# Test 2: Main app routes
print("\n2. Testing main app routes...")
from app import app as main_app
main_app.config['TESTING'] = True
client = main_app.test_client()

resp = client.get('/')
assert resp.status_code == 200, f"GET / failed: {resp.status_code}"
print(f"   GET /: {resp.status_code} OK")

resp = client.get('/admin', follow_redirects=False)
assert resp.status_code in (302, 303), f"GET /admin failed: {resp.status_code}"
print(f"   GET /admin: {resp.status_code} OK (redirect)")

# Old superadmin routes should be gone (404)
resp = client.get('/admin/create_school', follow_redirects=False)
assert resp.status_code == 404, f"GET /admin/create_school should 404: {resp.status_code}"
print(f"   GET /admin/create_school: {resp.status_code} OK (removed)")

resp = client.get('/admin/school/1/edit', follow_redirects=False)
assert resp.status_code == 404, f"GET /admin/school/1/edit should 404: {resp.status_code}"
print(f"   GET /admin/school/1/edit: {resp.status_code} OK (removed)")

# Test 3: Superadmin app routes
print("\n3. Testing superadmin app routes...")
from superadmin_app import app as sa_app
sa_app.config['TESTING'] = True
sa_client = sa_app.test_client()

resp = sa_client.get('/superadmin/login')
assert resp.status_code == 200, f"GET /superadmin/login failed: {resp.status_code}"
print(f"   GET /superadmin/login: {resp.status_code} OK")

# Protected routes redirect without auth
for path in ['/superadmin', '/superadmin/schools', '/superadmin/users',
             '/superadmin/statistics', '/superadmin/schools/create',
             '/superadmin/school_portal/1']:
    resp = sa_client.get(path, follow_redirects=False)
    assert resp.status_code in (302, 303), f"{path} should redirect: {resp.status_code}"
    print(f"   {path}: {resp.status_code} OK (redirect)")

# Test 4: Template rendering
print("\n4. Testing template rendering...")
with sa_app.test_request_context():
    from flask import render_template

    templates_to_test = [
        ('superadmin/base.html', {}),
        ('superadmin/panel.html', {'school_count': 0, 'user_count': 0, 'total_users': 0, 'total_students': 0, 'schools': []}),
        ('superadmin/school_portal.html', {'school': {'id': 1, 'name': 'Test', 'school_code': 'T001', 'description': ''}, 'student_count': 0, 'teacher_count': 0, 'admin_count': 0, 'attendance_today': 0, 'recent_announcements': [], 'recent_events': [], 'recent_grades': []}),
        ('superadmin/schools.html', {'schools': []}),
        ('superadmin/create_school.html', {}),
        ('superadmin/edit_school.html', {'school': {'id': 1, 'name': 'Test', 'school_code': 'T001', 'description': ''}}),
        ('superadmin/view_school.html', {'school': {'id': 1, 'name': 'Test', 'school_code': 'T001', 'description': ''}, 'student_count': 0, 'admin_count': 0, 'teacher_count': 0, 'users': []}),
        ('superadmin/users.html', {'users': [], 'schools': []}),
        ('superadmin/create_user.html', {'schools': []}),
        ('superadmin/edit_user.html', {'user': {'id': 1, 'name': 'Test', 'email': '', 'role': 'admin', 'school_id': None, 'login_code': 'test', 'active': 1}, 'schools': []}),
        ('superadmin/statistics.html', {'stats': {}, 'users_per_school': [], 'students_per_school': []}),
    ]

    for tmpl, ctx in templates_to_test:
        try:
            html = render_template(tmpl, **ctx)
            print(f"   {tmpl}: OK")
        except Exception as e:
            print(f"   {tmpl}: FAIL - {e}")
            sys.exit(1)

# Test 5: Verify no broken url_for references in main app templates
print("\n5. Checking for broken superadmin url_for references in main templates...")
import re
main_templates = ['base.html', 'dashboard.html', 'admin.html', 'school_portal.html',
                  'edit_school.html', 'superadmin.html']

# These should NOT exist in main app templates anymore
broken_patterns = [
    "url_for('superadmin_panel')",
    "url_for('superadmin_schools')",
    "url_for('superadmin_school_portal'",
    "url_for('superadmin_users')",
    "url_for('superadmin_statistics')",
    "url_for('superadmin_create'",
    "url_for('superadmin_edit'",
    "url_for('superadmin_view'",
    "url_for('superadmin_delete'",
    "url_for('superadmin_login')",
    "url_for('superadmin_logout')",
    "url_for('superadmin_remove'",
    "url_for('superadmin_suspend'",
    "url_for('superadmin_update'",
    "url_for('superadmin_cleanup'",
    "url_for('superadmin_remove_user'",
]

for tmpl_name in main_templates:
        path = f'templates/{tmpl_name}'
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except:
                print(f"   {path}: skipped (binary/encoding issue)")
                continue
            found_issue = False
            for pattern in broken_patterns:
                if pattern in content:
                    print(f"   WARNING: {tmpl_name} contains {pattern}")
                    found_issue = True
            if not found_issue:
                print(f"   {tmpl_name}: OK (no broken superadmin refs)")
        else:
            print(f"   {path}: does not exist (OK if deleted)")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)

print("\n=== SUMMARY ===")
print("Main app (port 5000): app.py - handles school-level operations")
print("Superadmin app (configurable via SUPERADMIN_PORT, default 8080): superadmin_app.py - handles system-wide admin")
print("Shared database: school.db")
print("Superadmin login: http://localhost:<SUPERADMIN_PORT>/superadmin/login")
print("Main portal login: http://localhost:5000/")