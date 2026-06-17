with open('app.py', 'rb') as f:
    data = f.read()

old = b'\'UPDATE teaching_plans SET subject = ?, grade = ?, section = ?, title = ?, description = ?, objectives = ?, content = ?, resources = ?, activities = ?, assessment_methods = ?, duration = ?, start_date = ?, end_date = ?, status = ?, week_number = ?, week_ending = ?, period_duration = ?, day_of_week = ?, strand = ?, sub_strand = ?, content_standard = ?, indicator = ?, performance_indicator = ?, core_competencies = ?, keywords = ?, tlm = ?, \\"references\\" = ?, starter_activities = ?, main_activities = ?, formative_assessment = ?, plenary_reflection = ?, teacher_reflection = ?, attachment_path = ?, attachment_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",\r\n'

new = b'\'UPDATE teaching_plans SET subject = ?, grade = ?, section = ?, title = ?, description = ?, objectives = ?, content = ?, resources = ?, activities = ?, assessment_methods = ?, duration = ?, start_date = ?, end_date = ?, status = ?, week_number = ?, week_ending = ?, period_duration = ?, day_of_week = ?, strand = ?, sub_strand = ?, content_standard = ?, indicator = ?, performance_indicator = ?, core_competencies = ?, keywords = ?, tlm = ?, "\"references\"" = ?, starter_activities = ?, main_activities = ?, formative_assessment = ?, plenary_reflection = ?, teacher_reflection = ?, attachment_path = ?, attachment_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?\',\r\n'

if old in data:
    data = data.replace(old, new)
    with open('app.py', 'wb') as f:
        f.write(data)
    print('Fixed')
else:
    print('Not found')
