with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

changed = []

for i, line in enumerate(lines):
    if i + 1 < len(lines) and 'INSERT INTO teaching_plans' in lines[i + 1] and 'query_db' in line:
        old = lines[i]
        new = old.replace('"""', "'''")
        if new != old:
            lines[i] = new
            changed.append(('insert', i + 1, old.rstrip(), new.rstrip()))
    if i + 1 < len(lines) and 'UPDATE teaching_plans' in lines[i + 1] and 'query_db' in line:
        old = lines[i]
        new = old.replace('"""', "'''")
        if new != old:
            lines[i] = new
            changed.append(('update', i + 1, old.rstrip(), new.rstrip()))

if changed:
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

for kind, lineno, before, after in changed:
    print(f'{kind} updated around line {lineno}\n  {before}\n  -> {after}\n')
