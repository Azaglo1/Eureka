with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix ORDER BY avg_pct
content = content.replace(
    'grade_query += " WHERE s.school_id = ? GROUP BY s.id ORDER BY avg_pct DESC, s.name"',
    'grade_query += " WHERE s.school_id = ? GROUP BY s.id ORDER BY grade_count DESC, s.name"'
)

# Fix grade_summaries building - remove avg_pct
old_summary = '''    grade_summaries = []
    for grade in grades_summary:
        avg_pct = grade["avg_pct"]
        grade_summaries.append({
            "id": grade["id"],
            "name": grade["name"],
            "student_number": grade["student_number"],
            "grade_level": grade["grade"],
            "section": grade["section"],
            "avg_pct": round(avg_pct, 2) if avg_pct is not None else None,
            "grade_count": grade["grade_count"],
            "position": None,
        })

    rank = 0
    last_score = None
    position = 0
    for student in grade_summaries:
        if student["avg_pct"] is not None:
            rank += 1
            if last_score is None or student["avg_pct"] != last_score:
                position = rank
                last_score = student["avg_pct"]
            student["position"] = position
        else:
            student["position"] = "-"

    if selected_student_id:
        try:
            selected_student_id = int(selected_student_id)
        except ValueError:
            selected_student_id = students[0]["id"] if students else None
    else:
        selected_student_id = students[0]["id"] if students else None

    students_with_grades = [row for row in grade_summaries if row["avg_pct"] is not None]
    class_average = (
        round(sum(row["avg_pct"] for row in students_with_grades) / len(students_with_grades), 2)
        if students_with_grades
        else None
    )'''

new_summary = '''    grade_summaries = []
    for grade in grades_summary:
        grade_summaries.append({
            "id": grade["id"],
            "name": grade["name"],
            "student_number": grade["student_number"],
            "grade_level": grade["grade"],
            "section": grade["section"],
            "grade_count": grade["grade_count"],
            "position": None,
        })

    rank = 0
    last_count = None
    position = 0
    for student in grade_summaries:
        if student["grade_count"] > 0:
            rank += 1
            if last_count is None or student["grade_count"] != last_count:
                position = rank
                last_count = student["grade_count"]
            student["position"] = position
        else:
            student["position"] = "-"

    if selected_student_id:
        try:
            selected_student_id = int(selected_student_id)
        except ValueError:
            selected_student_id = students[0]["id"] if students else None
    else:
        selected_student_id = students[0]["id"] if students else None

    students_with_grades = [row for row in grade_summaries if row["grade_count"] > 0]
    class_average = (
        round(sum(row["grade_count"] for row in students_with_grades) / len(students_with_grades), 2)
        if students_with_grades
        else None
    )'''

content = content.replace(old_summary, new_summary)

# Fix class_average display in template
content = content.replace(
    '<h3 class="stat-value">{{ class_average|default(\'--\', true) }}%</h3>',
    '<h3 class="stat-value">{{ class_average|default(\'--\', true) }}</h3>'
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done fixing avg_pct references")
