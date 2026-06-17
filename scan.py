import os

app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
in_string = False
with open(app_path, encoding="utf-8", errors="replace") as source_file:
    for line_number, line in enumerate(source_file, start=1):
        if '"""' in line:
            if not in_string:
                in_string = True
                print("Start at line", line_number, ":", line.strip())
            else:
                in_string = False
                print("End at line", line_number, ":", line.strip())
if in_string:
    print("Unterminated string")