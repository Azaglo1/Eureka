import re

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the create_teaching_plan function and replace it completely
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if 'def create_teaching_plan():' in line and start_idx is None:
        start_idx = i
    if start_idx is not None and 'def edit_teaching_plan(plan_id):' in line:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    # Read the original function to preserve variable names/formatting style
    new_function = '''def create_teaching_plan():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        grade = request.form.get("grade", "").strip()
        section = request.form.get("section", "").strip()
        description = request.form.get("description", "").strip()
        objectives = request.form.get("objectives", "").strip()
        content = request.form.get("content", "").strip()
        resources = request.form.get("resources", "").strip()
        activities = request.form.get("activities", "").strip()
        assessment_methods = request.form.get("assessment_methods", "").strip()
        duration = request.form.get("duration", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        plan_date = request.form.get("plan_date", "").strip()
        status = request.form.get("status", "draft").strip()
        
        if not title or not subject or not grade or not section:
            flash("Title, subject, grade, and section are required.", "warning")
            return redirect(url_for("create_teaching_plan"))
        
        try:
            duration_int = int(duration) if duration else None
        except ValueError:
            duration_int = None
        
        query_db(
            "INSERT INTO teaching_plans (school_id, teacher_id, title, subject, grade, section, description, objectives, content, resources, activities, assessment_methods, duration, start_date, end_date, plan_date, status, is_active, week_number, week_ending, period_duration, day_of_week, strand, sub_strand, content_standard, indicator, performance_indicator, core_competencies, keywords, tlm, lesson_references, starter_activities, main_activities, formative_assessment, plenary_reflection, teacher_reflection, attachment_path, attachment_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                None,
                None,
            ),
            commit=True
        )

        attachment_path = None
        attachment_name = None
        uploaded = request.files.get("plan_attachment")
        if uploaded and uploaded.filename != "":
            if not _allowed_file(uploaded.filename, ALLOWED_ASSIGNMENT_EXTENSIONS):
                flash("Invalid file type. Allowed: PDF, DOC, DOCX, TXT, ZIP, RAR.", "danger")
                return redirect(url_for("create_teaching_plan"))
            _ensure_upload_dirs()
            attachment_name = f"plan_{secure_filename(uploaded.filename)}"
            attachment_path = f"uploads/{attachment_name}"
            uploaded.save(os.path.join(UPLOAD_FOLDER, attachment_name))
            
            if attachment_path:
                last_id_row = query_db("SELECT last_insert_rowid()", one=True)
                last_id = last_id_row[0] if last_id_row else None
                execute_db(
                    "UPDATE teaching_plans SET attachment_path = ?, attachment_name = ? WHERE id = ?",
                    (attachment_path, attachment_name, last_id)
                )

        flash("Teaching plan created successfully!", "success")
        return redirect(url_for("teaching_plans"))
    
    # GET request - show form
    return render_template("create_teaching_plan.html")

'''
    
    lines[start_idx:end_idx] = [new_function]
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Replaced create_teaching_plan (lines {start_idx+1}-{end_idx})")
else:
    print(f"Could not find function boundaries: start={start_idx}, end={end_idx}")
