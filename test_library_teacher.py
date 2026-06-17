"""Smoke-test: library accessible to both admin and teacher roles."""
import sys
sys.path.insert(0, ".")

from app import app

passed = failed = 0

def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

# ── Admin session ──────────────────────────────────────────────────────────────
with app.test_client() as c:
    with c.session_transaction() as s:
        s["user_id"]    = 1
        s["user_name"]  = "Admin"
        s["role"]       = "admin"
        s["school_id"]  = 1

    r = c.get("/library")
    html = r.data.decode()
    check("ADMIN GET /library 200", r.status_code == 200)
    check("ADMIN sees Add Book form", "Add New Book" in html)
    check("ADMIN sees upload route", 'action="/library/upload"' in html)
    check("ADMIN sees upload_audio route", 'action="/library/upload_audio/' in html)
    check("ADMIN sees upload_cover route", 'action="/library/upload_cover/' in html)
    check("ADMIN sees delete button", "delete-btn" in html)
    check("ADMIN sees Gatsby", "The Great Gatsby" in html)
    check("ADMIN sees Hawking", "Stephen Hawking" in html)

# ── Teacher session ───────────────────────────────────────────────────────────
with app.test_client() as c:
    with c.session_transaction() as s:
        s["user_id"]    = 2
        s["user_name"]  = "Teacher"
        s["role"]       = "teacher"
        s["school_id"]  = 1

    r = c.get("/library")
    html = r.data.decode()
    check("TEACHER GET /library 200", r.status_code == 200)
    check("TEACHER sees Gatsby", "The Great Gatsby" in html)
    check("TEACHER sees Hawking", "Stephen Hawking" in html)
    check("TEACHER sees Add Book form", "Add New Book" in html)
    check("TEACHER no upload route", 'action="/library/upload"' not in html)
    check("TEACHER no upload_audio route", 'action="/library/upload_audio/' not in html)
    check("TEACHER no upload_cover route", 'action="/library/upload_cover/' not in html)
    check("TEACHER no delete button", '>🗑 Remove</button>' not in html)
    check("TEACHER sees audio player", "audio-player" in html)
    check("TEACHER no download link (no file uploaded)", 'href="/library/download/' not in html)

# ── Route list ────────────────────────────────────────────────────────────────
from app import app as _app
lib_routes = [r.rule for r in _app.url_map.iter_rules() if "library" in r.rule]
check("All library routes registered (>= 10)", len(lib_routes) >= 10)

print(f"\n{passed} passed, {failed} failed out of {passed+failed} checks.")
