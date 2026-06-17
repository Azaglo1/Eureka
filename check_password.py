
import os
from dotenv import load_dotenv

load_dotenv()
password = os.environ.get('SMTP_PASSWORD', '')
print(f'Password: {repr(password)}')
print(f'Length: {len(password)}')
for i, char in enumerate(password):
    print(f'{i}: {char} (ord={ord(char)})')

