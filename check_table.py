import sys
sys.path.insert(0, r'C:\Users\LENOVO\OneDrive\Desktop\school')
import os
os.chdir(r'C:\Users\LENOVO\OneDrive\Desktop\school')
from app import app

with app.test_request_context('/'):
    from app import init_db, get_db
    init_db()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'school_subjects'")
    rows = cur.fetchall()
    print('school_subjects found:', rows)
    cur.close()
    db.close()
