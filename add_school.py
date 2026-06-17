import sqlite3

conn = sqlite3.connect('school.db')
cursor = conn.cursor()

# Check if school already exists
cursor.execute('SELECT * FROM schools WHERE name = ? OR school_code = ?', ('Gracy International', 'GRACY001'))
existing = cursor.fetchone()

if existing:
    print(f'School already exists: {existing}')
else:
    # Add the school
    cursor.execute('INSERT INTO schools (name, school_code, description) VALUES (?, ?, ?)',
                   ('Gracy International', 'GRACY001', 'Gracy International School'))
    conn.commit()
    school_id = cursor.lastrowid
    print(f'School added successfully!')
    print(f'  ID: {school_id}')
    print(f'  Name: Gracy International')
    print(f'  Code: GRACY001')

# Show all schools
cursor.execute('SELECT * FROM schools')
schools = cursor.fetchall()
print(f'\nAll schools in database:')
for school in schools:
    print(f'  - {school[1]} ({school[2]})')

conn.close()
