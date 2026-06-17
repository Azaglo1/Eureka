import sqlite3
conn = sqlite3.connect('school.db')
cur = conn.cursor()
tables = ['schools','users','students','grades','attendances','announcements','events','assignments','teaching_plans','teacher_assignments','timetable','library_books','book_loans','certificates','medical_records','fees','fee_payments','messages']
for t in tables:
    cur.execute(f'PRAGMA table_info({t})')
    cols = [r[1] for r in cur.fetchall()]
    print(f'{t}: {cols}')
