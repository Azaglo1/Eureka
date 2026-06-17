import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# In create_teaching_plan query line
old_insert = 'query_db(\n        "INSERT INTO teaching_plans'
new_insert = "query_db(\n        'INSERT INTO teaching_plans"
content = content.replace(old_insert, new_insert, 1)

# In edit_teaching_plan query line
old_update = 'query_db(\n        "UPDATE teaching_plans'
new_update = "query_db(\n        'UPDATE teaching_plans"
content = content.replace(old_update, new_update, 1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed query strings')
