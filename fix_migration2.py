import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the old teaching_plans migration and the old grade_columns loop
old_pattern = r'    # Add missing columns to teaching_plans table for PostgreSQL.*?\n\n     # Add student_report table for terminal report metadata'

new_block = '''     # Add student_report table for terminal report metadata'''

content = re.sub(old_pattern, new_block, content, flags=re.DOTALL)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Migration block cleaned')