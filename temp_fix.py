with open('app.py', 'r') as f:
    lines = f.readlines()

# Check lines around 1711
for i in range(1708, 1715):
    if i < len(lines):
        print('Line', i+1, ':', repr(lines[i]))