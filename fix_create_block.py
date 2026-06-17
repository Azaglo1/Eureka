import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = """query_db(
        'INSERT INTO teaching_plans (school_id, teacher_id, title, subject, grade, section, description, objectives, content, resources, activities, assessment_methods, duration, start_date, end_date, plan_date, status, is_active, week_number, week_ending, period_duration, day_of_week, strand, sub_strand, content_standard, indicator, performance_indicator, core_competencies, keywords, tlm, "references", starter_activities, main_activities, formative_assessment, plenary_reflection, teacher_reflection, attachment_path, attachment_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                session.get("school_id"),
                session.get("user_id"),
                title,
                subject,
                grade,
                section,
                description,
                objectives,
                content,
                resources,
                activities,
                assessment_methods,
                duration_int,
                start_date if start_date else None,
                end_date if end_date else None,
                plan_date if plan_date else None,
                status,
                request.form.get("week_number", "").strip() or None,
                request.form.get("week_ending", "").strip() or None,
                request.form.get("period_duration", "").strip() or None,
                request.form.get("day_of_week", "").strip() or None,
                request.form.get("strand", "").strip(),
                request.form.get("sub_strand", "").strip(),
                request.form.get("content_standard", "").strip(),
                request.form.get("indicator", "").strip(),
                request.form.get("performance_indicator", "").strip(),
                request.form.get("core_competencies", "").strip(),
                request.form.get("keywords", "").strip(),
                request.form.get("tlm", "").strip(),
                request.form.get("references", "").strip(),
                request.form.get("starter_activities", "").strip(),
                request.form.get("main_activities", "").strip(),
                request.form.get("formative_assessment", "").strip(),
                request.form.get("plenary_reflection", "").strip(),
                request.form.get("teacher_reflection", "").strip(),
                attachment_path,
                attachment_name,
            ),
            commit=True
        )"""

new = """query_db(
        'INSERT INTO teaching_plans (school_id, teacher_id, title, subject, grade, section, description, objectives, content, resources, activities, assessment_methods, duration, start_date, end_date, plan_date, status, is_active, week_number, week_ending, period_duration, day_of_week, strand, sub_strand, content_standard, indicator, performance_indicator, core_competencies, keywords, tlm, "references", starter_activities, main_activities, formative_assessment, plenary_reflection, teacher_reflection, attachment_path, attachment_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                session.get("school_id"),
                session.get("user_id"),
                title,
                subject,
                grade,
                section,
                description,
                objectives,
                content,
                resources,
                activities,
                assessment_methods,
                duration_int,
                start_date if start_date else None,
                end_date if end_date else None,
                plan_date if plan_date else None,
                status,
                request.form.get("week_number", "").strip() or None,
                request.form.get("week_ending", "").strip() or None,
                request.form.get("period_duration", "").strip() or None,
                request.form.get("day_of_week", "").strip() or None,
                request.form.get("strand", "").strip(),
                request.form.get("sub_strand", "").strip(),
                request.form.get("content_standard", "").strip(),
                request.form.get("indicator", "").strip(),
                request.form.get("performance_indicator", "").strip(),
                request.form.get("core_competencies", "").strip(),
                request.form.get("keywords", "").strip(),
                request.form.get("tlm", "").strip(),
                request.form.get("references", "").strip(),
                request.form.get("starter_activities", "").strip(),
                request.form.get("main_activities", "").strip(),
                request.form.get("formative_assessment", "").strip(),
                request.form.get("plenary_reflection", "").strip(),
                request.form.get("teacher_reflection", "").strip(),
                attachment_path,
                attachment_name,
            ),
            commit=True
        )"""

if old in content:
    content = content.replace(old, new)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced create_teaching_plan block.')
else:
    print('Exact block not found; leaving file unchanged.')
