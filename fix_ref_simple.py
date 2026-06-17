import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace \"references\" with 'references' since outer string quotes are "
content = content.replace('"references"', "'references'")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')
