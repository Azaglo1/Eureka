with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '\"references\"' in line and 'UPDATE teaching_plans' in line:
        lines[idx] = line.replace('\\"references\\"', "'\"references\"'")
        print(f'Fixed line {idx + 1}: replaced escaped quotes')

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
