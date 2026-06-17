
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')

print(f'SMTP_SERVER: {SMTP_SERVER}')
print(f'SMTP_PORT: {SMTP_PORT}')
print(f'SMTP_EMAIL: {SMTP_EMAIL}')
print(f'SMTP_PASSWORD length: {len(SMTP_PASSWORD)}')
if SMTP_PASSWORD:
    print(f'SMTP_PASSWORD (first 4 chars): {SMTP_PASSWORD[:4]}...')
else:
    print('SMTP_PASSWORD: [EMPTY]')

if not SMTP_EMAIL or not SMTP_PASSWORD:
    print('ERROR: SMTP_EMAIL or SMTP_PASSWORD not set!')
    exit(1)

try:
    print('Attempting to connect to Gmail SMTP...')
    msg = MIMEMultipart()
    msg['From'] = SMTP_EMAIL
    msg['To'] = SMTP_EMAIL  # Send to yourself for testing
    msg['Subject'] = 'Test Email from School System'
    
    body = 'This is a test email from the school management system.'
    msg.attach(MIMEText(body, 'plain'))
    
    if SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    else:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
    server.set_debuglevel(1)  # Enable debug output
    print('Attempting to login...')
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    print('Login successful!')
    
    print('Sending message...')
    server.send_message(msg)
    print('Message sent successfully!')
    server.quit()
    print('Test completed successfully!')
    
except Exception as e:
    print(f'ERROR: {e}')
    print(f'Error type: {type(e).__name__}')

