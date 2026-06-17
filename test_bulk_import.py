#!/usr/bin/env python
"""Test bulk user import feature"""
import os
import sys
import io
import csv
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from superadmin_app import app as sa_app, query_db, get_db, ROLE_SUPERADMIN, ROLE_TEACHER, ROLE_STUDENT
from werkzeug.security import generate_password_hash

sa_app.config['TESTING'] = True

def test_import():
    print("=" * 60)
    print("BULK USER IMPORT TEST")
    print("=" * 60)

    with sa_app.test_client() as client:
        # First, create a superadmin user via init route
        print("\n1. Creating superadmin user...")
        with sa_app.app_context():
            db = get_db()
            cur = db.cursor()
            # Check if superadmin exists
            existing = query_db("SELECT id FROM users WHERE role = ?", (ROLE_SUPERADMIN,), one=True)
            if not existing:
                password_hash = generate_password_hash('superpass123')
                cur.execute(
                    "INSERT INTO users (name, email, role, login_code, password_hash, privileges) VALUES (?, ?, ?, ?, ?, ?)",
                    ('System Superadmin', 'superadmin@system.local', ROLE_SUPERADMIN, 'SYSADMIN001', password_hash, 'all')
                )
                db.commit()
                print("   Created superadmin user: SYSADMIN001 / superpass123")
            else:
                print("   Superadmin already exists")

        # Now login
        print("\n2. Logging in as superadmin...")
        resp = client.post('/superadmin/login', data={
            'login_code': 'SYSADMIN001'
        }, follow_redirects=True)
        print(f"   Login status: {resp.status_code}")
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        print("   [OK] Logged in successfully")

        # Test template download
        print("\n2. Testing template download...")
        resp = client.get('/superadmin/users/template')
        print(f"   Template download: {resp.status_code}")
        assert resp.status_code == 200, f"Template download failed: {resp.status_code}"
        assert 'text/csv' in resp.content_type or 'csv' in resp.content_type
        content = resp.data.decode('utf-8')
        print(f"   Template content preview:\n{content[:200]}")
        assert 'name,email,role,login_code' in content
        print("   [OK] Template OK")

        # Create a test CSV
        print("\n3. Creating test CSV...")
        test_csv = io.StringIO()
        writer = csv.writer(test_csv)
        writer.writerow(['name', 'email', 'role', 'login_code', 'password', 'school_id', 'student_number', 'grade', 'section'])
        writer.writerow(['Test Teacher', 'testteacher@example.com', 'teacher', 'TEST001', 'TestPass123', '1', '', '', ''])
        writer.writerow(['Test Student', 'teststudent@example.com', 'student', 'TEST002', 'TestPass456', '1', 'TESTSTU001', '10', 'A'])
        writer.writerow(['Test Parent', 'testparent@example.com', 'parent', 'TEST003', 'TestPass789', '1', '', '', ''])
        test_csv.seek(0)

        # Upload CSV for preview
        print("\n4. Uploading CSV for preview...")
        resp = client.post('/superadmin/users/import',
            data={'csv_file': (io.BytesIO(test_csv.getvalue().encode('utf-8')), 'test_users.csv')},
            content_type='multipart/form-data')
        print(f"   Upload preview: {resp.status_code}")
        assert resp.status_code == 200, f"Upload failed: {resp.status_code}"
        assert b'Preview' in resp.data or b'preview' in resp.data
        print("   [OK] Preview page rendered")

        # Check that preview shows all 3 users
        data = resp.data.decode('utf-8')
        assert 'Test Teacher' in data
        assert 'Test Student' in data
        assert 'Test Parent' in data
        print("   [OK] All 3 users shown in preview")

        # Confirm import
        print("\n5. Confirming import...")
        # Need to re-upload the file for confirmation
        test_csv.seek(0)
        resp = client.post('/superadmin/users/import',
            data={
                'csv_file': (io.BytesIO(test_csv.getvalue().encode('utf-8')), 'test_users.csv'),
                'confirm': '1'
            },
            content_type='multipart/form-data')
        print(f"   Import confirm: {resp.status_code}")
        assert resp.status_code == 200, f"Import failed: {resp.status_code}"
        assert b'Import complete' in resp.data or b'succeeded' in resp.data
        print("   [OK] Import completed")

        # Verify users were created
        print("\n6. Verifying created users...")
        for login_code in ['TEST001', 'TEST002', 'TEST003']:
            user = query_db("SELECT * FROM users WHERE login_code = ?", (login_code,), one=True)
            assert user is not None, f"User {login_code} not found"
            print(f"   [OK] {login_code}: {user['name']} ({user['role']})")

        # Verify student record for student user
        student = query_db("SELECT * FROM students WHERE student_number = ?", ('TESTSTU001',), one=True)
        assert student is not None, "Student record not created"
        print(f"   [OK] Student record: {student['name']} (ID: {student['id']})")

    print("\n" + "=" * 60)
    print("ALL BULK IMPORT TESTS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    try:
        test_import()
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
