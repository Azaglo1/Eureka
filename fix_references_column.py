import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix INSERT queries - quote the reserved word 'references'
content = re.sub(
    r'tlm, references, starter',
    'tlm, "references", starter',
    content
)
content = re.sub(
    r'tlm, references, attachment',
    'tlm, "references", attachment',
    content
)

# Fix UPDATE queries - quote 'references' when used as a column target
content = re.sub(
    r'tlm, references = \?',
    'tlm, "references" = ?',
    content
)
content = re.sub(
    r'tlm, references,',
    'tlm, "references",',
    content
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done: quoted reserved word `references` in SQL queries.')
