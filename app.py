import os
import sqlite3
import smtplib
import base64
import html
import json
import uuid
import csv
import io
import re
import requests
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, timedelta
from urllib.parse import quote
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, render_template_string, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from dotenv import load_dotenv
from db_utils import get_db, connect_db, has_table_columns, add_column_if_not_exists

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "school.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
AUDIO_FOLDER = os.path.join(UPLOAD_FOLDER, "audio")
COVER_FOLDER = os.path.join(UPLOAD_FOLDER, "covers")
ALLOWED_BOOK_EXTENSIONS = {"pdf", "epub", "mobi", "doc", "docx", "txt"}
ALLOWED_ASSIGNMENT_EXTENSIONS = {"pdf", "doc", "docx", "txt", "zip", "rar"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "aac"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

def validate_production_config():
    critical_vars = {
        "FLASK_SECRET_KEY": "At least 32 characters of random data",
        "POSTGRES_HOST": "PostgreSQL database host",
        "POSTGRES_USER": "PostgreSQL database user",
        "POSTGRES_PASSWORD": "PostgreSQL database password",
        "POSTGRES_DB": "PostgreSQL database name",
    }
    optional_but_important = {
        "SMTP_EMAIL": "SMTP email for sending notifications",
        "SMTP_PASSWORD": "SMTP password for sending notifications",
        "TWILIO_ACCOUNT_SID": "Twilio account for SMS notifications",
        "TWILIO_AUTH_TOKEN": "Twilio auth token",
    }
    missing_critical = []
    missing_important = []
    for var, description in critical_vars.items():
        if not os.environ.get(var):
            missing_critical.append(f"  - {var}: {description}")
    for var, description in optional_but_important.items():
        if not os.environ.get(var):
            missing_important.append(f"  - {var}: {description} (optional)")
    if missing_critical:
        print("[WARNING] Missing critical environment variables:")
        for msg in missing_critical:
            print(msg)
        print("\nApplication may fail in production. Please set these in your .env file.")
    if missing_important:
        print("[INFO] Optional environment variables not configured:")
        for msg in missing_important:
            print(msg)
    if os.environ.get("FLASK_DEBUG", "false").lower() == "true" and os.environ.get("FLASK_RUN_FROM_CLI") != "true":
        print("[WARNING] FLASK_DEBUG is enabled. Disable in production.")

validate_production_config()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

def _basic_pdf_table_commands(rows):
    if not rows:
        return []

    commands = []
    y = 780
    for row_index, row in enumerate(rows):
        column_count = max(len(row), 1)
        if column_count == 8:
            widths = [85, 35, 50, 50, 50, 50, 50, 165]
        elif column_count == 2:
            widths = [140, 395]
        else:
            widths = [535 / column_count] * column_count
        row_height = 34 if column_count == 8 else 24
        x = 30
        for column_index, width in enumerate(widths):
            value = row[column_index] if column_index < len(row) else ""
            words = value.split()
            lines = []
            current = ""
            max_chars = max(8, int(width / 4.5))
            for word in words:
                candidate = f"{current} {word}".strip()
                if len(candidate) > max_chars and current:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                lines.append(current)
            commands.append(f"{x:.1f} {y - row_height:.1f} {width:.1f} {row_height:.1f} re S")
            for line_index, line in enumerate(lines[:2]):
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.extend(["BT", "/F1 7 Tf", f"{x + 3:.1f} {y - 11 - (line_index * 9):.1f} Td", f"({escaped}) Tj", "ET"])
            x += width
        y -= row_height
        if y < 35:
            break
    return commands


def generate_pdf_from_html(html_content):
    class ReportTextParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.lines = []
            self.current = ""
            self.ignored_depth = 0
            self.table_rows = []
            self.current_row = None
            self.current_cell = None

        def handle_data(self, data):
            if self.ignored_depth:
                return
            text = " ".join(data.split())
            if text:
                if self.current_cell is not None:
                    self.current_cell += (" " if self.current_cell else "") + text
                    return
                self.current += (" " if self.current else "") + text

        def handle_starttag(self, tag, attrs):
            if tag in {"style", "script"}:
                self.ignored_depth += 1
                return
            if self.ignored_depth:
                return
            if tag == "tr":
                self.current_row = []
                return
            if tag in {"td", "th"} and self.current_row is not None:
                self.current_cell = ""
                return
            if tag in {"h1", "h2", "h3", "p", "tr", "div"} and self.current:
                self.lines.append(self.current)
                self.current = ""

        def handle_endtag(self, tag):
            if tag in {"style", "script"}:
                self.ignored_depth = max(0, self.ignored_depth - 1)
                return
            if self.ignored_depth:
                return
            if tag in {"td", "th"} and self.current_row is not None and self.current_cell is not None:
                self.current_row.append(self.current_cell)
                self.current_cell = None
                return
            if tag == "tr" and self.current_row is not None:
                if self.current_row:
                    self.table_rows.append(self.current_row)
                self.current_row = None
                return
            if tag in {"h1", "h2", "h3", "p", "tr", "div", "li"} and self.current:
                self.lines.append(self.current)
                self.current = ""

        def finish(self):
            if self.current:
                self.lines.append(self.current)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes, None
    except Exception as e:
        print(f"[PDF ERROR] Failed to generate PDF with WeasyPrint: {e}")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            parser = ReportTextParser()
            parser.feed(html_content)
            parser.finish()

            output = io.BytesIO()
            document = canvas.Canvas(output, pagesize=A4)
            _, page_height = A4
            y = page_height - 40
            document.setFont("Helvetica", 9)
            for line in parser.lines:
                words = line.split()
                current_line = ""
                for word in words:
                    candidate = f"{current_line} {word}".strip()
                    if document.stringWidth(candidate, "Helvetica", 9) > 520:
                        document.drawString(40, y, current_line)
                        y -= 13
                        current_line = word
                    else:
                        current_line = candidate
                if current_line:
                    document.drawString(40, y, current_line)
                    y -= 13
                if y < 40:
                    document.showPage()
                    document.setFont("Helvetica", 9)
                    y = page_height - 40
            document.save()
            return output.getvalue(), None
        except Exception as fallback_error:
            print(f"[PDF ERROR] ReportLab fallback failed: {fallback_error}")
            try:
                parser = ReportTextParser()
                parser.feed(html_content)
                parser.finish()
                # Every visible report element is represented by a table row.
                # Do not render parser.lines separately or content appears above the tables.
                lines = []
                wrapped_lines = []
                for line in lines:
                    words = line.split()
                    current = ""
                    for word in words:
                        candidate = f"{current} {word}".strip()
                        if len(candidate) > 92:
                            wrapped_lines.append(current)
                            current = word
                        else:
                            current = candidate
                    if current:
                        wrapped_lines.append(current)

                table_pages = [
                    parser.table_rows[index:index + 18]
                    for index in range(0, len(parser.table_rows), 18)
                ] or [[]]
                page_lines = [[] for _ in table_pages]
                objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
                page_refs = []
                for page_number, page_lines_group in enumerate(page_lines, start=1):
                    content = ["BT", "/F1 9 Tf", "40 790 Td"]
                    for line in page_lines_group:
                        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                        content.append(f"({escaped}) Tj")
                        content.append("0 -14 Td")
                    content.append("ET")
                    if table_pages[page_number - 1]:
                        content.extend(_basic_pdf_table_commands(table_pages[page_number - 1]))
                    content_bytes = "\n".join(content).encode("latin-1", errors="replace")
                    content_ref = len(objects) + 1
                    objects.append(f"<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii") + content_bytes + b"\nendstream")
                    page_ref = len(objects) + 1
                    objects.append(
                        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {len(objects) + 2} 0 R >> >> /Contents {content_ref} 0 R >>".encode("ascii")
                    )
                    page_refs.append(page_ref)
                font_ref = len(objects) + 1
                objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
                objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{ref} 0 R' for ref in page_refs)}] /Count {len(page_refs)} >>".encode("ascii")

                pdf = bytearray(b"%PDF-1.4\n")
                offsets = [0]
                for object_number, object_data in enumerate(objects, start=1):
                    offsets.append(len(pdf))
                    pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
                    pdf.extend(object_data)
                    pdf.extend(b"\nendobj\n")
                xref_offset = len(pdf)
                pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
                for offset in offsets[1:]:
                    pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
                pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii"))
                return bytes(pdf), None
            except Exception as basic_pdf_error:
                print(f"[PDF ERROR] Basic PDF fallback failed: {basic_pdf_error}")
                return None, basic_pdf_error



@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Superadmin portal configuration
SUPERADMIN_PORT = os.environ.get("SUPERADMIN_PORT", "8080")
SUPERADMIN_URL = f"http://localhost:{SUPERADMIN_PORT}"

ROLE_ADMIN = "admin"
ROLE_SUPERADMIN = "superadmin"
ROLE_TEACHER = "teacher"
ROLE_PARENT = "parent"
ROLE_STUDENT = "student"

# Email configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# Debug: Check if email credentials are loaded
print(f"[EMAIL CONFIG] SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
if SMTP_EMAIL and SMTP_PASSWORD:
    print("[EMAIL CONFIG] Email credentials loaded successfully")
else:
    print("[EMAIL CONFIG WARNING] Email credentials not found in environment variables")

# SMS configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")

SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "").lower().strip()
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_API_URL = os.environ.get("SMS_API_URL", "")
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "")

# WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = "v17.0"
TEMP_FILES_DIR = os.path.join(BASE_DIR, "temp_exports")
os.makedirs(TEMP_FILES_DIR, exist_ok=True)


def normalize_phone_number(phone, default_country_code="233"):
    """Return an E.164-ish phone number, defaulting local numbers to Ghana."""
    if not phone:
        return None

    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        digits = "".join(ch for ch in cleaned[1:] if ch.isdigit())
        return f"+{digits}" if digits else None

    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("00"):
        return f"+{digits[2:]}"
    if digits.startswith(default_country_code):
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+{default_country_code}{digits[1:]}"
    return f"+{digits}"


def twilio_error_message(error_body):
    try:
        error_data = json.loads(error_body)
    except json.JSONDecodeError:
        return "SMS provider rejected the message. Check Twilio settings and phone number format."

    code = error_data.get("code")
    message = error_data.get("message", "Twilio rejected the message.")
    known_errors = {
        20003: "Twilio authentication failed. Check your Account SID and Auth Token.",
        21211: "The parent phone number is invalid. Use a Ghana number like 0546859356 or +233546859356.",
        21606: "Your Twilio From number is invalid, not SMS-capable, or not owned by this Twilio account.",
        21608: "Your Twilio trial account can only send SMS to verified recipient numbers.",
        21408: "SMS permission is not enabled for this destination country on your Twilio account.",
    }
    if code in known_errors:
        return known_errors[code]
    return f"Twilio rejected the SMS: {message}"


def send_email(recipient_email, subject, body, sender_name="Eureka School", attachment=None, attachment_filename=None):
    """Send email via Gmail SMTP. attachment should be (content_bytes, mimetype) or (content_str, mimetype)."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"[EMAIL DEBUG] Email not configured. Would send to {recipient_email}")
        return False, "Email not configured. Please check SMTP_EMAIL and SMTP_PASSWORD environment variables."
    
    def build_message(attachment_content=None):
        formatted_body = html.escape(body).replace("\n", "<br>")
        
        # If we have attachment content for fallback, include it inline
        if attachment_content:
            formatted_body = f"{formatted_body}<br><br><strong>Grade Report Document:</strong><br><pre>{html.escape(attachment_content)}</pre>"
        
        email_body = f"""
        <html>
            <body>
                <p>Hello,</p>
                <p>{formatted_body}</p>
                <br>
                <p>Best regards,<br>{sender_name}</p>
            </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(email_body, "html"))
        
        return msg
    
    def send_msg(msg):
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
        with server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        return True, ""
    
    try:
        msg = build_message()

        if attachment is not None and attachment_filename:
            if isinstance(attachment, tuple):
                attachment_content, mime_type = attachment
                main_type, sub_type = (mime_type.split('/', 1) + ['octet-stream'])[:2]
            elif isinstance(attachment, str):
                attachment_content = attachment.encode('utf-8')
                main_type, sub_type = 'text', 'plain'
            else:
                attachment_content = attachment
                main_type, sub_type = 'application', 'octet-stream'
            if attachment_content is None:
                raise ValueError("Attachment content is empty")
            part = MIMEBase(main_type, sub_type)
            part.set_payload(attachment_content)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{attachment_filename}"')
            msg.attach(part)

        return send_msg(msg)
    except smtplib.SMTPException as e:
        print(f"[EMAIL SMTP ERROR] Failed to send to {recipient_email}: {e}")
        return False, f"SMTP error sending to {recipient_email}: {e}"
    except Exception as e:
        print(f"[EMAIL ERROR] Send failed to {recipient_email}: {e}")
        try:
            msg = build_message()
            return send_msg(msg)
        except Exception as e2:
            print(f"[EMAIL ERROR] Fallback also failed to {recipient_email}: {e2}")
            return False, f"Failed to send email to {recipient_email}: {str(e2)}"


def send_text_message(recipient_phone, body):
    normalized_recipient = normalize_phone_number(recipient_phone)
    if not normalized_recipient:
        return False, "The recipient phone number is invalid."

    if SMS_PROVIDER == "generic_api":
        return _send_text_generic_api(normalized_recipient, body)

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return _send_text_twilio(normalized_recipient, body)

    return False, "No SMS provider is configured. Configure SMS_PROVIDER=generic_api or Twilio credentials."


def _send_text_twilio(normalized_recipient, body):
    if not TWILIO_FROM_NUMBER and not TWILIO_MESSAGING_SERVICE_SID:
        return False, "Twilio From Number or Messaging Service SID is not configured."

    payload = {
        "To": normalized_recipient,
        "Body": body,
    }
    if TWILIO_MESSAGING_SERVICE_SID:
        payload["MessagingServiceSid"] = TWILIO_MESSAGING_SERVICE_SID
    else:
        normalized_sender = normalize_phone_number(TWILIO_FROM_NUMBER)
        if not normalized_sender:
            return False, "Twilio From Number is invalid."
        payload["From"] = normalized_sender

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth_token = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")
    request_data = urllib.parse.urlencode(payload).encode("utf-8")
    request_obj = urllib.request.Request(url, data=request_data, method="POST")
    request_obj.add_header("Authorization", f"Basic {base64.b64encode(auth_token).decode('ascii')}")
    request_obj.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            return 200 <= response.status < 300, "SMS sent successfully."
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print(f"[SMS ERROR] Twilio returned {e.code}: {error_body}")
        return False, twilio_error_message(error_body)
    except Exception as e:
        print(f"[SMS ERROR] Failed to send SMS to {normalized_recipient}: {e}")
        return False, "Failed to send SMS. Check network and SMS configuration."


def _send_text_generic_api(normalized_recipient, body):
    if not SMS_API_URL or not SMS_API_KEY:
        return False, "SMS_API_URL and SMS_API_KEY must be configured for generic API provider."

    payload = {
        "to": normalized_recipient,
        "message": body,
        "sender_id": SMS_SENDER_ID or "",
    }

    headers = {
        "Authorization": f"Bearer {SMS_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(SMS_API_URL, json=payload, headers=headers, timeout=20)
        success = response.ok or 200 <= response.status_code < 300
        if success:
            return True, "SMS sent successfully."
        return False, f"SMS provider rejected the message: {response.status_code} {response.text}"
    except requests.exceptions.RequestException as e:
        print(f"[SMS ERROR] Failed to send SMS to {normalized_recipient}: {e}")
        return False, "Failed to send SMS. Check network and SMS API configuration."


def build_whatsapp_url(recipient_phone, message):
    normalized_phone = normalize_phone_number(recipient_phone)
    if not normalized_phone:
        return None
    digits = normalized_phone[1:]
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{digits}?text={encoded_message}"


def render_whatsapp_open_page(whatsapp_url, document_url=None):
    return render_template_string(
        """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="0; url={{ whatsapp_url }}">
    <title>Opening WhatsApp</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f8fafc;
            color: #111827;
            display: grid;
            min-height: 100vh;
            place-items: center;
            margin: 0;
        }
        main {
            width: min(480px, calc(100vw - 32px));
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }
        a {
            display: inline-block;
            margin-top: 12px;
            padding: 10px 14px;
            border-radius: 6px;
            background: #16a34a;
            color: white;
            text-decoration: none;
            font-weight: 700;
        }
        .secondary {
            background: #2563eb;
            margin-left: 8px;
        }
        p {
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <main>
        <h1>Opening WhatsApp</h1>
        <p>If WhatsApp does not open automatically, use the button below.</p>
        <a href="{{ whatsapp_url }}">Open WhatsApp</a>
        {% if document_url %}
        <a href="{{ document_url }}/view">View Grade Report</a>
        <a href="{{ document_url }}" class="secondary">Download Grade Report</a>
        {% endif %}
    </main>
    <script>
        window.location.href = {{ whatsapp_url|tojson }};
    </script>
</body>
</html>""",
        whatsapp_url=whatsapp_url,
        document_url=document_url,
    )


def save_temp_file(content, extension="csv"):
    """Save content to a secure temporary file and return download token"""
    file_id = str(uuid.uuid4())
    filename = f"grade_report_{file_id}.{extension}"
    file_path = os.path.join(TEMP_FILES_DIR, filename)

    if isinstance(content, bytes):
        with open(file_path, 'wb') as f:
            f.write(content)
    else:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return file_id, filename


def get_student_report_row(student_id, school_id, term=None):
    """Fetch student report metadata safely even when optional columns are missing."""
    available_columns = has_table_columns(
        "student_reports",
        {"teacher_remarks", "head_remarks", "attendance_present", "attendance_total", "conduct", "promoted_to", "signature", "interest", "position", "class_size", "reopening_date", "term"},
    )

    selected_columns = [
        "teacher_remarks",
        "head_remarks",
        "attendance_present",
        "attendance_total",
        "conduct",
        "promoted_to",
        "signature",
        "interest",
    ]
    if "position" in available_columns:
        selected_columns.append("position")
    if "class_size" in available_columns:
        selected_columns.append("class_size")
    if "reopening_date" in available_columns:
        selected_columns.append("reopening_date")
    if "term" in available_columns:
        selected_columns.append("term")

    select_columns = ", ".join(selected_columns)
    if term:
        report = query_db(
            f"SELECT {select_columns} FROM student_reports WHERE student_id = ? AND school_id = ? AND term = ?",
            (student_id, school_id, term),
            one=True,
        )
        if report:
            fallback_report = query_db(
                f"SELECT {select_columns} FROM student_reports WHERE student_id = ? AND school_id = ? AND term != ? ORDER BY id DESC LIMIT 1",
                (student_id, school_id, term),
                one=True,
            )
            if fallback_report:
                merged_report = dict(report)
                for column in selected_columns:
                    current_value = merged_report.get(column)
                    fallback_value = fallback_report.get(column)
                    if (current_value is None or current_value == "" or
                            (column in {"attendance_present", "attendance_total"} and current_value == 0 and fallback_value not in (None, "", 0))):
                        if fallback_value not in (None, ""):
                            merged_report[column] = fallback_value
                return merged_report
            return report

    return query_db(
        f"SELECT {select_columns} FROM student_reports WHERE student_id = ? AND school_id = ? ORDER BY id DESC LIMIT 1",
        (student_id, school_id),
        one=True,
    )


def build_grade_report_document(student, school_name, sender_name, grades_data, teacher_remarks, term, attendance_present, attendance_total, conduct="", promoted_to="", signature="", interest="", class_test_weight=0.20, midterm_exam_weight=0.20, class_score_weight=0.10, final_exam_weight=0.50, class_size="", position="", reopening_date="", head_remarks=""):
    """Build a Word-compatible HTML document for a student's grade report."""
    report_date = datetime.now().strftime("%d %B %Y")
    rows = []
    for grade_row in grades_data:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(grade_row['subject'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['grade'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['class_test'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['midterm_exam'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['class_score'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['final_exam'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['total_score'] or ''))}</td>"
            f"<td>{html.escape(str(grade_row['remark'] or ''))}</td>"
            "</tr>"
        )

    if not rows:
        rows.append("<tr><td colspan=\"8\">No grade records found for this student.</td></tr>")

    remarks_items = []
    if attendance_present is not None and attendance_total is not None:
        remarks_items.append(("Attendance", f"{attendance_present}/{attendance_total}"))
    if conduct:
        remarks_items.append(("Conduct", conduct))
    if promoted_to:
        remarks_items.append(("Promoted To", promoted_to))
    if interest:
        remarks_items.append(("Interest", interest))
    if signature:
        remarks_items.append(("Signature", signature))
    if teacher_remarks:
        remarks_items.append(("Teacher's Remarks", teacher_remarks))
    if head_remarks:
        remarks_items.append(("Headmaster's Remarks", head_remarks))

    remarks_rows = "".join(
        f"<tr><td class='label'>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>"
        for label, value in remarks_items
    )

    return f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Grade Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: "Segoe UI", Arial, sans-serif; color: #1f2937; font-size: 11px; line-height: 1.3; margin: 0; padding: 18px; }}
        .sheet {{ max-width: 780px; margin: 0 auto; }}
        .summary {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
        .summary td {{ border: 1px solid #111827; padding: 5px 8px; }}
        .summary .summary-title {{ background: #111827; color: #ffffff; font-size: 14px; font-weight: 700; text-align: center; text-transform: uppercase; }}
        .summary .label {{ width: 24%; background: #e5e7eb; color: #374151; font-size: 8px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; }}
        .summary .value {{ color: #111827; font-weight: 600; }}
        .details {{ width: 100%; border-collapse: collapse; margin: 0 0 10px; font-size: 10px; }}
        .details td {{ width: 25%; padding: 5px 8px; border: 1px solid #e5e7eb; }}
        .details .label {{ color: #64748b; font-size: 8px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; }}
        .details .value {{ color: #1f2937; font-weight: 600; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 10.5px; }}
        th {{ background: #111827; color: #ffffff; font-weight: 600; text-align: left; padding: 5px 8px; border: 1px solid #111827; }}
        td {{ padding: 4px 8px; border: 1px solid #d1d5db; }}
        tr:nth-child(even) {{ background: #f9fafb; }}
        .section-title {{ width: 100%; border-collapse: collapse; margin: 10px 0 0; }}
        .section-title td {{ padding: 4px 7px; background: #e5e7eb; border: 1px solid #cbd5e1; color: #111827; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }}
        .remarks {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
        .remarks td {{ border: 1px solid #d1d5db; padding: 5px 8px; vertical-align: top; }}
        .remarks td.label {{ width: 140px; font-weight: 600; background: #f3f4f6; color: #111827; }}
        .footer {{ margin-top: 14px; display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }}
        .footer-box {{ flex: 1; border-top: 1px solid #9ca3af; padding-top: 4px; font-size: 10px; color: #4b5563; min-height: 28px; }}
        .footer-label {{ font-weight: 700; color: #111827; margin-bottom: 2px; text-transform: uppercase; font-size: 9px; letter-spacing: 0.5px; }}
        @media print {{
            body {{ padding: 0; }}
            .sheet {{ max-width: none; }}
            .footer {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="sheet">
        <table class="summary"><tbody>
            <tr><td class="summary-title" colspan="4">Grade Report</td></tr>
            <tr><td class="label">School</td><td class="value" colspan="3">{html.escape(school_name)}</td></tr>
            <tr><td class="label">Report Period</td><td class="value" colspan="3">Academic Report &middot; {html.escape(str(term or 'All terms'))} &middot; {html.escape(report_date)}</td></tr>
            <tr><td class="label">Student Academic Record</td><td class="value" colspan="3">{html.escape(str(student['name']))}</td></tr>
            <tr><td class="label">Student No.</td><td class="value">{html.escape(str(student.get('student_number') or 'Not provided'))}</td><td class="label">Class</td><td class="value">{html.escape(str(student.get('grade') or ''))} {html.escape(str(student.get('section') or ''))}</td></tr>
            <tr><td class="label">Term</td><td class="value">{html.escape(str(term or 'All terms'))}</td><td class="label">Position</td><td class="value">{html.escape(str(position or 'Not recorded'))}</td></tr>
            <tr><td class="label">Class Size</td><td class="value">{html.escape(str(class_size or 'Not recorded'))}</td><td class="label">Teacher</td><td class="value">{html.escape(sender_name)}</td></tr>
        </tbody></table>

        {(remarks_rows) and f'''
        <table class="section-title"><tbody><tr><td>End of Term Report</td></tr></tbody></table>
        <table class="remarks">
            <tbody>
                {remarks_rows}
            </tbody>
        </table>
        ''' or ''}

        <table>
            <thead>
                <tr><th colspan="8">Academic Performance</th></tr>
                <tr>
                    <th>Subject</th>
                    <th>Grade</th>
                    <th>Class Test ({int(class_test_weight * 100)}%)</th>
                    <th>Midterm Exam ({int(midterm_exam_weight * 100)}%)</th>
                    <th>Class Score ({int(class_score_weight * 100)}%)</th>
                    <th>Final Exam ({int(final_exam_weight * 100)}%)</th>
                    <th>Total Score</th>
                    <th>Remarks</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>

        <table class="footer"><tbody><tr><td class="footer-box"><span class="footer-label">Teacher</span><br>{html.escape(sender_name)}</td></tr></tbody></table>
    </div>
</body>
</html>
"""


def cleanup_temp_files():
    """Clean up expired temporary files (run periodically via cron or scheduler)"""
    now = datetime.now()
    for filename in os.listdir(TEMP_FILES_DIR):
        file_path = os.path.join(TEMP_FILES_DIR, filename)
        try:
            # Check if file is older than 24 hours
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if now - file_time > timedelta(hours=24):
                os.remove(file_path)
        except:
            pass  # Continue if we can't read the file time


def send_whatsapp_api_message(data, access_token=None, phone_number_id=None):
    """Send message via WhatsApp Business API"""
    access_token = access_token or WHATSAPP_ACCESS_TOKEN
    phone_number_id = phone_number_id or WHATSAPP_PHONE_NUMBER_ID
    
    if not access_token or not phone_number_id:
        return False, "WhatsApp Business API not configured. Please set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID environment variables."
    
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return True, ""
    except requests.exceptions.RequestException as e:
        print(f"[WHATSAPP ERROR] {response.status_code if hasattr(e, 'response') else 'N/A'}: {response.text if hasattr(e, 'response') else str(e)}")
        return False, f"WhatsApp API error: {str(e)}"


def upload_whatsapp_media(file_bytes, filename, mime_type="application/pdf", access_token=None, phone_number_id=None):
    """Upload media file to WhatsApp Business API and return media_id"""
    access_token = access_token or WHATSAPP_ACCESS_TOKEN
    phone_number_id = phone_number_id or WHATSAPP_PHONE_NUMBER_ID

    if not access_token or not phone_number_id:
        return None, "WhatsApp Business API not configured."

    upload_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_number_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "file": (filename, file_bytes, mime_type),
    }
    data = {
        "messaging_product": "whatsapp",
    }

    try:
        response = requests.post(upload_url, headers=headers, files=files, data=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        media_id = result.get("id")
        if media_id:
            return media_id, ""
        return None, "Media upload response missing 'id'."
    except requests.exceptions.RequestException as e:
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        print(f"[WHATSAPP MEDIA ERROR] {body}")
        return None, f"WhatsApp media upload failed: {str(e)}"


def format_parent_notice(school_name, sender_name, student_name, parent_name, subject, body):
    notice_date = datetime.now().strftime("%d %B %Y")
    return "\n".join([
        f"*{school_name}*",
        "Official Parent Notice",
        "",
        f"Date: {notice_date}",
        f"Student: {student_name}",
        f"Parent/Guardian: {parent_name}",
        f"Admin/Staff: {sender_name}",
        "",
        f"*Subject: {subject}*",
        "",
        f"Dear {parent_name},",
        "",
        body,
        "",
        "Thank you.",
        "",
        "Signed,",
        sender_name,
        school_name,
    ])


def broadcast_announcement(school_id, sender_id, title, content, target_audience, delivery_method):
    results = {"email": 0, "whatsapp": 0, "text": 0, "app": 0, "errors": []}
    if delivery_method not in ("email", "whatsapp", "text", "all"):
        delivery_method = "app"

    audience_query = "SELECT id, name, email, role FROM users WHERE school_id = ? AND active = 1"
    audience_params = [school_id]
    if target_audience == "students":
        audience_query += " AND role = 'student'"
    elif target_audience == "teachers":
        audience_query += " AND role = 'teacher'"
    elif target_audience == "parents":
        audience_query += " AND role = 'parent'"

    recipients = query_db(audience_query, audience_params)
    sender_name = query_db("SELECT name FROM users WHERE id = ?", (sender_id,), one=True)
    sender_name = sender_name["name"] if sender_name else "School Administration"

    for recipient in recipients:
        if delivery_method in ("email", "all"):
            if recipient.get("email"):
                email_body = f"{content}\n\nFrom: {sender_name}"
                sent, error = send_email(recipient["email"], title, email_body, sender_name=sender_name)
                if sent:
                    results["email"] += 1
                else:
                    results["errors"].append(f"Email failed for {recipient['name']}: {error}")

        phone = None
        if recipient["role"] == "student":
            student = query_db(
                "SELECT parent_contact FROM students WHERE user_id = ? AND school_id = ? LIMIT 1",
                (recipient["id"], school_id), one=True
            )
            if student:
                phone = student.get("parent_contact")

        if phone:
            if delivery_method in ("whatsapp", "all"):
                data = {
                    "messaging_product": "whatsapp",
                    "to": normalize_phone_number(phone),
                    "type": "text",
                    "text": {"preview_url": False, "body": f"{title}\n\n{content}"},
                }
                send_whatsapp_api_message(data)
            elif delivery_method in ("text", "all"):
                send_text_message(phone, f"{content}\n\nFrom: {sender_name}")

    return results


# Database schema initialization


def _seed_library_samples(cur):
    try:
        cur.execute("SELECT COUNT(*) AS total FROM library_books WHERE school_id = 1 AND is_active = 1")
        row = cur.fetchone()
        if row and row.get("total", 0):
            return
        samples = [
            (1, "The Great Gatsby", "F. Scott Fitzgerald", "978-0743273565", "Fiction", "A classic American novel.", 2, "available"),
            (1, "A Brief History of Time", "Stephen Hawking", "978-0553380163", "Science", "A landmark overview of cosmology.", 1, "available"),
        ]
        cur.executemany(
            """
            INSERT INTO library_books
                (school_id, title, author, isbn, category, description, quantity, stock_status, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            samples,
        )
    except Exception:
        pass


def init_db():
    db = get_db()
    cur = db.cursor()
    
    # Check if we're using SQLite
    is_sqlite = hasattr(db, '_is_sqlite') and db._is_sqlite
    
    # SQLite doesn't have current_database()/current_schema()
    if not is_sqlite:
        try:
            cur.execute("SELECT current_database(), current_schema()")
            db_info = cur.fetchone()
            print(f"[init_db] current_database={db_info[0] if isinstance(db_info, (list, tuple)) else db_info.get('current_database')}, current_schema={db_info[1] if isinstance(db_info, (list, tuple)) else db_info.get('current_schema')}")
        except Exception:
            print(f"[init_db] Could not query database info")
    else:
        print(f"[init_db] Using SQLite database")
    
    # SQLite and PostgreSQL have different syntax for auto-increment columns
    serial_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
    timestamp_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if is_sqlite else "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
    
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS school_sections (
            id {serial_type},
            school_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS school_grade_levels (
            id {serial_type},
            school_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS school_subjects (
            id {serial_type},
            school_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS school_class_subjects (
            id {serial_type},
            school_id INTEGER NOT NULL,
            grade_level TEXT NOT NULL,
            section TEXT,
            subject TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS library_books (
            id {serial_type},
            school_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT,
            category TEXT,
            description TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            stock_status TEXT NOT NULL DEFAULT 'available',
            is_active INTEGER NOT NULL DEFAULT 1,
            file_path TEXT,
            audio_path TEXT,
            cover_image TEXT,
            created_at {timestamp_type},
            updated_at {timestamp_type},
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )
    school_id = None
    try:
        cur.execute("SELECT id FROM schools LIMIT 1")
        row = cur.fetchone()
        if row:
            school_id = row["id"] if isinstance(row, dict) else row[0]
    except Exception:
        pass
    _seed_library_samples(cur)
    _seed_default_subjects(cur, school_id)
    
    # Use helper function for database-agnostic column additions
    add_column_if_not_exists(db, "students", "parent_user_id", "INTEGER REFERENCES users(id)")
    add_column_if_not_exists(db, "schools", "passing_marks", "INTEGER DEFAULT 50")
    
    try:
        cur.execute("SELECT academic_term FROM schools LIMIT 1")
    except Exception:
        add_column_if_not_exists(db, "schools", "academic_term", "TEXT DEFAULT 'Term 1'")
    
    try:
        cur.execute("SELECT attendance_term_weeks FROM schools LIMIT 1")
    except Exception:
        add_column_if_not_exists(db, "schools", "attendance_term_weeks", "INTEGER DEFAULT 12")
    
    add_column_if_not_exists(db, "schools", "smtp_server", "TEXT DEFAULT 'smtp.gmail.com'")
    add_column_if_not_exists(db, "schools", "smtp_port", "INTEGER DEFAULT 587")
    add_column_if_not_exists(db, "schools", "smtp_email", "TEXT")
    add_column_if_not_exists(db, "schools", "smtp_password", "TEXT")
    add_column_if_not_exists(db, "schools", "sender_name", "TEXT DEFAULT 'School Administration'")
    add_column_if_not_exists(db, "schools", "twilio_account_sid", "TEXT")
    add_column_if_not_exists(db, "schools", "twilio_auth_token", "TEXT")
    add_column_if_not_exists(db, "schools", "twilio_from_number", "TEXT")
    add_column_if_not_exists(db, "schools", "twilio_messaging_service_sid", "TEXT")
    add_column_if_not_exists(db, "schools", "whatsapp_access_token", "TEXT")
    add_column_if_not_exists(db, "schools", "whatsapp_phone_number_id", "TEXT")
    add_column_if_not_exists(db, "schools", "school_email", "TEXT")
    add_column_if_not_exists(db, "schools", "school_phone", "TEXT")
    add_column_if_not_exists(db, "schools", "school_address", "TEXT")
    add_column_if_not_exists(db, "schools", "school_website", "TEXT")
    
    migrations = [
        ("student_reports", "signature", "TEXT"),
        ("student_reports", "position", "TEXT"),
        ("student_reports", "reopening_date", "TEXT"),
        ("student_reports", "class_size", "TEXT"),
        ("assignments", "subject", "TEXT"),
        ("assignments", "file_path", "TEXT"),
        ("assignments", "file_name", "TEXT"),
    ]
    for table, column, col_type in migrations:
        add_column_if_not_exists(db, table, column, col_type)
    try:
        cur.execute("SELECT session FROM attendances LIMIT 1")
    except Exception:
        try:
            cur.execute("ALTER TABLE attendances ADD COLUMN session TEXT")
            db.commit()
        except Exception:
            db.rollback()
            pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS week_number INTEGER")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS week_ending TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS strand TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS sub_strand TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS content_standard TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS indicator TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS performance_indicator TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS core_competencies TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS keywords TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS tlm TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS references TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS starter_activities TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS main_activities TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS formative_assessment TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS plenary_reflection TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS teacher_reflection TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS attachment_path TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS attachment_name TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS period_duration TEXT")
    except Exception:
        db.rollback()
        pass
    try:
        cur.execute("ALTER TABLE teaching_plans ADD COLUMN IF NOT EXISTS day_of_week TEXT")
    except Exception:
        db.rollback()
        pass
    db.commit()
    _seed_library_samples(cur)
    _seed_default_subjects(cur, school_id)
    db.commit()
    cur.close()


def _seed_default_subjects(cur, school_id):
    default_subjects = [
        "English Language",
        "Mathematics",
        "Science",
        "Our World and Our People (OWOP)",
        "History",
        "Creative Arts",
        "Religious and Moral Education (RME)",
        "Ghanaian Language and Culture",
        "Physical Education (PE)",
        "Computing",
        "French Language",
        "Career Technology",
        "Creative Arts and Design",
        "Social Studies",
        "Languages",
        "Physical and Health Education",
    ]
    cur.execute(
        "CREATE TABLE IF NOT EXISTS school_subjects (id SERIAL PRIMARY KEY, school_id INTEGER NOT NULL, name TEXT NOT NULL, FOREIGN KEY (school_id) REFERENCES schools(id))"
    )
    for subject in default_subjects:
        try:
            cur.execute(
                "INSERT INTO school_subjects (school_id, name) VALUES (?, ?)",
                (school_id, subject),
            )
        except Exception:
            pass


def query_db(query, args=(), one=False, commit=False):
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    cur.close()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
        g._database = None


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        user_role = session.get("role")
        # Normalize role to lowercase for case-insensitive comparison
        if user_role:
            user_role_normalized = user_role.lower()
        else:
            user_role_normalized = None
        # Debug: print role for troubleshooting
        print(f"DEBUG admin_required: user_role = {user_role!r}, normalized = {user_role_normalized!r}")
        # Allow both admin and superadmin roles
        if user_role_normalized not in ('admin', 'superadmin'):
            flash(f"Admin access required. Your role: {user_role}", "warning")
            return redirect(url_for("dashboard"))
        return view(**kwargs)
    return wrapped_view


def admin_or_teacher_required(view):
    """Allow admin, superadmin, and teacher roles."""
    @wraps(view)
    def wrapped_view(**kwargs):
        user_role = session.get("role")
        if user_role:
            user_role_normalized = user_role.lower()
        else:
            user_role_normalized = None
        if user_role_normalized not in ('admin', 'superadmin', 'teacher'):
            flash("Admin or teacher access required.", "warning")
            return redirect(url_for("dashboard"))
        return view(**kwargs)
    return wrapped_view


def has_privilege(privilege):
    if session.get("role") in (ROLE_ADMIN, ROLE_SUPERADMIN):
        return True
    privileges = session.get("privileges", "") or ""
    return privilege in [p.strip() for p in privileges.split(",") if p.strip()]


def teacher_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("role") in (ROLE_ADMIN, ROLE_TEACHER, ROLE_SUPERADMIN):
            return view(**kwargs)
        if not has_privilege("teacher_access"):
            flash("Teacher access required.", "warning")
            return redirect(url_for("dashboard"))
        return view(**kwargs)
    return wrapped_view


@app.route("/", methods=["GET", "POST"])
def login():
    schools = query_db("SELECT id, name, school_code FROM schools ORDER BY name")
    if request.method == "POST":
        school_code = request.form.get("school_code", "").strip()
        login_code = request.form.get("login_code", "").strip()

        # Block superadmin login from main portal - superadmins must use the separate superadmin app
        superadmin_user = query_db(
            "SELECT * FROM users WHERE role = ? AND login_code = ? AND active = 1",
            (ROLE_SUPERADMIN, login_code),
            one=True,
        )

        if superadmin_user:
            flash("Access Denied. Superadmin portal is on a different port.", "danger")
            return render_template("login.html", schools=schools, show_superadmin_link=False)

        # Regular users must have a valid school and matching login code
        if not school_code:
            flash("School code is required for this account.", "danger")
            return render_template("login.html", schools=schools, show_superadmin_link=True)

        user = query_db(
            "SELECT users.*, schools.name as school_name FROM users JOIN schools ON users.school_id = schools.id WHERE schools.school_code = ? AND users.login_code = ? AND users.active = 1",
            (school_code, login_code),
            one=True,
        )
        if not user:
            flash("Invalid school code or login code.", "danger")
            return render_template("login.html", schools=schools, show_superadmin_link=True)

        school_name = user["school_name"]
        school_code_val = school_code
        school_id = user["school_id"]

        school_active_row = query_db("SELECT active FROM schools WHERE id = ?", (school_id,), one=True)
        is_school_active = school_active_row["active"] if school_active_row else 1

        if user and check_password_hash(user["password_hash"], login_code):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            session["privileges"] = user["privileges"] or ""
            session["school_name"] = school_name
            session["school_code"] = school_code_val
            session["school_id"] = school_id
            if not is_school_active:
                flash("This school has been deactivated. All data is retained and can be reactivated by the superadmin.", "warning")
            else:
                flash(f"Welcome, {user['name']}!", "success")
            if user["role"] == ROLE_ADMIN:
                return redirect(url_for("admin_panel"))
            if user["role"] == ROLE_PARENT:
                return redirect(url_for("parent_dashboard"))
            return redirect(url_for("dashboard"))

        flash("Invalid school code or login code.", "danger")

    return render_template("login.html", schools=schools, show_superadmin_link=True)


@app.route("/parent_dashboard")
@login_required
def parent_dashboard():
    return render_template("parent_dashboard.html")


@app.route("/dashboard")
@login_required
def dashboard():
    student_count = query_db(
        "SELECT COUNT(*) AS total FROM students WHERE school_id = ?",
        (session.get("school_id"),),
        one=True,
    )["total"]
    user_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ?",
        (session.get("school_id"),),
        one=True,
    )["total"]
    
    teacher_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ? AND role = ? AND active = 1",
        (session.get("school_id"), ROLE_TEACHER),
        one=True,
    )["total"]
     
    # Only calculate financial metrics for admins and superadmins
    user_role = session.get("role")
    if user_role in ['admin', 'superadmin']:
        owing_count = query_db(
            "SELECT COUNT(DISTINCT student_id) AS total FROM fees WHERE school_id = ? AND is_paid != 1",
            (session.get("school_id"),),
            one=True,
        )["total"] or 0
        outstanding_total = query_db(
            "SELECT SUM(amount) AS total FROM fees WHERE school_id = ? AND is_paid != 1",
            (session.get("school_id"),),
            one=True,
        )["total"] or 0
    else:
        owing_count = 0
        outstanding_total = 0
     
    recent_students = query_db(
        "SELECT * FROM students WHERE school_id = ? AND active = 1 ORDER BY id DESC LIMIT 5",
        (session.get("school_id"),),
    )
    return render_template(
        "dashboard.html",
        student_count=student_count,
        user_count=user_count,
        teacher_count=teacher_count,
        owing_count=owing_count,
        outstanding_total=outstanding_total,
        recent_students=recent_students,
    )


@app.route("/teacher_dashboard")
@login_required
@teacher_required
def teacher_dashboard():
    school_id = session.get("school_id")
    teacher_id = session.get("user_id")
    
    # Get teacher's class assignments (grade, section, subject combinations)
    assignments = query_db(
        """
        SELECT ta.*, u.name AS teacher_name
        FROM teacher_assignments ta
        JOIN users u ON ta.teacher_id = u.id
        WHERE ta.teacher_id = ? AND ta.active = 1
        ORDER BY ta.grade, ta.section, ta.subject
        """,
        (teacher_id,),
    )
    
    # Get students in classes taught by this teacher
    my_students = query_db(
        """
        SELECT DISTINCT s.* FROM students s
        JOIN teacher_assignments ta ON s.grade = ta.grade AND (s.section = ta.section OR ta.section IS NULL OR ta.section = '')
        WHERE ta.teacher_id = ? AND s.school_id = ? AND s.active = 1
        ORDER BY s.name
        """,
        (teacher_id, school_id),
    )
    
    # Get assignments created by this teacher
    my_assignments = query_db(
        """
        SELECT a.* FROM assignments a
        WHERE a.assigned_by = ? AND a.is_active = 1
        ORDER BY a.due_date ASC
        """,
        (teacher_id,),
    )
    
    # Get upcoming (not yet due) assignments for activity tab
    upcoming_assignments = query_db(
        """
        SELECT a.* FROM assignments a
        WHERE a.assigned_by = ? AND a.is_active = 1 AND a.due_date >= date('now')
        ORDER BY a.due_date ASC
        LIMIT 6
        """,
        (teacher_id,),
    )
    
    # Get recent grades recorded by this teacher
    recent_grades = query_db(
        """
        SELECT g.*, s.name AS student_name, u.name AS recorder_name
        FROM grades g
        JOIN students s ON g.student_id = s.id
        JOIN users u ON g.recorded_by = u.id
        WHERE g.school_id = ? AND (g.recorded_by = ? OR EXISTS (
            SELECT 1 FROM teacher_assignments ta
            WHERE ta.teacher_id = ? AND ta.active = 1
            AND ta.subject = g.subject
            AND (ta.grade = s.grade OR ta.grade IS NULL OR ta.grade = '')
            AND (ta.section = s.section OR ta.section IS NULL OR ta.section = '')
        ))
        ORDER BY g.created_at DESC
        LIMIT 15
        """,
        (school_id, teacher_id, teacher_id),
    )
    
    # Calculate average grade percentage
    avg_grade = 0
    if recent_grades:
        total_pct = sum((g.get("score", 0) / g.get("max_score", 1) * 100) for g in recent_grades if g.get("max_score"))
        avg_grade = round(total_pct / len(recent_grades)) if recent_grades else 0
    
    # Count overdue assignments
    overdue_count = query_db(
        "SELECT COUNT(*) as count FROM assignments WHERE assigned_by = ? AND due_date < date('now') AND is_active = 1",
        (teacher_id,),
        one=True,
    )
    
    return render_template(
        "teacher_dashboard.html",
        my_students=my_students or [],
        my_assignments=my_assignments or [],
        upcoming_assignments=upcoming_assignments or [],
        recent_grades=recent_grades or [],
        assignments=assignments or [],
        avg_grade=avg_grade,
        overdue_count=overdue_count["count"] if overdue_count else 0,
    )


@app.route("/attendance")
@login_required
def attendance():
    from datetime import datetime, timedelta

    school_id = session.get("school_id")
    user_role = session.get("role")

    # Get filter parameters
    selected_grade = request.args.get("grade", "").strip()
    selected_section = request.args.get("section", "").strip()
    selected_term = request.args.get("term", "").strip()
    selected_month = request.args.get("month", "").strip()

    if user_role == ROLE_PARENT:
        base_query = "SELECT * FROM students WHERE school_id = ? AND active = 1 AND parent_user_id = ?"
        base_params = [school_id, session.get("user_id")]
    else:
        base_query = "SELECT * FROM students WHERE school_id = ? AND active = 1"
        base_params = [school_id]

    grade_levels = query_db(
        "SELECT DISTINCT grade FROM students WHERE school_id = ? AND grade IS NOT NULL AND grade != '' ORDER BY grade",
        (school_id,),
    )
    sections = query_db(
        "SELECT DISTINCT section FROM students WHERE school_id = ? AND section IS NOT NULL AND section != '' ORDER BY section",
        (school_id,),
    )
    
    # Also get custom grade levels and sections from settings
    custom_sections = []
    try:
        custom_sections = query_db(
            "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
    except Exception:
        pass
    custom_grades = []
    try:
        custom_grades = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,)
        )
    except Exception:
        pass
    
    # Add custom grades to grade_levels if not already present
    grade_names = [g["grade"] for g in grade_levels]
    for cg in custom_grades:
        if cg["name"] not in grade_names:
            grade_levels.append({"grade": cg["name"]})
    
    # Add custom sections to sections if not already present
    section_names = [s["section"] for s in sections]
    for cs in custom_sections:
        if cs["name"] not in section_names:
            sections.append({"section": cs["name"]})

    # Apply filters based on selected grade and section
    if selected_grade or selected_section:
        query = base_query
        params = base_params.copy()
        if selected_grade:
            query += " AND grade = ?"
            params.append(selected_grade)
        if selected_section:
            query += " AND section = ?"
            params.append(selected_section)
        query += " ORDER BY grade, section, name"
        students = query_db(query, tuple(params))
    else:
        students = query_db(base_query + " ORDER BY grade, section, name", tuple(base_params))

    today = datetime.now().date()

    def calculate_age(dob_str):
        if not dob_str:
            return ""
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        except ValueError:
            return ""
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age

    for student in students:
        student["age"] = calculate_age(student.get("date_of_birth"))

    week_start_param = request.args.get("week_start", "").strip()
    if not week_start_param and selected_month:
        try:
            selected_month_date = datetime.strptime(selected_month, "%Y-%m").date()
            week_start_param = (selected_month_date - timedelta(days=selected_month_date.weekday())).isoformat()
        except ValueError:
            selected_month = ""
    if week_start_param:
        try:
            week_start = datetime.strptime(week_start_param, "%Y-%m-%d").date()
        except ValueError:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)
    week_dates = [(week_start + timedelta(days=i)).isoformat() for i in range(5)]

    try:
        week_attendance_rows = query_db(
            "SELECT student_id, date, status, session FROM attendances WHERE school_id = ? AND date IN (?,?,?,?,?)",
            (school_id, *week_dates),
        )
        week_rows_have_session = True
    except Exception:
        week_rows_have_session = False
        week_attendance_rows = query_db(
            "SELECT student_id, date, status FROM attendances WHERE school_id = ? AND date IN (?,?,?,?,?)",
            (school_id, *week_dates),
        )

    week_attendance_index = {}
    for row in week_attendance_rows:
        week_attendance_index.setdefault(row["student_id"], {})[row["date"]] = row

    def is_present(student, date_str, session):
        entry = (week_attendance_index.get(student["id"]) or {}).get(date_str)
        if not entry:
            return False
        if week_rows_have_session and entry.get("session") in ("AM", "PM"):
            return entry["session"] == session and entry["status"] == "present"
        legacy = not week_rows_have_session or entry.get("session") is None
        return legacy and session == "AM" and entry["status"] == "present"

    try:
        term_attendance_rows = query_db(
            "SELECT student_id, date, status, session FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        term_rows_have_session = True
    except Exception:
        term_rows_have_session = False
        term_attendance_rows = query_db(
            "SELECT student_id, date, status FROM attendances WHERE school_id = ?",
            (school_id,),
        )

    try:
        school_settings = query_db("SELECT attendance_term_weeks FROM schools WHERE id = ?", (school_id,), one=True) or {}
    except Exception:
        school_settings = {}

    term_attendance_index = {}
    for row in term_attendance_rows:
        term_attendance_index.setdefault(row["student_id"], {})[row["date"]] = row

    def is_present_for_term(student, date_str, session):
        entry = (term_attendance_index.get(student["id"]) or {}).get(date_str)
        if not entry:
            return False
        if term_rows_have_session and entry.get("session") in ("AM", "PM"):
            return entry["session"] == session and entry["status"] == "present"
        legacy = not term_rows_have_session or entry.get("session") is None
        return legacy and session == "AM" and entry["status"] == "present"

    def week_present_count(student):
        count = 0
        for date_str in week_dates:
            if is_present(student, date_str, "AM"):
                count += 1
            if week_rows_have_session and is_present(student, date_str, "PM"):
                count += 1
        return count

    term_dates = sorted({row["date"] for row in term_attendance_rows})
    def term_present_count(student):
        count = 0
        for date_str in term_dates:
            if is_present_for_term(student, date_str, "AM") or (
                term_rows_have_session and is_present_for_term(student, date_str, "PM")
            ):
                count += 1
        return count

    term_weeks = school_settings.get("attendance_term_weeks") or 12
    term_total_slots = term_weeks * 5

    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    school_name = school["name"] if school else ""
    grade = (students[0]["grade"] if students else "") or ""
    section = (students[0]["section"] if students else "") or ""
    class_name = f"{grade} {section}".strip() if grade or section else "Class"
    academic_year = f"{today.year}/{today.year + 1}"
    school_term = ""
    try:
        school_term = (query_db("SELECT academic_term FROM schools WHERE id = ?", (school_id,), one=True) or {}).get("academic_term", "") or ""
    except Exception:
        school_term = ""
    term_options = ["Term 1", "Term 2", "Term 3"]
    selected_term = selected_term or school_term or "Term 1"
    term = selected_term
    try:
        datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        selected_month = week_start.strftime("%Y-%m")
    month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y")

    class_teacher = session.get("user_name", "")

    prev_week = (week_start - timedelta(days=7)).isoformat()
    next_week = (week_start + timedelta(days=7)).isoformat()
    today_week = (today - timedelta(days=today.weekday())).isoformat()
    prev_month = (week_start - timedelta(days=7)).strftime("%Y-%m")
    next_month = (week_start + timedelta(days=7)).strftime("%Y-%m")

    return render_template(
        "attendance.html",
        school_name=school_name,
        class_name=class_name,
        academic_year=academic_year,
        term=term,
        selected_month=selected_month,
        month_label=month_label,
        class_teacher=class_teacher,
        week_start=week_start.isoformat(),
        week_dates=week_dates,
        week_headers=[{"date": d, "label": datetime.strptime(d, "%Y-%m-%d").strftime("%a %d")} for d in week_dates],
        students=students,
        grades=grade_levels,
        sections=sections,
        term_options=term_options,
        prev_week=prev_week,
        next_week=next_week,
        today_week=today_week,
        prev_month=prev_month,
        next_month=next_month,
        is_present=is_present,
        week_present_count=week_present_count,
        term_present_count=term_present_count,
        term_total_slots=term_total_slots,
        term_weeks=term_weeks,
        term_dates=term_dates,
    )


@app.route("/attendance/settings", methods=["POST"])
@login_required
@teacher_required
def save_attendance_settings():
    term_weeks = request.form.get("term_weeks", type=int)
    if not term_weeks or not 1 <= term_weeks <= 52:
        flash("Term weeks must be between 1 and 52.", "error")
    else:
        query_db(
            "UPDATE schools SET attendance_term_weeks = ? WHERE id = ?",
            (term_weeks, session.get("school_id")),
            commit=True,
        )
        flash(f"Attendance term updated to {term_weeks} weeks ({term_weeks * 5} school days).", "success")

    return redirect(url_for(
        "attendance",
        week_start=request.form.get("week_start", ""),
        month=request.form.get("month", ""),
        grade=request.form.get("grade", ""),
        section=request.form.get("section", ""),
        term=request.form.get("term", ""),
    ))


@app.route("/attendance/download")
@login_required
def download_attendance():
    """Download the currently selected attendance week as a CSV file."""
    from datetime import datetime, timedelta

    school_id = session.get("school_id")
    selected_grade = request.args.get("grade", "").strip()
    selected_section = request.args.get("section", "").strip()
    week_start_value = request.args.get("week_start", "").strip()

    try:
        week_start = datetime.strptime(week_start_value, "%Y-%m-%d").date()
    except ValueError:
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())

    week_dates = [(week_start + timedelta(days=index)).isoformat() for index in range(5)]
    student_query = "SELECT id, name, student_number, grade, section, date_of_birth FROM students WHERE school_id = ? AND active = 1"
    student_params = [school_id]
    if session.get("role") == ROLE_PARENT:
        student_query += " AND parent_user_id = ?"
        student_params.append(session.get("user_id"))
    if selected_grade:
        student_query += " AND grade = ?"
        student_params.append(selected_grade)
    if selected_section:
        student_query += " AND section = ?"
        student_params.append(selected_section)
    student_query += " ORDER BY grade, section, name"
    students = query_db(student_query, tuple(student_params))

    try:
        attendance_rows = query_db(
            "SELECT student_id, date, status, session FROM attendances WHERE school_id = ? AND date IN (?,?,?,?,?)",
            (school_id, *week_dates),
        )
        rows_have_session = True
    except Exception:
        attendance_rows = query_db(
            "SELECT student_id, date, status FROM attendances WHERE school_id = ? AND date IN (?,?,?,?,?)",
            (school_id, *week_dates),
        )
        rows_have_session = False

    try:
        term_rows = query_db(
            "SELECT student_id, date, status, session FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        term_rows_have_session = True
    except Exception:
        term_rows = query_db(
            "SELECT student_id, date, status FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        term_rows_have_session = False

    attendance_index = {(row["student_id"], row["date"], row.get("session")): row["status"] for row in attendance_rows}
    term_index = {(row["student_id"], row["date"], row.get("session")): row["status"] for row in term_rows}

    def marked_present(index, student_id, date_str, session_slot, has_session):
        if has_session:
            return index.get((student_id, date_str, session_slot)) == "present"
        return index.get((student_id, date_str, None)) == "present"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "S/N", "Student Name", "Student Number", "Grade", "Section",
        *[datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %d %b") for date_str in week_dates],
        "Weekly Present", "Term Present",
    ])
    for index, student in enumerate(students, start=1):
        weekly_total = 0
        day_values = []
        for date_str in week_dates:
            day_present = marked_present(attendance_index, student["id"], date_str, "AM", rows_have_session)
            if rows_have_session:
                day_present = day_present or marked_present(attendance_index, student["id"], date_str, "PM", rows_have_session)
            if day_present:
                weekly_total += 1
            day_values.append("Present" if day_present else "Not marked")

        term_total = sum(
            1 for (student_id, date_str, session_slot), status in term_index.items()
            if student_id == student["id"] and status == "present"
            and (term_rows_have_session or session_slot is None)
        )
        writer.writerow([
            index, student["name"], student.get("student_number") or "",
            student.get("grade") or "", student.get("section") or "",
            *day_values, weekly_total, term_total,
        ])

    filename_parts = ["attendance", week_start.isoformat()]
    if selected_grade:
        filename_parts.append(secure_filename(selected_grade))
    if selected_section:
        filename_parts.append(secure_filename(selected_section))
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={'_'.join(filename_parts)}.csv"},
    )


@app.route("/attendance/save", methods=["POST"])
@login_required
@teacher_required
def save_attendance():
    data = request.get_json() or {}
    attendance_entries = data.get("entries", [])
    school_id = session.get("school_id")
    user_id = session.get("user_id")
    saved = 0
    columns = ["student_id", "school_id", "date", "status", "recorded_by"]
    try:
        query_db("SELECT session FROM attendances LIMIT 0", commit=False)
        use_session = True
        columns.insert(5, "session")
    except Exception:
        use_session = False

    for entry in attendance_entries:
        student_id = entry.get("student_id")
        date_str = entry.get("date", "").strip()
        status = entry.get("status", "").strip().lower()
        session_slot = entry.get("session", "AM").upper()
        if not student_id or not date_str or status not in ("present", "absent"):
            continue
        delete_kwargs = (student_id, school_id, date_str)
        insert_values = (student_id, school_id, date_str, status, user_id)
        if use_session:
            delete_kwargs = delete_kwargs + (session_slot,)
            insert_values = insert_values + (session_slot,)

        query_db(
            f"DELETE FROM attendances WHERE student_id = ? AND school_id = ? AND date = ?{' AND session = ?' if use_session else ''}",
            delete_kwargs,
            commit=True,
        )

        placeholders = ",".join(["?"] * len(columns))
        query_db(
            f"INSERT INTO attendances ({', '.join(columns)}) VALUES ({placeholders})",
            insert_values,
            commit=True,
        )
        saved += 1
    return {"success": True, "saved": saved}


@app.route("/attendance/record", methods=["POST"])
@login_required
@teacher_required
def record_attendance():
    student_id = request.form.get("student_id")
    attendance_date = request.form.get("date", "").strip()
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()

    if not student_id or not attendance_date or status not in ("present", "absent"):
        flash("Please select a valid student, date, and status.", "warning")
        return redirect(url_for("attendance"))

    query_db(
        "DELETE FROM attendances WHERE student_id = ? AND school_id = ? AND date = ?",
        (student_id, session.get("school_id"), attendance_date),
        commit=True,
    )
    query_db(
        "INSERT INTO attendances (student_id, school_id, date, status, recorded_by) VALUES (?, ?, ?, ?, ?)",
        (student_id, session.get("school_id"), attendance_date, status, session.get("user_id")),
        commit=True,
    )
    flash("Attendance recorded successfully.", "success")
    return redirect(url_for("attendance"))


@app.route("/finance")
@login_required
@admin_required
def finance():
    students = query_db(
        "SELECT * FROM students WHERE school_id = ? AND active = 1 ORDER BY grade, section, name",
        (session.get("school_id"),),
    )
    fees = query_db(
        "SELECT f.*, s.name AS student_name, s.student_number FROM fees f "
        "JOIN students s ON f.student_id = s.id "
        "WHERE f.school_id = ? AND f.is_active = 1 ORDER BY f.due_date IS NULL, f.due_date ASC, f.created_at DESC",
        (session.get("school_id"),),
    )
    outstanding_total = query_db(
        "SELECT SUM(amount) AS total FROM fees WHERE school_id = ? AND is_active = 1 AND is_paid != 1",
        (session.get("school_id"),),
        one=True,
    )["total"] or 0
    return render_template("finance.html", students=students, fees=fees, outstanding_total=outstanding_total)


@app.route("/finance/delete/<int:fee_id>", methods=["POST"])
@login_required
@admin_required
def delete_fee(fee_id):
    fee = query_db("SELECT * FROM fees WHERE id = ?", (fee_id,), one=True)
    if not fee:
        flash("Fee not found.", "danger")
        return redirect(url_for("finance"))
    if session.get("role") != ROLE_SUPERADMIN and fee["school_id"] != session.get("school_id"):
        flash("You can only delete fees from your own school.", "warning")
        return redirect(url_for("finance"))
    query_db("UPDATE fees SET is_active = 0 WHERE id = ?", (fee_id,), commit=True)
    flash("Fee deleted successfully.", "success")
    return redirect(url_for("finance"))


@app.route("/finance/create_charge", methods=["POST"])
@login_required
@admin_required
def create_charge():
    student_id = request.form.get("student_id")
    fee_type = request.form.get("fee_type", "").strip()
    description = request.form.get("description", "").strip()
    amount_due = request.form.get("amount_due", "").strip()
    due_date = request.form.get("due_date", "").strip()

    if not student_id or not fee_type or not amount_due:
        flash("Student, fee type, and amount due are required.", "warning")
        return redirect(url_for("finance"))

    try:
        amount_due_value = float(amount_due)
    except ValueError:
        flash("Amount due must be numeric.", "warning")
        return redirect(url_for("finance"))

    # Combine fee type with description
    full_description = f"{fee_type}: {description}" if description else fee_type
    
    new_fee = query_db(
        "INSERT INTO fees (student_id, school_id, fee_type, amount, due_date, is_paid) VALUES (?, ?, ?, ?, ?, 0) RETURNING id",
        (student_id, session.get("school_id"), full_description, amount_due_value, due_date or None),
        one=True,
        commit=True,
    )
    fee_id = new_fee["id"]
    fee = query_db(
        "SELECT f.*, s.name AS student_name, s.parent_name, s.parent_email, s.parent_contact FROM fees f JOIN students s ON f.student_id = s.id WHERE f.id = ?",
        (fee_id,),
        one=True,
    )

    delivery_method = request.form.get("delivery_method", "app")
    if fee and delivery_method and delivery_method != "app":
        sender = query_db("SELECT name FROM users WHERE id = ?", (session.get("user_id"),), one=True)
        sender_name = sender["name"] if sender else "School Administration"
        school_name = session.get("school_name") or "Eureka School"
        parent_name = fee.get("parent_name") or "Parent"
        subject = f"Fee Notification: {full_description}"
        body = f"Dear {parent_name},\n\nThis is a billing notice for {fee['student_name']}.\nFee: {full_description}\nAmount: {amount_due_value} GHS\nDue Date: {due_date or 'Not set'}\n\nPlease make payment at the school office.\n\nBest regards,\n{sender_name}\n{school_name}"

        if delivery_method in ("email", "all"):
            if fee.get("parent_email"):
                send_email(fee["parent_email"], subject, body, sender_name=sender_name)

        if delivery_method in ("whatsapp", "all"):
            phone = fee.get("parent_contact")
            if phone:
                data = {
                    "messaging_product": "whatsapp",
                    "to": normalize_phone_number(phone),
                    "type": "text",
                    "text": {"preview_url": False, "body": f"*{subject}*\n\n{body}"},
                }
                send_whatsapp_api_message(data)

        if delivery_method in ("text", "all"):
            phone = fee.get("parent_contact")
            if phone:
                send_text_message(phone, f"{subject}\n\n{body}")

        if delivery_method in ("app", "all"):
            parent_user = query_db(
                "SELECT id FROM users WHERE school_id = ? AND role = 'parent' AND active = 1 LIMIT 1",
                (session.get("school_id"),),
                one=True,
            )
            if parent_user:
                query_db(
                    "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
                    (session.get("user_id"), parent_user["id"], session.get("school_id"), subject, body, "app"),
                    commit=True,
                )

    flash("Fee charge created successfully.", "success")
    return redirect(url_for("finance"))


@app.route("/finance/pay", methods=["POST"])
@login_required
@admin_required
def pay_fee():
    fee_id = request.form.get("fee_id")
    amount = request.form.get("amount", "").strip()

    if not fee_id or not amount:
        flash("Please select a fee and enter a payment amount.", "warning")
        return redirect(url_for("finance"))

    try:
        amount_value = float(amount)
    except ValueError:
        flash("Payment amount must be numeric.", "warning")
        return redirect(url_for("finance"))

    fee = query_db("SELECT * FROM fees WHERE id = ? AND school_id = ?", (fee_id, session.get("school_id")), one=True)
    if not fee:
        flash("Fee not found.", "danger")
        return redirect(url_for("finance"))

    query_db(
        "UPDATE fees SET is_paid = 1 WHERE id = ?",
        (fee_id,),
        commit=True,
    )
    query_db(
        "INSERT INTO fee_payments (fee_id, amount, recorded_by) VALUES (?, ?, ?)",
        (fee_id, amount_value, session.get("user_id")),
        commit=True,
    )
    flash("Payment recorded successfully.", "success")
    return redirect(url_for("finance"))


def _next_grade_level(school_id, current_grade):
    """Return the configured grade after current_grade, or increment numeric grades."""
    current = str(current_grade or "").strip()
    try:
        configured = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,),
        )
    except Exception:
        configured = []
    names = [row["name"] for row in configured if row.get("name")]
    if current in names:
        index = names.index(current)
        if index + 1 < len(names):
            return names[index + 1]

    match = re.search(r"(\d+)", current)
    if not match:
        return None
    next_number = str(int(match.group(1)) + 1)
    if current.lower().startswith("grade"):
        return f"Grade {next_number}"
    prefix = current[:match.start()].strip()
    return f"{prefix} {next_number}".strip()


@app.route("/grades/promote-term3", methods=["POST"])
@login_required
@teacher_required
def promote_term3():
    """Advance a completed Term 3 class and allocate students into A/B/C."""
    school_id = session.get("school_id")
    current_grade = request.form.get("grade", "").strip()
    current_section = request.form.get("section", "").strip()
    if not school_id or not current_grade:
        flash("Select a class before promoting students.", "warning")
        return redirect(url_for("grades"))

    next_grade = _next_grade_level(school_id, current_grade)
    if not next_grade:
        flash(f"No next grade is configured for {current_grade}.", "warning")
        return redirect(url_for("grades", grade=current_grade, section=current_section, term="Term 3"))

    student_query = "SELECT id, name, grade, section FROM students WHERE school_id = ? AND active = 1 AND grade = ?"
    args = [school_id, current_grade]
    if current_section:
        student_query += " AND section = ?"
        args.append(current_section)
    students = query_db(student_query, tuple(args))
    ranked = []
    for student in students:
        average_row = query_db(
            "SELECT AVG(total_score) AS average_score, COUNT(id) AS grade_count FROM grades WHERE student_id = ? AND school_id = ? AND term = ? AND total_score IS NOT NULL",
            (student["id"], school_id, "Term 3"), one=True
        )
        if average_row and average_row.get("grade_count", 0):
            ranked.append({
                "id": student["id"],
                "name": student["name"],
                "average": float(average_row["average_score"] or 0),
            })

    if not ranked:
        flash("No Term 3 grade records were found for this class.", "warning")
        return redirect(url_for("grades", grade=current_grade, section=current_section, term="Term 3"))

    ranked.sort(key=lambda item: (-item["average"], item["name"].lower()))
    total = len(ranked)
    for index, student in enumerate(ranked):
        section = ("A", "B", "C")[min((index * 3) // total, 2)]
        query_db(
            "UPDATE students SET grade = ?, section = ? WHERE id = ? AND school_id = ?",
            (next_grade, section, student["id"], school_id), commit=True
        )

    skipped = len(students) - len(ranked)
    flash(
        f"Term 3 promotion complete: {len(ranked)} students moved to {next_grade}. "
        f"Sections assigned by average: A highest, B middle, C lowest. Skipped without Term 3 grades: {skipped}.",
        "success",
    )
    return redirect(url_for("grades", grade=next_grade, term="Term 1"))


@app.route("/grades")
@login_required
def grades():
    school_id = session.get("school_id")
    user_role = session.get("role")
    
    if user_role == ROLE_PARENT:
        students_query = "SELECT * FROM students WHERE school_id = ? AND active = 1 AND parent_user_id = ?"
        students_params = [school_id, session.get("user_id")]
    else:
        students_query = "SELECT * FROM students WHERE school_id = ? AND active = 1"
        students_params = [school_id]
    
    # Get filter parameters
    selected_grade = request.args.get("grade", "").strip()
    selected_section = request.args.get("section", "").strip()
    selected_term = request.args.get("term", "").strip()
    
    # Get all sections and grade levels for filter dropdowns
    sections = query_db(
        "SELECT DISTINCT section FROM students WHERE school_id = ? AND section IS NOT NULL AND section != '' ORDER BY section",
        (school_id,),
    )

    # Get grade levels
    grade_levels = query_db(
        "SELECT DISTINCT grade FROM students WHERE school_id = ? AND grade IS NOT NULL AND grade != '' ORDER BY grade",
        (school_id,),
    )

    # Get custom sections from settings
    try:
        custom_sections = query_db(
            "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
    except Exception:
        custom_sections = []

    # Get custom grade levels from settings
    try:
        custom_grade_levels = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,)
        )
    except Exception:
        custom_grade_levels = []

    # Convert sections to list of strings (combine existing with custom)
    section_list = [s["section"] for s in sections]
    for cs in custom_sections:
        if cs["name"] not in section_list:
            section_list.append(cs["name"])

    # Convert grade_levels to list of strings (combine existing with custom)
    grade_level_list = [g["grade"] for g in grade_levels]
    for cg in custom_grade_levels:
        if cg["name"] not in grade_level_list:
            grade_level_list.append(cg["name"])
    
    if selected_grade:
        students_query += " AND grade = ?"
        students_params.append(selected_grade)
    if selected_section:
        students_query += " AND section = ?"
        students_params.append(selected_section)
    
    students_query += " ORDER BY grade, section, name"
    students = query_db(students_query, tuple(students_params))
    
    # Get subjects from school_subjects table (configured subjects only)
    school_subjects_for_options = []
    try:
        school_subjects_for_options = query_db(
            "SELECT name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
    except Exception:
        pass
    
    # Build subject options list - only from school_subjects
    subject_options = []
    for row in school_subjects_for_options:
        if row["name"] and row["name"] not in subject_options:
            subject_options.append(row["name"])

    # Build class-specific subject map (grade -> list of subjects)
    class_subjects_by_grade = {}
    if selected_grade:
        try:
            if selected_section:
                class_specific_subjects = query_db(
                    "SELECT subject FROM school_class_subjects WHERE school_id = ? AND grade_level = ? AND section = ? ORDER BY subject",
                    (school_id, selected_grade, selected_section)
                )
                if class_specific_subjects:
                    class_subjects_by_grade[selected_grade] = [r["subject"] for r in class_specific_subjects]
                else:
                    class_specific_subjects = query_db(
                        "SELECT subject FROM school_class_subjects WHERE school_id = ? AND grade_level = ? AND section IS NULL ORDER BY subject",
                        (school_id, selected_grade)
                    )
                    if class_specific_subjects:
                        class_subjects_by_grade[selected_grade] = [r["subject"] for r in class_specific_subjects]
            else:
                class_specific_subjects = query_db(
                    "SELECT subject FROM school_class_subjects WHERE school_id = ? AND grade_level = ? ORDER BY subject",
                    (school_id, selected_grade)
                )
                if class_specific_subjects:
                    class_subjects_by_grade[selected_grade] = [r["subject"] for r in class_specific_subjects]
        except Exception:
            pass
    else:
        try:
            all_class_subjects = query_db(
                "SELECT grade_level, subject FROM school_class_subjects WHERE school_id = ? ORDER BY grade_level, subject",
                (school_id,)
            )
            for row in all_class_subjects:
                grade = row["grade_level"]
                if grade not in class_subjects_by_grade:
                    class_subjects_by_grade[grade] = []
                if row["subject"] not in class_subjects_by_grade[grade]:
                    class_subjects_by_grade[grade].append(row["subject"])
        except Exception:
            pass
    
    # Get school grading weights
    school_weights = query_db(
        "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight FROM schools WHERE id = ?",
        (school_id,), one=True
    )
    if school_weights:
        class_test_weight = school_weights["class_test_weight"] or 0.20
        midterm_exam_weight = school_weights["midterm_exam_weight"] or 0.20
        class_score_weight = school_weights["class_score_weight"] or 0.10
        final_exam_weight = school_weights["final_exam_weight"] or 0.50
    else:
        class_test_weight = 0.20
        midterm_exam_weight = 0.20
        class_score_weight = 0.10
        final_exam_weight = 0.50

    school = query_db(
        "SELECT name, whatsapp_access_token, whatsapp_phone_number_id FROM schools WHERE id = ?",
        (school_id,), one=True
    )
    school_name = school["name"] if school else "School"

    term_options = ["Term 1", "Term 2", "Term 3"]
    
    # Get current grades for each student by subject (filtered by term if selected)
    grades_query = "SELECT student_id, subject, grade, class_test, midterm_exam, class_score, final_exam, total_score, remark, term FROM grades WHERE school_id = ?"
    grades_params = [school_id]
    if selected_term:
        grades_query += " AND term = ?"
        grades_params.append(selected_term)
    
    student_grades = query_db(grades_query, tuple(grades_params))

    try:
        attendance_rows = query_db(
            "SELECT student_id, date, status, session FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        attendance_has_session = True
    except Exception:
        attendance_rows = query_db(
            "SELECT student_id, date, status FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        attendance_has_session = False
    attendance_dates_by_student = {}
    for row in attendance_rows:
        if row["status"] == "present":
            attendance_dates_by_student.setdefault(row["student_id"], set()).add(row["date"])
    attendance_settings = query_db(
        "SELECT attendance_term_weeks FROM schools WHERE id = ?",
        (school_id,), one=True,
    ) or {}
    attendance_term_weeks = attendance_settings.get("attendance_term_weeks") or 12
    attendance_total = attendance_term_weeks * 5
    
    # Organize grades by student
    grades_by_student = {}
    for g in student_grades:
        if g["student_id"] not in grades_by_student:
            grades_by_student[g["student_id"]] = {}
        grades_by_student[g["student_id"]][g["subject"]] = g
    
    # Convert students to list of dicts and add grades
    students_list = []
    for student in students:
        student_dict = dict(student)
        student_dict["grades"] = grades_by_student.get(student["id"], {})
        student_dict["attendance_present"] = len(attendance_dates_by_student.get(student["id"], set()))
        student_dict["attendance_total"] = attendance_total
        if selected_term:
            report = query_db(
                "SELECT head_remarks, teacher_remarks, interest, conduct, signature FROM student_reports WHERE student_id = ? AND school_id = ? AND term = ?",
                (student["id"], school_id, selected_term), one=True
            )
            student_dict["head_remarks"] = report["head_remarks"] if report else None
            student_dict["teacher_remarks"] = report["teacher_remarks"] if report else None
            student_dict["interest"] = report["interest"] if report else None
            student_dict["conduct"] = report["conduct"] if report else None
            student_dict["signature"] = report["signature"] if report else None
        else:
            student_dict["head_remarks"] = None
            student_dict["teacher_remarks"] = None
            student_dict["interest"] = None
            student_dict["conduct"] = None
            student_dict["signature"] = None
        students_list.append(student_dict)
    students = students_list
    
    # Get grade summaries for ranking
    grade_query = (
        "SELECT s.id, s.name, s.student_number, s.grade, s.section, "
        "COUNT(g.id) AS grade_count "
        "FROM students s "
        "LEFT JOIN grades g ON s.id = g.student_id AND g.school_id = ? "
        "WHERE s.school_id = ? GROUP BY s.id ORDER BY grade_count DESC, s.name"
    )
    grades_summary = query_db(grade_query, (school_id, school_id))

    grade_summaries = []
    for grade in grades_summary:
        grade_summaries.append({
            "id": grade["id"],
            "name": grade["name"],
            "student_number": grade["student_number"],
            "grade_level": grade["grade"],
            "section": grade["section"],
            "grade_count": grade["grade_count"],
            "position": None,
        })

    selected_student = None
    selected_student_id = request.args.get("student_id", "").strip()
    if selected_student_id:
        try:
            selected_student_id = int(selected_student_id)
        except ValueError:
            selected_student_id = None
    
    if selected_student_id is not None:
        selected_student = next((s for s in students if s["id"] == selected_student_id), None)
    
    student_report_subjects = []
    if selected_student:
        for subject in sorted(selected_student["grades"].keys()):
             grade_data = selected_student["grades"][subject]
             student_report_subjects.append({
                 "subject": subject,
                 "class_test": grade_data.get("class_test") if isinstance(grade_data, dict) else None,
                 "midterm_exam": grade_data.get("midterm_exam") if isinstance(grade_data, dict) else None,
                 "class_score": grade_data.get("class_score") if isinstance(grade_data, dict) else None,
                 "final_exam": grade_data.get("final_exam") if isinstance(grade_data, dict) else None,
                 "total_score": grade_data.get("total_score") if isinstance(grade_data, dict) else None,
                 "grade": grade_data.get("grade") if isinstance(grade_data, dict) else grade_data,
                 "remark": grade_data.get("remark") if isinstance(grade_data, dict) else None
             })

    # Load report metadata for the selected student and term
    attendance_present = 0
    attendance_total = attendance_total
    promoted_to = None
    conduct = None
    interest = None
    teacher_remarks = None
    head_remarks = None
    signature = ""
    position = ""
    class_size = ""
    reopening_date = ""
    if selected_student_id and selected_term:
        report_data = query_db(
            "SELECT * FROM student_reports WHERE student_id = ? AND school_id = ? AND term = ?",
            (selected_student_id, school_id, selected_term), one=True
        )
        if report_data:
            promoted_to = report_data.get("promoted_to")
            conduct = report_data.get("conduct")
            interest = report_data.get("interest")
            teacher_remarks = report_data.get("teacher_remarks")
            head_remarks = report_data.get("head_remarks")

    if selected_student:
        attendance_present = selected_student.get("attendance_present", 0)

    # Calculate report total
    report_total = sum(
        item["total_score"] for item in student_report_subjects if isinstance(item["total_score"], (int, float))
    ) if student_report_subjects else ""

    academic_year = f"{datetime.now().year}/{datetime.now().year + 1}"
    closing_date = datetime.now().strftime("%d %B %Y")
    reopening_date_display = (datetime.now() + timedelta(days=60)).strftime("%d %B %Y")

    rank = 0
    last_count = None
    class_rank_position = 0
    for student in grade_summaries:
        if student["grade_count"] > 0:
            rank += 1
            if last_count is None or student["grade_count"] != last_count:
                rank_position = rank
                last_count = student["grade_count"]
            student["position"] = rank_position
        else:
            student["position"] = "-"

    if selected_student_id:
        try:
            selected_student_id = int(selected_student_id)
        except ValueError:
            selected_student_id = students[0]["id"] if students else None
    else:
        selected_student_id = students[0]["id"] if students else None

    students_with_grades = [row for row in grade_summaries if row["grade_count"] > 0]
    class_average = (
        round(sum(row["grade_count"] for row in students_with_grades) / len(students_with_grades), 2)
        if students_with_grades
        else None
    )
    top_students = students_with_grades[:5]

    recent_query = (
        "SELECT g.*, s.name AS student_name, u.name AS recorder_name FROM grades g "
        "JOIN students s ON g.student_id = s.id "
        "JOIN users u ON g.recorded_by = u.id "
        "WHERE g.school_id = ? "
        "ORDER BY g.created_at DESC LIMIT 15"
    )
    recent_grades = query_db(recent_query, (school_id,))

    return render_template(
        "grades.html",
        students=students,
        subjects=subject_options,
        sections=section_list,
        grade_levels=grade_level_list,
        selected_grade=selected_grade,
        selected_section=selected_section,
        selected_term=selected_term,
        selected_student_id=selected_student_id,
        selected_student=selected_student,
        student_report_subjects=student_report_subjects,
        grade_summaries=grade_summaries,
        class_average=class_average,
        top_students=top_students,
        academic_year=academic_year,
        closing_date=closing_date,
        reopening_date=reopening_date,
        report_total=report_total,
        recent_grades=recent_grades,
        term_options=term_options,
        attendance_present=attendance_present,
        attendance_total=attendance_total,
        promoted_to=promoted_to,
        conduct=conduct,
        interest=interest,
        teacher_remarks=teacher_remarks,
        head_remarks=head_remarks,
        signature=signature,
        position=position,
        class_size=class_size,
        school_name=school_name,
        class_test_weight=class_test_weight,
        midterm_exam_weight=midterm_exam_weight,
        class_score_weight=class_score_weight,
        final_exam_weight=final_exam_weight,
        class_subjects_by_grade=class_subjects_by_grade,
    )


@app.route("/messages")
@login_required
def messages():
    # Determine recipients based on user role
    user_role = session.get("role")
    if user_role == "parent":
        # Parents should not see superadmin in the recipient list
        recipients = query_db(
            "SELECT id, name, role FROM users WHERE school_id = ? AND active = 1 AND role != 'superadmin' ORDER BY role, name",
            (session.get("school_id"),),
        )
    else:
        recipients = query_db(
            "SELECT id, name, role FROM users WHERE school_id = ? AND active = 1 ORDER BY role, name",
            (session.get("school_id"),),
        )
    students = query_db(
        """
        SELECT id, name, student_number, parent_name, parent_email, parent_contact
        FROM students
        WHERE school_id = ? AND active = 1
        ORDER BY name
        """,
        (session.get("school_id"),),
    )
    messages = query_db(
        "SELECT m.*, u.name AS sender_name, "
        "COALESCE(m.external_recipient_name, r.name) AS recipient_name FROM messages m "
        "JOIN users u ON m.sender_id = u.id "
        "LEFT JOIN users r ON m.recipient_id = r.id "
        "WHERE m.school_id = ? AND m.is_active = 1 AND (m.sender_id = ? OR m.recipient_id = ?) "
        "ORDER BY m.created_at DESC",
        (session.get("school_id"), session.get("user_id"), session.get("user_id")),
    )
    unread_count = query_db(
        "SELECT COUNT(*) AS total FROM messages WHERE school_id = ? AND is_active = 1 AND recipient_id = ? AND read_at IS NULL",
        (session.get("school_id"), session.get("user_id")),
        one=True,
    )["total"]
    return render_template(
        "messages.html",
        recipients=recipients,
        students=students,
        messages=messages,
        unread_count=unread_count,
    )


@app.route("/messages/send", methods=["POST"])
@login_required
def send_message():
    recipient_type = request.form.get("recipient_type", "user")
    recipient_id = request.form.get("recipient_id")
    student_id = request.form.get("student_id")
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    delivery_method = request.form.get("delivery_method", "app")

    if not subject or not body:
        flash("Subject and message body are required.", "warning")
        return redirect(url_for("messages"))
    
    sender = query_db("SELECT name FROM users WHERE id = ?", (session.get("user_id"),), one=True)
    sender_name = sender["name"] if sender else "School Staff"
    school_name = session.get("school_name") or "School Administration"

    if recipient_type == "student_parent":
        student = query_db(
            """
            SELECT id, name, parent_name, parent_email, parent_contact
            FROM students
            WHERE id = ? AND school_id = ? AND active = 1
            """,
            (student_id, session.get("school_id")),
            one=True,
        )
        if not student:
            flash("Please select a valid student.", "warning")
            return redirect(url_for("messages"))
        if delivery_method not in ("email", "text", "whatsapp"):
            flash("Parent messages can be sent by email, text message, or WhatsApp.", "warning")
            return redirect(url_for("messages"))

        parent_name = student["parent_name"] or f"Parent of {student['name']}"
        recipient_name = f"{parent_name} ({student['name']})"
        parent_email = student["parent_email"]
        parent_phone = student["parent_contact"]
        formatted_body = format_parent_notice(
            school_name,
            sender_name,
            student["name"],
            parent_name,
            subject,
            body,
        )

        if delivery_method == "email":
            if not parent_email:
                flash("This student does not have a parent email address on file.", "warning")
                return redirect(url_for("messages"))
            email_sent, email_error = send_email(
                parent_email,
                subject,
                formatted_body,
                sender_name=f"{sender_name} (via Eureka)",
            )
            if not email_sent:
                flash(email_error or "Failed to send email. Please check email configuration.", "danger")
                return redirect(url_for("messages"))
        elif delivery_method == "text":
            if not parent_phone:
                flash("This student does not have a parent phone number on file.", "warning")
                return redirect(url_for("messages"))
            sms_sent, sms_message = send_text_message(parent_phone, formatted_body)
            if not sms_sent:
                flash(sms_message, "danger")
                return redirect(url_for("messages"))
        else:
            if not parent_phone:
                flash("This student does not have a parent phone number on file.", "warning")
                return redirect(url_for("messages"))
            whatsapp_url = build_whatsapp_url(parent_phone, formatted_body)
            if not whatsapp_url:
                flash("This student's parent phone number is invalid.", "warning")
                return redirect(url_for("messages"))

        query_db(
            """
            INSERT INTO messages (
                sender_id, recipient_id, school_id, subject, body, read_at, delivery_method,
                student_id, external_recipient_name, external_recipient_email, external_recipient_phone
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
            """,
            (
                session.get("user_id"),
                session.get("user_id"),
                session.get("school_id"),
                subject,
                formatted_body,
                delivery_method,
                student["id"],
                recipient_name,
                parent_email,
                parent_phone,
            ),
            commit=True,
        )
        if delivery_method == "email":
            flash(f"Message sent by email to {recipient_name}.", "success")
        elif delivery_method == "whatsapp":
            flash(f"Opening WhatsApp message for {recipient_name}.", "success")
            return redirect(whatsapp_url)
        else:
            flash(f"Text message sent to {recipient_name}.", "success")
        return redirect(url_for("messages"))

    if not recipient_id:
        flash("Recipient, subject, and message body are required.", "warning")
        return redirect(url_for("messages"))
    
    if delivery_method == "email":
        # Send via email
        recipient = query_db("SELECT email FROM users WHERE id = ?", (recipient_id,), one=True)
        if not recipient or not recipient["email"]:
            flash("Recipient does not have an email address on file.", "warning")
            return redirect(url_for("messages"))
        
        email_sent, email_error = send_email(
            recipient["email"],
            subject,
            body,
            sender_name=f"{sender_name} (via Eureka)"
        )
        
        if email_sent:
            # Still create app message record for history
            query_db(
                "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
                (session.get("user_id"), recipient_id, session.get("school_id"), subject, body, "email"),
                commit=True,
            )
            flash(f"Message sent via email to recipient.", "success")
        else:
            flash(email_error or "Failed to send email. Please check email configuration.", "danger")
    else:
        # Send via app
        query_db(
            "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (session.get("user_id"), recipient_id, session.get("school_id"), subject, body, "app"),
            commit=True,
        )
        flash("Message sent successfully via app.", "success")
    
    return redirect(url_for("messages"))


@app.route("/messages/read/<int:message_id>")
@login_required
def read_message(message_id):
    message = query_db(
        "SELECT m.*, u.name AS sender_name, "
        "COALESCE(m.external_recipient_name, r.name) AS recipient_name FROM messages m "
        "JOIN users u ON m.sender_id = u.id "
        "LEFT JOIN users r ON m.recipient_id = r.id "
        "WHERE m.id = ? AND m.school_id = ?",
        (message_id, session.get("school_id")),
        one=True,
    )
    if not message or not message["is_active"] or (message["sender_id"] != session.get("user_id") and message["recipient_id"] != session.get("user_id")):
        flash("Message not found.", "danger")
        return redirect(url_for("messages"))

    if message["recipient_id"] == session.get("user_id") and message["read_at"] is None:
        query_db(
            "UPDATE messages SET read_at = CURRENT_TIMESTAMP WHERE id = ?",
            (message_id,),
            commit=True,
        )

    return render_template("message_detail.html", message=message)


@app.route("/messages/delete/<int:message_id>", methods=["POST"])
@login_required
def delete_message(message_id):
    message = query_db(
        "SELECT * FROM messages WHERE id = ? AND school_id = ? AND is_active = 1",
        (message_id, session.get("school_id")),
        one=True,
    )
    if not message:
        flash("Message not found.", "danger")
        return redirect(url_for("messages"))
    if message["sender_id"] != session.get("user_id") and message["recipient_id"] != session.get("user_id"):
        flash("You can only delete messages you sent or received.", "warning")
        return redirect(url_for("messages"))
    query_db("UPDATE messages SET is_active = 0 WHERE id = ?", (message_id,), commit=True)
    flash("Message deleted.", "success")
    return redirect(url_for("messages"))

@app.route("/grades/record", methods=["POST"])
@login_required
@teacher_required
def record_grade():
    # Check if this is a bulk grade submission (from subject/section tabs)
    # Bulk submissions will have form data like: grade_1, grade_2, etc. for each student
    bulk_grades = {}
    for key in request.form:
        if key.startswith('grade_') and key != 'grade':
            try:
                student_id = int(key.split('_')[1])
                grade_value = request.form[key].strip()
                if grade_value:  # Only process if grade is provided
                    bulk_grades[student_id] = grade_value
            except (ValueError, IndexError):
                continue
    
    if bulk_grades:
        # Process bulk grade submission
        subject = request.form.get("subject", "").strip()
        term = request.form.get("term", "").strip() or None
        
        if not subject:
            flash("Subject is required for bulk grade entry.", "warning")
            return redirect(url_for("grades"))
        
        # Insert grades for each student
        for student_id, grade_value in bulk_grades.items():
            query_db(
                "INSERT INTO grades (student_id, school_id, subject, grade, recorded_by) VALUES (?, ?, ?, ?, ?)",
                (student_id, session.get("school_id"), subject, grade_value, session.get("user_id")),
                commit=True,
            )
        
        flash(f"Grades recorded successfully for {len(bulk_grades)} students.", "success")
        return redirect(url_for("grades"))
    else:
        # Process single grade submission (from class tab)
        student_id = request.form.get("student_id")
        subject = request.form.get("subject", "").strip()
        grade_value = request.form.get("grade", "").strip()

        if not student_id or not subject or not grade_value:
            flash("Student, subject, and grade are required.", "warning")
            return redirect(url_for("grades"))

        query_db(
            "INSERT INTO grades (student_id, school_id, subject, grade, recorded_by) VALUES (?, ?, ?, ?, ?)",
            (student_id, session.get("school_id"), subject, grade_value, session.get("user_id")),
            commit=True,
        )
        flash("Grade recorded successfully.", "success")
        return redirect(url_for("grades"))


@app.route("/grades/download")
@login_required
@teacher_required
def download_grades_csv():
    """Download all grades as CSV"""
    school_id = session.get("school_id")
    selected_term = request.args.get("term", "").strip()

    grades_query = """SELECT g.*, s.name as student_name, s.student_number, u.name as recorded_by_name
               FROM grades g
               JOIN students s ON g.student_id = s.id
               JOIN users u ON g.recorded_by = u.id
               WHERE g.school_id = ?"""
    grades_params = [school_id]
    if selected_term:
        grades_query += " AND g.term = ?"
        grades_params.append(selected_term)
    grades_query += " ORDER BY g.created_at DESC"

    grades_data = query_db(grades_query, tuple(grades_params))

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student ID", "Student Name", "Student Number", "Subject",
        "Term", "Grade", "Recorded By", "Date"
    ])

    for grade in grades_data:
        writer.writerow([
            grade["student_id"],
            grade["student_name"],
            grade["student_number"],
            grade["subject"],
            grade["term"] or "",
            grade["grade"],
            grade["recorded_by_name"],
            grade["created_at"][:10] if grade["created_at"] else "",
        ])

    from flask import Response
    filename = f"grades_export_{selected_term or 'all'}.csv"
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )
    return response


def calculate_grade_result(class_test=None, midterm_exam=None, class_score=None, final_exam=None,
                           class_test_weight=0.20, midterm_exam_weight=0.20, class_score_weight=0.10, final_exam_weight=0.50):
    """Calculate weighted total, grade, and remark from uploaded score components."""
    score_parts = (class_test, midterm_exam, class_score, final_exam)
    if all(score is None for score in score_parts):
        return None, "", ""

    total_score = (
        ((class_test or 0) * class_test_weight) +
        ((midterm_exam or 0) * midterm_exam_weight) +
        ((class_score or 0) * class_score_weight) +
        ((final_exam or 0) * final_exam_weight)
    )

    if total_score >= 80:
        return total_score, "1", "Outstanding / Excellent performance. Keeps up the brilliant work."
    if total_score >= 70:
        return total_score, "2", "High / Very Good / Very good. Very high understanding of the subject matter."
    if total_score >= 60:
        return total_score, "3", "High Average / Good / Good. Possesses a reasonable and fair understanding."
    if total_score >= 50:
        return total_score, "4", "Average / Credit / Satisfactory. Average performance but capable of better."
    if total_score >= 40:
        return total_score, "5", "Low / Pass / Pass. A developing understanding; requires close monitoring."
    if total_score >= 35:
        return total_score, "6", "Lower / Weak / Needs Improvement. Struggling with basic concepts."
    return total_score, "9", "Lowest / Failure / Unsatisfactory. Intensive remedial attention required."


@app.route("/grades/upload_scores", methods=["POST"])
@login_required
@teacher_required
def upload_scores():
    """Upload scores from CSV file"""
    school_id = session.get("school_id")
    if not school_id:
        flash("Please select a school first.", "error")
        return redirect(url_for("grades"))
    
    term = request.form.get("term")
    subject = request.form.get("subject")
    score_file = request.files.get("score_file")
    
    if not term or not subject:
        flash("Please select both term and subject.", "error")
        return redirect(url_for("grades"))
    
    if not score_file or score_file.filename == "":
        flash("Please select a CSV file to upload.", "error")
        return redirect(url_for("grades"))
    
    if not score_file.filename.lower().endswith('.csv'):
        flash("Please upload a CSV file only.", "error")
        return redirect(url_for("grades"))
    
    try:
        # Read and parse CSV file
        import csv
        import io
        
        # Read the file content
        stream = io.StringIO(score_file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Expected columns: student_id or student_number, class_test, midterm_exam, final_exam
        # We'll try to be flexible with column names
        fieldnames = [name.strip().lower() for name in csv_input.fieldnames] if csv_input.fieldnames else []
        
        # Map possible column names
        student_id_col = None
        student_number_col = None
        class_test_col = None
        midterm_exam_col = None
        class_score_col = None
        final_exam_col = None
        
        for field in fieldnames:
            if 'student' in field and 'id' in field:
                student_id_col = field
            elif 'student' in field and 'number' in field:
                student_number_col = field
            elif 'class' in field and 'test' in field:
                class_test_col = field
            elif 'midterm' in field and 'exam' in field:
                midterm_exam_col = field
            elif ('class' in field and 'score' in field) or (field == 'cs'):
                class_score_col = field
            elif 'final' in field and 'exam' in field:
                final_exam_col = field
        
        # If we didn't find specific columns, try alternatives
        if not student_id_col:
            for field in fieldnames:
                if field == 'student_id' or field == 'id':
                    student_id_col = field
                    break
        if not student_number_col:
            for field in fieldnames:
                if field == 'student_number' or field == 'roll_no' or field == 'rollnumber':
                    student_number_col = field
                    break
        if not class_test_col:
            for field in fieldnames:
                if field == 'class_test' or field == 'ct':
                    class_test_col = field
                    break
        if not midterm_exam_col:
            for field in fieldnames:
                if field == 'midterm_exam' or field == 'me':
                    midterm_exam_col = field
                    break
        if not class_score_col:
            for field in fieldnames:
                if field == 'class_score' or field == 'cs':
                    class_score_col = field
                    break
        if not final_exam_col:
            for field in fieldnames:
                if field == 'final_exam' or field == 'fe':
                    final_exam_col = field
                    break
        
        if not student_id_col and not student_number_col:
            flash("CSV must contain either 'student_id' or 'student_number' column.", "error")
            return redirect(url_for("grades"))
        
        if not class_test_col and not midterm_exam_col and not class_score_col and not final_exam_col:
            flash("CSV must contain at least one of: 'class_test', 'midterm_exam', 'class_score', or 'final_exam' column.", "error")
            return redirect(url_for("grades"))
        
        # Process each row
        updated_count = 0
        for row in csv_input:
            # Get student identifier
            student_identifier = None
            if student_id_col and row.get(student_id_col):
                student_identifier = row.get(student_id_col).strip()
            elif student_number_col and row.get(student_number_col):
                student_identifier = row.get(student_number_col).strip()
            
            if not student_identifier:
                continue
            
            # Find student by ID or student number
            student = None
            if student_id_col:
                try:
                    student_id = int(student_identifier)
                    student = query_db("SELECT * FROM students WHERE id = ? AND school_id = ?", 
                                      (student_id, school_id), one=True)
                except ValueError:
                    pass
            
            if not student and student_number_col:
                student = query_db("SELECT * FROM students WHERE student_number = ? AND school_id = ?", 
                                  (student_identifier, school_id), one=True)
            
            if not student:
                continue  # Skip if student not found
            
            student_id = student["id"]
            
            # Get scores
            class_test = None
            midterm_exam = None
            class_score = None
            final_exam = None
            
            if class_test_col and row.get(class_test_col):
                try:
                    class_test = float(row.get(class_test_col))
                except ValueError:
                    pass
            
            if midterm_exam_col and row.get(midterm_exam_col):
                try:
                    midterm_exam = float(row.get(midterm_exam_col))
                except ValueError:
                    pass
            
            if class_score_col and row.get(class_score_col):
                try:
                    class_score = float(row.get(class_score_col))
                except ValueError:
                    pass
            
            if final_exam_col and row.get(final_exam_col):
                try:
                    final_exam = float(row.get(final_exam_col))
                except ValueError:
                    pass
            
            total_score, grade, remark = calculate_grade_result(
                class_test, midterm_exam, class_score, final_exam
            )
            
            # Insert or update grade record
            # Check if record already exists for this student, subject, and term
            existing = query_db("""SELECT id FROM grades 
                                  WHERE student_id = ? AND school_id = ? AND subject = ? 
                                  AND term = ?""", 
                               (student_id, school_id, subject, term), one=True)
            
            if existing:
                # Update existing record
                query_db("""UPDATE grades SET 
                           class_test = COALESCE(?, class_test),
                           midterm_exam = COALESCE(?, midterm_exam),
                           class_score = COALESCE(?, class_score),
                           final_exam = COALESCE(?, final_exam),
                           total_score = COALESCE(?, total_score),
                           grade = COALESCE(?, grade),
                           remark = COALESCE(?, remark),
                           recorded_by = ?,
                           created_at = CURRENT_TIMESTAMP
                           WHERE id = ?""", 
                       (class_test, midterm_exam, class_score, final_exam, total_score, grade, remark,
                        session.get("user_id"), existing["id"]), 
                       commit=True)
            else:
                # Insert new record
                query_db("""INSERT INTO grades 
                           (student_id, school_id, subject, term, class_test, midterm_exam, 
                            class_score, final_exam, total_score, grade, remark, recorded_by) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                       (student_id, school_id, subject, term, class_test, midterm_exam, 
                        class_score, final_exam, total_score, grade, remark, session.get("user_id")), 
                       commit=True)
            
            updated_count += 1
        
        if updated_count > 0:
            flash(f"Scores uploaded successfully for {updated_count} students.", "success")
        else:
            flash("No valid data found in the CSV file.", "warning")
        
    except Exception as e:
        flash(f"Error processing CSV file: {str(e)}", "error")
     
    return redirect(url_for("grades"))


@app.route("/save_grades", methods=["POST"])
@teacher_required
def save_grades():
    """Save grades from inline form"""
    school_id = session.get("school_id")
    student_id = request.form.get("student_id")
    term = request.form.get("term")
    
    if not school_id or not student_id:
        flash("Invalid request. Please select a school and student.", "error")
        return redirect(url_for("grades"))
    
    try:
        student_id = int(student_id)
    except ValueError:
        flash("Invalid student ID.", "error")
        return redirect(url_for("grades"))
    
    # Get form data
    subjects = request.form.getlist("subject")
    
    # Attendance is always sourced from the attendance register, never typed into Grades.
    try:
        attendance_rows = query_db(
            "SELECT student_id, status, session FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        attendance_has_session = True
    except Exception:
        attendance_rows = query_db(
            "SELECT student_id, status FROM attendances WHERE school_id = ?",
            (school_id,),
        )
        attendance_has_session = False
    attendance_present = len({
        row["date"] for row in attendance_rows
        if row["student_id"] == student_id and row["status"] == "present"
    })
    attendance_settings = query_db(
        "SELECT attendance_term_weeks FROM schools WHERE id = ?",
        (school_id,), one=True,
    ) or {}
    attendance_total = (attendance_settings.get("attendance_term_weeks") or 12) * 5

    # Get the remaining report metadata.
    promoted_to = request.form.get("promoted_to")
    conduct = request.form.get("conduct")
    interest = request.form.get("interest")
    head_remarks = request.form.get("head_remarks")
    teacher_remarks = request.form.get("teacher_remarks", head_remarks)
    signature = request.form.get("signature", "").strip() or None
    position = request.form.get("position", "").strip() or None
    class_size = request.form.get("class_size", "").strip() or None
    reopening_date = request.form.get("reopening_date", "").strip() or None
    
    # Get school grading weights
    school_weights = query_db(
        "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight FROM schools WHERE id = ?",
        (school_id,), one=True
    )
    if school_weights:
        class_test_weight = school_weights["class_test_weight"] or 0.20
        midterm_exam_weight = school_weights["midterm_exam_weight"] or 0.20
        class_score_weight = school_weights["class_score_weight"] or 0.10
        final_exam_weight = school_weights["final_exam_weight"] or 0.50
    else:
        class_test_weight = 0.20
        midterm_exam_weight = 0.20
        class_score_weight = 0.10
        final_exam_weight = 0.50
    
    report_term = term or "General"
    existing_report = query_db(
        "SELECT id FROM student_reports WHERE student_id = ? AND school_id = ? AND term = ?",
        (student_id, school_id, report_term), one=True
    )

    allowed_columns = has_table_columns("student_reports", {"position", "class_size", "reopening_date"})
    base_columns = [
        "attendance_present","attendance_total","promoted_to","conduct","interest",
        "teacher_remarks","head_remarks","signature",
    ]
    base_values = [
        attendance_present,
        attendance_total,
        promoted_to or None,
        conduct or None,
        interest or None,
        teacher_remarks or None,
        head_remarks or None,
        signature,
    ]

    if "position" in allowed_columns:
        base_columns.append("position")
        base_values.append(position)
    if "class_size" in allowed_columns:
        base_columns.append("class_size")
        base_values.append(class_size)
    if "reopening_date" in allowed_columns:
        base_columns.append("reopening_date")
        base_values.append(reopening_date)

    update_assignments = ", ".join(f"{col} = ?" for col in base_columns)
    if existing_report:
        update_values = [*base_values, existing_report["id"]]
        query_db(f"UPDATE student_reports SET {update_assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", update_values, commit=True)
    else:
        import datetime
        base_values.append(datetime.datetime.now())
        insert_columns = ["student_id", "school_id", "term", *base_columns, "updated_at"]
        insert_values = [student_id, school_id, report_term, *base_values]
        placeholders = ", ".join("?" for _ in insert_columns)
        query_db(f"INSERT INTO student_reports ({', '.join(insert_columns)}) VALUES ({placeholders})", insert_values, commit=True)
    
    # Process each subject
    for subject in subjects:
        # Get field values for this subject
        class_test_val = request.form.get(f"class_test_{subject}")
        midterm_exam_val = request.form.get(f"midterm_exam_{subject}")
        class_score_val = request.form.get(f"class_score_{subject}")
        final_exam_val = request.form.get(f"final_exam_{subject}")
        grade_val = request.form.get(f"grade_{subject}")
        remark_val = request.form.get(f"remark_{subject}")
        
        # Convert scores to float or None
        class_test = None
        if class_test_val:
            try:
                class_test = float(class_test_val)
            except ValueError:
                pass
              
        midterm_exam = None
        if midterm_exam_val:
            try:
                midterm_exam = float(midterm_exam_val)
            except ValueError:
                pass
                
        class_score = None
        if class_score_val:
            try:
                class_score = float(class_score_val)
            except ValueError:
                pass
                
        final_exam = None
        if final_exam_val:
            try:
                final_exam = float(final_exam_val)
            except ValueError:
                pass

        # Calculate total score from weighted inputs
        total_score = (
            ((class_test or 0) * class_test_weight) +
            ((midterm_exam or 0) * midterm_exam_weight) +
            ((class_score or 0) * class_score_weight) +
            ((final_exam or 0) * final_exam_weight)
        )
        
        remarks_map = {
            'A+': 'Excellent. Outstanding / Exceptional work. Shows deep understanding. Consistently performs at a high level.',
            'A': 'Excellent. High-quality results. Active class participant. Expresses ideas clearly.',
            'B+': 'Very Good. High-quality results. Active class participant. Expresses ideas clearly.',
            'B': 'Very Good / Good. High-quality results. Active class participant. Expresses ideas clearly.',
            'C+': 'Satisfactory. Competent work. Meets basic requirements. Capable of higher achievement with focus.',
            'C': 'Satisfactory / Fair. Competent work. Meets basic requirements. Capable of higher achievement with focus.',
            'D+': 'Needs Improvement. Struggles to stay on task. Requires frequent reminders. Extra support needed.',
            'D': 'Needs Improvement. Struggles to stay on task. Requires frequent reminders. Extra support needed.',
            'F': 'Unsatisfactory. Below grade expectations. Missing core assignments. Frequent absences impacting performance.',
            '1': 'Outstanding / Excellent performance. Keeps up the brilliant work.',
            '2': 'High / Very Good / Very good. Very high understanding of the subject matter.',
            '3': 'High Average / Good / Good. Possesses a reasonable and fair understanding.',
            '4': 'Average / Credit / Satisfactory. Average performance but capable of better.',
            '5': 'Low / Pass / Pass. A developing understanding; requires close monitoring.',
            '6': 'Lower / Weak / Needs Improvement. Struggling with basic concepts.',
            '9': 'Lowest / Failure / Unsatisfactory. Intensive remedial attention required.'
        }
        
        if not grade_val:
            if total_score >= 95:
                grade = 'A+'
            elif total_score >= 90:
                grade = 'A'
            elif total_score >= 85:
                grade = 'B+'
            elif total_score >= 80:
                grade = 'B'
            elif total_score >= 75:
                grade = 'C+'
            elif total_score >= 70:
                grade = 'C'
            elif total_score >= 65:
                grade = 'D+'
            elif total_score >= 60:
                grade = 'D'
            else:
                grade = 'F'
            remark = remark_val if remark_val else remarks_map.get(grade, '')
        else:
            grade = grade_val
            remark = remark_val if remark_val else remarks_map.get(grade_val.upper(), '')
        
        # Check if record exists
        existing = query_db("""SELECT id FROM grades 
                              WHERE student_id = ? AND school_id = ? AND subject = ? 
                              AND term = ?""", 
                        (student_id, school_id, subject, term), one=True)
        
        if existing:
            query_db("""UPDATE grades SET 
                        class_test = ?,
                        midterm_exam = ?,
                        class_score = ?,
                        final_exam = ?,
                        total_score = ?,
                        grade = ?,
                        remark = ?,
                        recorded_by = ?,
                        created_at = CURRENT_TIMESTAMP
                        WHERE id = ?""", 
                     (class_test, midterm_exam, class_score, final_exam, total_score, grade, remark,
                      session.get("user_id"), existing["id"]), 
                     commit=True)
        else:
            query_db("""INSERT INTO grades 
                        (student_id, school_id, subject, term, class_test, midterm_exam, 
                         class_score, final_exam, total_score, grade, remark, recorded_by) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                     (student_id, school_id, subject, term, class_test, midterm_exam, 
                      class_score, final_exam, total_score, grade, remark, session.get("user_id")), 
                     commit=True)
    
    flash("Grades saved successfully.", "success")
    return redirect(url_for("grades", student_id=student_id, term=term))
    
    
@app.route("/grades/report/<int:student_id>")
@login_required
def student_grade_report(student_id):
    """Generate a printable/downloadable grade report for a single student."""
    school_id = session.get("school_id")
    if not school_id:
        abort(404)

    student = query_db(
        "SELECT * FROM students WHERE id = ? AND school_id = ?",
        (student_id, school_id),
        one=True,
    )
    if not student:
        abort(404)

    if session.get("role") == ROLE_PARENT and student.get("parent_user_id") != session.get("user_id"):
        abort(403)

    term = request.args.get("term", "").strip()
    school = query_db("SELECT name, class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight FROM schools WHERE id = ?", (school_id,), one=True)
    school_name = school["name"] if school else "School"

    sender = query_db("SELECT name FROM users WHERE id = ?", (session.get("user_id"),), one=True)
    sender_name = sender["name"] if sender else "Teacher"

    if term:
        grades_data = query_db(
            "SELECT subject, grade, class_test, midterm_exam, class_score, final_exam, total_score, remark, term FROM grades WHERE student_id = ? AND school_id = ? AND term = ? ORDER BY subject",
            (student_id, school_id, term),
        )
        report = get_student_report_row(student_id, school_id, term)
    else:
        grades_data = query_db(
            "SELECT subject, grade, class_test, midterm_exam, class_score, final_exam, total_score, remark, term FROM grades WHERE student_id = ? AND school_id = ? ORDER BY subject",
            (student_id, school_id),
        )
        report = get_student_report_row(student_id, school_id)

    teacher_remarks = ""
    head_remarks = ""
    attendance_present = None
    attendance_total = None
    conduct = ""
    promoted_to = ""
    signature = ""
    interest = ""
    report_term = term or (report.get("term") if report else "")
    position = ""
    class_size = ""
    reopening_date = ""

    if report:
        teacher_remarks = report.get("teacher_remarks") or ""
        head_remarks = report.get("head_remarks") or ""
        attendance_present = report.get("attendance_present")
        attendance_total = report.get("attendance_total")
        conduct = report.get("conduct") or ""
        promoted_to = report.get("promoted_to") or ""
        signature = report.get("signature") or ""
        interest = report.get("interest") or ""
        position = report.get("position") or ""
        class_size = report.get("class_size") or ""
        reopening_date = report.get("reopening_date") or ""

    class_test_weight = (school.get("class_test_weight") if school else None) or 0.20
    midterm_exam_weight = (school.get("midterm_exam_weight") if school else None) or 0.20
    class_score_weight = (school.get("class_score_weight") if school else None) or 0.10
    final_exam_weight = (school.get("final_exam_weight") if school else None) or 0.50

    report_document = build_grade_report_document(
        student,
        school_name,
        sender_name,
        grades_data,
        teacher_remarks,
        report_term,
        attendance_present,
        attendance_total,
        conduct,
        promoted_to,
        signature,
        interest,
        class_test_weight,
        midterm_exam_weight,
        class_score_weight,
        final_exam_weight,
        class_size,
        position,
        reopening_date,
        head_remarks=head_remarks,
    )

    if request.args.get("download") == "1" or request.args.get("format") == "pdf":
        pdf_bytes, _ = generate_pdf_from_html(report_document)
        safe_student_name = secure_filename(student["name"].replace(" ", "_")) or "student"
        if pdf_bytes:
            filename = f"{safe_student_name}_grade_report_{(term or report_term or 'all').replace(' ', '_')}.pdf"
            return Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        filename = f"{safe_student_name}_grade_report_{(term or report_term or 'all').replace(' ', '_')}.html"
        return Response(
            report_document.encode("utf-8"),
            mimetype="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return Response(report_document, mimetype="text/html")


def _bulk_grade_report(student, school_id, school_name, sender_name, term, custom_message=""):
    """Build the per-student grade report and delivery payload for bulk sends."""
    grades_query = (
        "SELECT subject, grade, class_test, midterm_exam, class_score, final_exam, "
        "total_score, remark, term FROM grades WHERE student_id = ? AND school_id = ?"
    )
    grade_args = [student["id"], school_id]
    if term:
        grades_query += " AND term = ?"
        grade_args.append(term)
    grades_query += " ORDER BY subject"
    grades_data = query_db(grades_query, tuple(grade_args))
    if not grades_data:
        return None

    report = get_student_report_row(student["id"], school_id, term if term else None) or {}
    teacher_remarks = report.get("teacher_remarks") or ""
    head_remarks = report.get("head_remarks") or ""
    report_term = report.get("term") or term
    school_weights = query_db(
        "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight FROM schools WHERE id = ?",
        (school_id,), one=True
    ) or {}
    weights = [
        school_weights.get("class_test_weight") or 0.20,
        school_weights.get("midterm_exam_weight") or 0.20,
        school_weights.get("class_score_weight") or 0.10,
        school_weights.get("final_exam_weight") or 0.50,
    ]
    report_document = build_grade_report_document(
        student, school_name, sender_name, grades_data, teacher_remarks, report_term,
        report.get("attendance_present"), report.get("attendance_total"),
        report.get("conduct") or "", report.get("promoted_to") or "",
        report.get("signature") or "", report.get("interest") or "",
        *weights, report.get("class_size") or "", report.get("position") or "",
        report.get("reopening_date") or "", head_remarks=head_remarks,
    )
    pdf_bytes, _ = generate_pdf_from_html(report_document)
    attachment = (pdf_bytes, "application/pdf") if pdf_bytes else None
    safe_name = secure_filename(student["name"].replace(" ", "_")) or "student"
    attachment_filename = (
        f"grade_report_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        if pdf_bytes else None
    )
    sms_lines = [f"Grade report for {student['name']}"]
    for grade in grades_data:
        total = f"{grade['total_score']:.1f}" if grade.get("total_score") is not None else "N/A"
        sms_lines.append(f"{grade.get('subject') or 'Subject'}: {grade.get('grade') or 'N/A'} ({total})")
    if teacher_remarks:
        sms_lines.append(f"Teacher's remarks: {teacher_remarks}")
    email_message = custom_message.strip() or f"Please find the grade report for {student['name']} attached."
    if not pdf_bytes:
        email_message += "\n\n" + "\n".join(sms_lines)
    return {
        "attachment": attachment,
        "attachment_filename": attachment_filename,
        "email_body": (
            f"Dear {student.get('parent_name') or 'Parent'},\n\n"
            f"{email_message}\n\n"
            f"Best regards,\n{sender_name}\n{school_name}"
        ),
        "sms_body": "\n".join(sms_lines),
    }


@app.route("/send_grades_bulk", methods=["POST"])
@login_required
@teacher_required
def send_grades_bulk():
    """Send each student's grade report separately to their parent."""
    school_id = session.get("school_id")
    grade = request.form.get("grade", "").strip()
    section = request.form.get("section", "").strip()
    term = request.form.get("term", "").strip()
    subject = request.form.get("subject", "Grade Reports").strip() or "Grade Reports"
    custom_message = request.form.get("message", "")
    channels = set(request.form.getlist("channels")) & {"app", "email", "sms", "whatsapp"}

    if not school_id or not (grade or section):
        flash("Select a class or section before sending bulk grade reports.", "warning")
        return redirect(url_for("grades", grade=grade, section=section, term=term))
    if not channels:
        flash("Choose at least one delivery channel.", "warning")
        return redirect(url_for("grades", grade=grade, section=section, term=term))

    student_query = "SELECT * FROM students WHERE school_id = ? AND active = 1"
    student_args = [school_id]
    if grade:
        student_query += " AND grade = ?"
        student_args.append(grade)
    if section:
        student_query += " AND section = ?"
        student_args.append(section)
    students = query_db(student_query + " ORDER BY name", tuple(student_args))
    school = query_db("SELECT name FROM schools WHERE id = ?", (school_id,), one=True)
    sender = query_db("SELECT name FROM users WHERE id = ?", (session.get("user_id"),), one=True)
    school_name = school["name"] if school else "School"
    sender_name = sender["name"] if sender else "Teacher"
    whatsapp_access_token = (school.get("whatsapp_access_token") if school else None) or WHATSAPP_ACCESS_TOKEN
    whatsapp_phone_number_id = (school.get("whatsapp_phone_number_id") if school else None) or WHATSAPP_PHONE_NUMBER_ID
    counts = {channel: 0 for channel in channels}
    skipped = 0
    failures = 0
    skipped_students = []
    parent_user_available = "parent_user_id" in has_table_columns("students", {"parent_user_id"})

    for student in students:
        payload = _bulk_grade_report(student, school_id, school_name, sender_name, term, custom_message)
        if not payload:
            skipped += 1
            skipped_students.append(f"{student['name']} (no grades saved for the selected term)")
            continue
        delivered = False
        parent_email = student.get("parent_email")
        parent_phone = student.get("parent_contact")
        if "email" in channels and parent_email:
            sent, _ = send_email(parent_email, subject, payload["email_body"], sender_name,
                                 attachment=payload["attachment"], attachment_filename=payload["attachment_filename"])
            if sent:
                counts["email"] += 1
                delivered = True
            else:
                failures += 1
        if "sms" in channels and parent_phone:
            sent, _ = send_text_message(parent_phone, payload["sms_body"])
            if sent:
                counts["sms"] += 1
                delivered = True
            else:
                failures += 1
        if "whatsapp" in channels and parent_phone and whatsapp_access_token and whatsapp_phone_number_id:
            if payload["attachment"]:
                file_id, filename = save_temp_file(payload["attachment"][0], "pdf")
                if file_id:
                    file_path = os.path.join(TEMP_FILES_DIR, filename)
                    with open(file_path, "rb") as report_file:
                        media_id, _ = upload_whatsapp_media(
                            report_file.read(), filename, payload["attachment"][1],
                            access_token=whatsapp_access_token,
                            phone_number_id=whatsapp_phone_number_id,
                        )
                    if media_id:
                        sent, _ = send_whatsapp_api_message({
                            "messaging_product": "whatsapp", "to": normalize_phone_number(parent_phone),
                            "type": "document", "document": {"id": media_id, "filename": payload["attachment_filename"]},
                        }, access_token=whatsapp_access_token, phone_number_id=whatsapp_phone_number_id)
                    else:
                        sent = False
                else:
                    sent = False
            else:
                sent, _ = send_whatsapp_api_message({
                    "messaging_product": "whatsapp", "to": normalize_phone_number(parent_phone),
                    "type": "text", "text": {"preview_url": False, "body": payload["sms_body"]},
                }, access_token=whatsapp_access_token, phone_number_id=whatsapp_phone_number_id)
            if sent:
                counts["whatsapp"] += 1
                delivered = True
            else:
                failures += 1
        if "app" in channels and parent_user_available and student.get("parent_user_id"):
            query_db(
                "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (session.get("user_id"), student["parent_user_id"], school_id, subject, payload["email_body"], "app"),
                commit=True,
            )
            counts["app"] += 1
            delivered = True
        if not delivered:
            skipped += 1
            reasons = []
            if "app" in channels and (not parent_user_available or not student.get("parent_user_id")):
                reasons.append("parent has no linked app account")
            if "email" in channels and not parent_email:
                reasons.append("no parent email")
            if "sms" in channels and not parent_phone:
                reasons.append("no parent phone")
            if "whatsapp" in channels:
                if not parent_phone:
                    reasons.append("no parent phone for WhatsApp")
                elif not whatsapp_access_token or not whatsapp_phone_number_id:
                    reasons.append("WhatsApp is not configured")
            skipped_students.append(f"{student['name']} ({'; '.join(reasons) or 'no delivery completed'})")

    summary = ", ".join(f"{channel.title()}: {count}" for channel, count in counts.items())
    skipped_summary = f" Skipped students: {'; '.join(skipped_students)}." if skipped_students else ""
    flash(f"Bulk grade send complete. {summary}. Skipped: {skipped}. Failures: {failures}.{skipped_summary}", "success" if not failures and not skipped else "warning")
    return redirect(url_for("grades", grade=grade, section=section, term=term))


@app.route("/send_grades", methods=["POST"])
@login_required
@teacher_required
def send_grades():
    """Send grades to parent via email, SMS, or WhatsApp"""
    school_id = session.get("school_id")
    student_id = request.form.get("student_id")
    send_method = request.form.get("send_method", "email")
    subject = request.form.get("subject", "Grade Report")
    message = request.form.get("message", "")
    term = request.form.get("term")
    
    if not school_id or not student_id:
        flash("Invalid request. Please select a school and student.", "error")
        return redirect(url_for("grades"))
    
    try:
        student_id = int(student_id)
    except ValueError:
        flash("Invalid student ID.", "error")
        return redirect(url_for("grades"))
    
    # Get student data
    student = query_db(
        "SELECT * FROM students WHERE id = ? AND school_id = ?",
        (student_id, school_id),
        one=True
    )
    
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("grades"))
    
    # Get school name
    school = query_db("SELECT name FROM schools WHERE id = ?", (school_id,), one=True)
    school_name = school["name"] if school else "School"
    
    # Get sender name
    sender = query_db("SELECT name FROM users WHERE id = ?", (session.get("user_id"),), one=True)
    sender_name = sender["name"] if sender else "Teacher"
    
    # Get term from form
    term = request.form.get("term")
    
    # Get grade data
    if term:
        grades_data = query_db(
            "SELECT subject, grade, class_test, midterm_exam, class_score, final_exam, total_score, remark, term FROM grades WHERE student_id = ? AND school_id = ? AND term = ? ORDER BY subject",
            (student_id, school_id, term)
        )
    else:
        grades_data = query_db(
            "SELECT subject, grade, class_test, midterm_exam, class_score, final_exam, total_score, remark, term FROM grades WHERE student_id = ? AND school_id = ? ORDER BY subject",
            (student_id, school_id)
        )

    if not grades_data:
        flash("No grade records found for this student. Please save grades before sending a report.", "warning")
        return redirect(url_for("grades"))

    # Get teacher/head remarks and attendance from student_reports
    teacher_remarks = ""
    head_remarks = ""
    attendance_present = None
    attendance_total = None
    conduct = ""
    promoted_to = ""
    signature = ""
    interest = ""
    position = ""
    class_size = ""
    reopening_date = ""
    report_term = term
    report = get_student_report_row(student_id, school_id, term if term else None)
    if report:
        teacher_remarks = report.get("teacher_remarks") or ""
        head_remarks = report.get("head_remarks") or ""
        attendance_present = report.get("attendance_present")
        attendance_total = report.get("attendance_total")
        conduct = report.get("conduct") or ""
        promoted_to = report.get("promoted_to") or ""
        signature = report.get("signature") or ""
        interest = report.get("interest") or ""
        report_term = report.get("term") or report_term
        position = report.get("position") or ""
        class_size = report.get("class_size") or ""
        reopening_date = report.get("reopening_date") or ""
    import csv
    import io
    csv_output = io.StringIO()
    csv_writer = csv.writer(csv_output)

    school_weights = query_db(
        "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight FROM schools WHERE id = ?",
        (school_id,), one=True
    )
    if school_weights:
        class_test_weight = school_weights["class_test_weight"] or 0.20
        midterm_exam_weight = school_weights["midterm_exam_weight"] or 0.20
        class_score_weight = school_weights["class_score_weight"] or 0.10
        final_exam_weight = school_weights["final_exam_weight"] or 0.50
    else:
        class_test_weight = 0.20
        midterm_exam_weight = 0.20
        class_score_weight = 0.10
        final_exam_weight = 0.50

    report_document = build_grade_report_document(
        student,
        school_name,
        sender_name,
        grades_data,
        teacher_remarks,
        report_term,
        attendance_present,
        attendance_total,
        conduct,
        promoted_to,
        signature,
        interest,
        class_test_weight,
        midterm_exam_weight,
        class_score_weight,
        final_exam_weight,
        class_size,
        position,
        reopening_date,
        head_remarks=head_remarks,
    )

    safe_student_name = secure_filename(student["name"].replace(" ", "_")) or "student"

    attachment = None
    attachment_filename = ""

    pdf_bytes, pdf_err = generate_pdf_from_html(report_document)
    if pdf_bytes:
        attachment = (pdf_bytes, "application/pdf")
        attachment_filename = f"grade_report_{safe_student_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    else:
        # Do not attach raw HTML when PDF rendering is unavailable.
        attachment = None
        attachment_filename = ""

    if not grades_data:
        flash("No grade records found for this student. Please save grades before sending.", "warning")
        return redirect(url_for("grades"))

    email_body = f"Dear {student.get('parent_name', 'Parent')},\n\nPlease find the grade report for {student['name']} attached.\n\nBest regards,\n{sender_name}\n{school_name}"
    if message.strip():
        email_body = f"Dear {student.get('parent_name', 'Parent')},\n\n{message}\n\nBest regards,\n{sender_name}\n{school_name}"
    sms_message = f"Grade report for {student['name']} has been sent to your email."

    def format_grade_table(grades_data, teacher_remarks):
        if not grades_data:
            return "No grade records found for this student."
        message = f"Grade Report for {student['name']}\n"
        message += "=" * 50 + "\n"
        message += f"{'Subject':<20} {'Grade':<8} {'Total':<8} {'Remark':<20}\n"
        message += "-" * 60 + "\n"
        for g in grades_data:
            subject = g['subject'] or 'N/A'
            grade = g['grade'] or 'N/A'
            total = f"{g['total_score']:.1f}" if g['total_score'] is not None else 'N/A'
            remark = g['remark'] or ''
            if len(subject) > 18:
                subject = subject[:15] + "..."
            if len(remark) > 18:
                remark = remark[:15] + "..."
            message += f"{subject:<20} {grade:<8} {total:<8} {remark:<20}\n"
        if teacher_remarks:
            message += "\n" + "=" * 50 + "\n"
            message += f"Teacher's Remarks: {teacher_remarks}\n"
        return message

    if not pdf_bytes:
        email_body += "\n\n" + format_grade_table(grades_data, teacher_remarks)

    if send_method == "email":
        if student.get("parent_email"):
            success, error_msg = send_email(
                student["parent_email"],
                subject,
                email_body,
                sender_name,
                attachment=attachment,
                attachment_filename=attachment_filename,
            )
            if success:
                delivery_note = " as a PDF attachment" if pdf_bytes else " in the email body"
                flash(f"Grade report sent to {student['parent_email']} via email{delivery_note}.", "success")
            else:
                flash(f"Failed to send email to {student['parent_email']}: {error_msg}", "error")
        else:
            flash("Student has no parent email address on file.", "warning")
    elif send_method == "sms":
        if student.get("parent_contact"):
            success, error_msg = send_text_message(student["parent_contact"], sms_message)
            if success:
                flash(f"Grade report sent to {student['parent_contact']} via SMS.", "success")
            else:
                flash(f"Failed to send SMS to {student['parent_contact']}: {error_msg}", "error")
        else:
            flash("Student has no parent contact number on file.", "warning")
    elif send_method == "whatsapp":
        if student.get("parent_contact"):
            file_id, saved_filename = save_temp_file(
                pdf_bytes if pdf_bytes else report_document.encode("utf-8"),
                "pdf" if pdf_bytes else "html",
            )
            preview_url = url_for("serve_temp_file", file_id=file_id, _external=True)

            if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
                whatsapp_url = build_whatsapp_url(
                    student["parent_contact"],
                    f"Grade report for {student['name']} is ready. Download PDF: {preview_url}",
                )
                if whatsapp_url:
                    flash("WhatsApp Business API is not configured. Opening WhatsApp with the report link for manual sending.", "info")
                    return render_whatsapp_open_page(whatsapp_url)
                flash("Student parent contact is not a valid WhatsApp phone number.", "warning")
                return redirect(url_for("grades", student_id=student_id, term=term))

            file_path = os.path.join(TEMP_FILES_DIR, saved_filename)
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            mime_type = "application/pdf" if (pdf_bytes and saved_filename.endswith(".pdf")) else "text/html"
            media_id, media_err = upload_whatsapp_media(file_bytes, saved_filename, mime_type)
            if media_id:
                whatsapp_data = {
                    "messaging_product": "whatsapp",
                    "to": normalize_phone_number(student["parent_contact"]),
                    "type": "document",
                    "document": {
                        "id": media_id,
                        "filename": attachment_filename,
                    },
                }
                success, error_msg = send_whatsapp_api_message(whatsapp_data)
                if success:
                    flash(
                        f"Grade report sent to {student['parent_contact']} via WhatsApp as document attachment.",
                        "success",
                    )
                else:
                    flash(f"Failed to send WhatsApp document to {student['parent_contact']}: {error_msg}", "error")
            else:
                flash(
                    f"WhatsApp media upload failed: {media_err}. <a href='{preview_url}' target='_blank'>Open report</a> and send manually.",
                    "warning",
                )
        else:
            flash("Student has no parent contact number on file.", "warning")
    else:
        flash("Unknown send method selected.", "error")

    return redirect(url_for("grades", student_id=student_id, term=term))


@app.route("/temp/<file_id>")
@login_required
def serve_temp_file(file_id):
    """Serve temporary export files securely"""
    if not file_id or not all(char.isalnum() or char == "-" for char in file_id):
        abort(400)

    prefix = f"grade_report_{file_id}."
    filename = next(
        (
            candidate
            for candidate in os.listdir(TEMP_FILES_DIR)
            if candidate.startswith(prefix) and os.path.isfile(os.path.join(TEMP_FILES_DIR, candidate))
        ),
        None,
    )

    if not filename:
        abort(404)

    # Determine MIME type based on file extension
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mimetype = "application/pdf" if ext == "pdf" else "text/html"

    return send_from_directory(TEMP_FILES_DIR, filename, as_attachment=True, mimetype=mimetype)


@app.route("/temp/<file_id>/view")
@login_required
def view_temp_file(file_id):
    """View a temporary export file in browser"""
    if not file_id or not all(char.isalnum() or char == "-" for char in file_id):
        abort(400)
    prefix = f"grade_report_{file_id}."
    filename = next(
        (
            candidate
            for candidate in os.listdir(TEMP_FILES_DIR)
            if candidate.startswith(prefix) and os.path.isfile(os.path.join(TEMP_FILES_DIR, candidate))
        ),
        None,
    )
    if not filename:
        abort(404)
    return send_from_directory(TEMP_FILES_DIR, filename, as_attachment=False)


@app.route("/admin")
@app.route("/admin_panel")
@login_required
@admin_required
def admin_panel():
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    # Superadmin sees all schools' data; regular admins see only their school
    if user_role == ROLE_SUPERADMIN:
        users = query_db(
            "SELECT users.*, schools.school_code FROM users JOIN schools ON users.school_id = schools.id ORDER BY users.role, users.name"
        )
        students = query_db(
            "SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id ORDER BY students.grade, students.section, students.name"
        )
        grades = query_db(
            "SELECT DISTINCT grade FROM students WHERE grade IS NOT NULL ORDER BY grade"
        )
        sections = query_db(
            "SELECT DISTINCT section FROM students WHERE section IS NOT NULL ORDER BY section"
        )
        recent_grades = query_db(
            """
            SELECT g.*, s.name AS student_name, u.name AS recorded_by_name
            FROM grades g
            JOIN students s ON g.student_id = s.id
            JOIN users u ON g.recorded_by = u.id
            ORDER BY g.created_at DESC
            LIMIT 5
            """
        )
        recent_announcements = query_db(
            """
            SELECT a.*, u.name AS created_by_name
            FROM announcements a
            JOIN users u ON a.created_by = u.id
            ORDER BY a.created_at DESC
            LIMIT 5
            """
        )
        attendances = query_db(
            """
            SELECT a.*, s.name AS student_name, s.student_number,
                   u.name AS teacher_name, schools.school_code
            FROM attendances a
            JOIN students s ON a.student_id = s.id
            JOIN users u ON a.recorded_by = u.id
            JOIN schools ON a.school_id = schools.id
            ORDER BY a.date DESC
            LIMIT 50
            """
        )
        inventory_items = query_db("SELECT * FROM inventory_items WHERE is_active = 1")
        low_stock_inventory = query_db("SELECT * FROM inventory_items WHERE is_active = 1 AND status = 'low_stock'")
    else:
        # Regular admin - filtered by their school
        users = query_db(
            "SELECT users.*, schools.school_code FROM users JOIN schools ON users.school_id = schools.id WHERE users.school_id = ? ORDER BY users.role, users.name",
            (user_school_id,)
        )
        students = query_db(
            "SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id WHERE students.school_id = ? ORDER BY students.grade, students.section, students.name",
            (user_school_id,)
        )
        grades = query_db(
            "SELECT DISTINCT grade FROM students WHERE school_id = ? AND grade IS NOT NULL ORDER BY grade",
            (user_school_id,),
        )
        sections = query_db(
            "SELECT DISTINCT section FROM students WHERE school_id = ? AND section IS NOT NULL ORDER BY section",
            (user_school_id,),
        )
        recent_grades = query_db(
            """
            SELECT g.*, s.name AS student_name, u.name AS recorded_by_name
            FROM grades g
            JOIN students s ON g.student_id = s.id
            JOIN users u ON g.recorded_by = u.id
            WHERE g.school_id = ?
            ORDER BY g.created_at DESC
            LIMIT 5
            """,
            (user_school_id,),
        )
        recent_announcements = query_db(
            """
            SELECT a.*, u.name AS created_by_name
            FROM announcements a
            JOIN users u ON a.created_by = u.id
            WHERE a.school_id = ?
            ORDER BY a.created_at DESC
            LIMIT 5
            """,
            (user_school_id,),
        )
        attendances = query_db(
            """
            SELECT a.*, s.name AS student_name, s.student_number,
                   u.name AS teacher_name, schools.school_code
            FROM attendances a
            JOIN students s ON a.student_id = s.id
            JOIN users u ON a.recorded_by = u.id
            JOIN schools ON a.school_id = schools.id
            WHERE a.school_id = ?
            ORDER BY a.date DESC
            LIMIT 50
            """,
            (user_school_id,)
        )
        inventory_items = query_db("SELECT * FROM inventory_items WHERE school_id = ? AND is_active = 1", (user_school_id,))
        low_stock_inventory = query_db("SELECT * FROM inventory_items WHERE school_id = ? AND is_active = 1 AND status = 'low_stock'", (user_school_id,))

    schools = query_db("SELECT * FROM schools ORDER BY name")
    return render_template("admin.html", users=users, students=students, schools=schools, attendances=attendances, grades=grades, sections=sections, recent_grades=recent_grades, recent_announcements=recent_announcements, inventory_items=inventory_items, low_stock_inventory=low_stock_inventory)


@app.route("/admin/settings")
@login_required
@admin_required
def admin_settings():
    if session.get("role") == ROLE_SUPERADMIN:
        school_id = request.args.get("school_id", type=int)
        if not school_id:
            flash("Please select a school to configure.", "warning")
            return redirect(url_for("admin_panel"))
    else:
        school_id = session.get("school_id")
        if not school_id:
            school_row = query_db("SELECT id FROM schools ORDER BY id LIMIT 1", one=True)
            school_id = school_row["id"] if school_row else None
            if school_id:
                session["school_id"] = school_id
    
    if not school_id:
        flash("Please select a school to configure.", "warning")
        return redirect(url_for("admin_panel"))

    # Get current grade weight settings
    settings = {}
    try:
        settings = dict(query_db(
            "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight, passing_marks, academic_term, attendance_term_weeks, smtp_server, smtp_port, smtp_email, sender_name, twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, whatsapp_access_token, whatsapp_phone_number_id, school_email, school_phone, school_address, school_website FROM schools WHERE id = ?",
            (school_id,), one=True
        ) or {})
    except Exception:
        try:
            settings = dict(query_db(
                "SELECT class_test_weight, midterm_exam_weight, class_score_weight, final_exam_weight, passing_marks, academic_term, attendance_term_weeks FROM schools WHERE id = ?",
                (school_id,), one=True
            ) or {})
        except Exception:
            settings = {}

    # Get current sections for this school
    try:
        sections = query_db(
            "SELECT id, name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        # Remove duplicates
        seen = set()
        unique_sections = []
        for s in (sections or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_sections.append(s)
        sections = unique_sections
    except Exception:
        sections = []

    # Get current grade levels for this school
    try:
        grade_levels = query_db(
            "SELECT id, name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,)
        )
        # Remove duplicates
        seen = set()
        unique_grades = []
        for g in (grade_levels or []):
            name = g.get("name")
            if name not in seen:
                seen.add(name)
                unique_grades.append(g)
        grade_levels = unique_grades
    except Exception:
        grade_levels = []

    try:
        school_subjects = query_db(
            "SELECT id, name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        # Remove duplicates based on name
        seen_names = set()
        unique_subjects = []
        for s in (school_subjects or []):
            name = s.get("name")
            if name not in seen_names:
                seen_names.add(name)
                unique_subjects.append(s)
        school_subjects = unique_subjects
    except Exception:
        school_subjects = []

    try:
        class_subjects = query_db(
            "SELECT id, grade_level, section, subject FROM school_class_subjects WHERE school_id = ? ORDER BY grade_level, section, sort_order, subject",
            (school_id,)
        )
        # Remove duplicates based on (grade_level, section, subject)
        seen_combos = set()
        unique_class_subjects = []
        for cs in (class_subjects or []):
            key = (cs.get("grade_level"), cs.get("section"), cs.get("subject"))
            if key not in seen_combos:
                seen_combos.add(key)
                unique_class_subjects.append(cs)
        class_subjects = unique_class_subjects
    except Exception:
        class_subjects = []

    # Get school info
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True) or {}

    return render_template("admin/settings.html", settings=settings, sections=sections, grade_levels=grade_levels, school=school, school_subjects=school_subjects, class_subjects=class_subjects)


@app.route("/admin/settings", methods=["POST"])
@login_required
@admin_required
def admin_settings_save():
    if session.get("role") == ROLE_SUPERADMIN:
        school_id = request.form.get("school_id", type=int)
        if not school_id:
            flash("Please select a school to configure.", "warning")
            return redirect(url_for("admin_panel"))
    else:
        school_id = session.get("school_id")

    action = request.form.get("action", "")

    if action == "save_weights":
        class_test = float(request.form.get("class_test_weight", 20)) / 100
        midterm = float(request.form.get("midterm_exam_weight", 20)) / 100
        class_score = float(request.form.get("class_score_weight", 10)) / 100
        final_exam = float(request.form.get("final_exam_weight", 50)) / 100

        # Validate total = 100%
        total = class_test + midterm + class_score + final_exam
        if abs(total - 1.0) > 0.01:
            flash("Grade weights must total 100%.", "error")
            return redirect(url_for("admin_settings"))

        # Save all settings fields
        school_name = request.form.get("school_name", "").strip()
        school_code = request.form.get("school_code", "").strip()
        school_description = request.form.get("school_description", "").strip()
        passing_marks = request.form.get("passing_marks", type=int)
        academic_term = request.form.get("academic_term", "").strip()
        attendance_term_weeks = request.form.get("attendance_term_weeks", type=int)

        smtp_server = request.form.get("smtp_server", "").strip()
        smtp_port = request.form.get("smtp_port", type=int)
        smtp_email = request.form.get("smtp_email", "").strip()
        smtp_password = request.form.get("smtp_password", "").strip()
        sender_name = request.form.get("sender_name", "").strip()

        twilio_account_sid = request.form.get("twilio_account_sid", "").strip()
        twilio_auth_token = request.form.get("twilio_auth_token", "").strip()
        twilio_from_number = request.form.get("twilio_from_number", "").strip()
        twilio_messaging_service_sid = request.form.get("twilio_messaging_service_sid", "").strip()

        whatsapp_access_token = request.form.get("whatsapp_access_token", "").strip()
        whatsapp_phone_number_id = request.form.get("whatsapp_phone_number_id", "").strip()

        school_email = request.form.get("school_email", "").strip()
        school_phone = request.form.get("school_phone", "").strip()
        school_address = request.form.get("school_address", "").strip()
        school_website = request.form.get("school_website", "").strip()

        execute_db(
            "UPDATE schools SET class_test_weight = ?, midterm_exam_weight = ?, class_score_weight = ?, final_exam_weight = ?, name = ?, school_code = ?, description = ?, passing_marks = ?, academic_term = ?, attendance_term_weeks = ?, smtp_server = ?, smtp_port = ?, smtp_email = ?, smtp_password = ?, sender_name = ?, twilio_account_sid = ?, twilio_auth_token = ?, twilio_from_number = ?, twilio_messaging_service_sid = ?, whatsapp_access_token = ?, whatsapp_phone_number_id = ?, school_email = ?, school_phone = ?, school_address = ?, school_website = ? WHERE id = ?",
            (class_test, midterm, class_score, final_exam, school_name, school_code, school_description, passing_marks, academic_term, attendance_term_weeks, smtp_server, smtp_port, smtp_email, smtp_password, sender_name, twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, whatsapp_access_token, whatsapp_phone_number_id, school_email, school_phone, school_address, school_website, school_id)
        )
        flash("Settings saved successfully.", "success")

    elif action == "add_section":
        section_name = request.form.get("new_section", "").strip()
        if section_name:
            try:
                existing = query_db(
                    "SELECT id FROM school_sections WHERE school_id = ? AND name = ?",
                    (school_id, section_name)
                )
                if existing:
                    flash(f"Section '{section_name}' already exists.", "warning")
                else:
                    execute_db(
                        "INSERT INTO school_sections (school_id, name) VALUES (?, ?)",
                        (school_id, section_name)
                    )
                    flash(f"Section '{section_name}' added successfully.", "success")
            except Exception as e:
                flash(f"Error adding section: {str(e)}", "error")

    elif action == "remove_section":
        section_id = request.form.get("section_id", type=int)
        if section_id:
            try:
                execute_db(
                    "DELETE FROM school_sections WHERE id = ? AND school_id = ?",
                    (section_id, school_id)
                )
                flash("Section removed successfully.", "success")
            except Exception as e:
                flash(f"Error removing section: {str(e)}", "error")

    elif action == "add_grade":
        grade_name = request.form.get("new_grade_level", "").strip()
        if grade_name:
            try:
                existing = query_db(
                    "SELECT id FROM school_grade_levels WHERE school_id = ? AND name = ?",
                    (school_id, grade_name)
                )
                if existing:
                    flash(f"Grade level '{grade_name}' already exists.", "warning")
                else:
                    execute_db(
                        "INSERT INTO school_grade_levels (school_id, name, sort_order) VALUES (?, ?, 0)",
                        (school_id, grade_name)
                    )
                    flash(f"Grade level '{grade_name}' added successfully.", "success")
            except Exception as e:
                flash(f"Error adding grade level: {str(e)}", "error")

    elif action == "remove_grade":
        grade_id = request.form.get("grade_id", type=int)
        if grade_id:
            try:
                execute_db(
                    "DELETE FROM school_grade_levels WHERE id = ? AND school_id = ?",
                    (grade_id, school_id)
                )
                flash("Grade level removed successfully.", "success")
            except Exception as e:
                flash(f"Error removing grade level: {str(e)}", "error")

    elif action == "add_subject":
        subject_name = request.form.get("new_subject", "").strip()
        if subject_name:
            try:
                existing = query_db(
                    "SELECT id FROM school_subjects WHERE school_id = ? AND LOWER(name) = LOWER(?)",
                    (school_id, subject_name)
                )
                if existing:
                    flash(f"Subject '{subject_name}' already exists.", "warning")
                else:
                    execute_db(
                        "INSERT INTO school_subjects (school_id, name) VALUES (?, ?)",
                        (school_id, subject_name)
                    )
                    grades = query_db(
                        "SELECT DISTINCT grade, section FROM students WHERE school_id = ? AND active = 1 AND grade IS NOT NULL AND grade != ''",
                        (school_id,)
                    )
                    grade_sections = {}
                    for row in grades:
                        g = row["grade"]
                        s = row.get("section")
                        if g not in grade_sections:
                            grade_sections[g] = set()
                        if s:
                            grade_sections[g].add(s)
                    for grade in grade_sections:
                        sections = grade_sections[grade]
                        if not sections:
                            sections = {None}
                        for section in sections:
                            try:
                                existing = query_db(
                                    "SELECT id FROM school_class_subjects WHERE school_id = ? AND grade_level = ? AND (section IS NULL AND ? IS NULL OR section = ?) AND subject = ?",
                                    (school_id, grade, section, section, subject_name)
                                )
                                if not existing:
                                    execute_db(
                                        "INSERT INTO school_class_subjects (school_id, grade_level, section, subject, sort_order) VALUES (?, ?, ?, ?, 0)",
                                        (school_id, grade, section, subject_name)
                                    )
                            except Exception:
                                pass
                    flash(f"Subject '{subject_name}' added successfully.", "success")
            except Exception as e:
                flash(f"Error adding subject: {str(e)}", "error")

    elif action == "remove_subject":
        subject_id = request.form.get("subject_id", type=int)
        if subject_id:
            try:
                execute_db(
                    "DELETE FROM school_subjects WHERE id = ? AND school_id = ?",
                    (subject_id, school_id)
                )
                execute_db(
                    "DELETE FROM school_class_subjects WHERE school_id = ? AND subject = (SELECT name FROM school_subjects WHERE id = ?)",
                    (school_id, subject_id)
                )
                flash("Subject removed successfully.", "success")
            except Exception as e:
                flash(f"Error removing subject: {str(e)}", "error")

    elif action == "assign_subject_to_class":
        grade_level = request.form.get("assign_grade", "").strip()
        section = request.form.get("assign_section", "").strip() or None
        subject = request.form.get("assign_subject", "").strip()
        if not grade_level or not subject:
            flash("Class/grade and subject are required.", "warning")
        else:
            try:
                existing = query_db(
                    "SELECT id FROM school_class_subjects WHERE school_id = ? AND grade_level = ? AND (section IS NULL AND ? IS NULL OR section = ?) AND subject = ?",
                    (school_id, grade_level, section, section, subject)
                )
                if existing:
                    flash(f"Subject '{subject}' is already assigned to {grade_level}{' Section ' + section if section else ''}.", "warning")
                else:
                    execute_db(
                        "INSERT INTO school_class_subjects (school_id, grade_level, section, subject, sort_order) VALUES (?, ?, ?, ?, 0)",
                        (school_id, grade_level, section, subject)
                    )
                    flash(f"Subject '{subject}' assigned to {grade_level}{' Section ' + section if section else ''} successfully.", "success")
            except Exception as e:
                flash(f"Error assigning subject: {str(e)}", "error")

    elif action == "remove_class_subject":
        class_subject_id = request.form.get("class_subject_id", type=int)
        if class_subject_id:
            try:
                execute_db(
                    "DELETE FROM school_class_subjects WHERE id = ? AND school_id = ?",
                    (class_subject_id, school_id)
                )
                flash("Subject removed from class successfully.", "success")
            except Exception as e:
                flash(f"Error removing subject from class: {str(e)}", "error")

    elif action == "save_email_settings":
        smtp_server = request.form.get("smtp_server", "").strip()
        smtp_port = request.form.get("smtp_port", type=int)
        smtp_email = request.form.get("smtp_email", "").strip()
        smtp_password = request.form.get("smtp_password", "").strip()
        sender_name = request.form.get("sender_name", "").strip()
        try:
            execute_db(
                "UPDATE schools SET smtp_server = ?, smtp_port = ?, smtp_email = ?, smtp_password = ?, sender_name = ? WHERE id = ?",
                (smtp_server, smtp_port, smtp_email, smtp_password, sender_name, school_id)
            )
            flash("Email settings updated successfully.", "success")
        except Exception:
            flash("Failed to save email settings. Columns may not exist in database yet.", "warning")

    elif action == "save_sms_settings":
        twilio_account_sid = request.form.get("twilio_account_sid", "").strip()
        twilio_auth_token = request.form.get("twilio_auth_token", "").strip()
        twilio_from_number = request.form.get("twilio_from_number", "").strip()
        twilio_messaging_service_sid = request.form.get("twilio_messaging_service_sid", "").strip()
        try:
            execute_db(
                "UPDATE schools SET twilio_account_sid = ?, twilio_auth_token = ?, twilio_from_number = ?, twilio_messaging_service_sid = ? WHERE id = ?",
                (twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, school_id)
            )
            flash("SMS settings updated successfully.", "success")
        except Exception:
            flash("Failed to save SMS settings. Columns may not exist in database yet.", "warning")

    elif action == "save_whatsapp_settings":
        whatsapp_access_token = request.form.get("whatsapp_access_token", "").strip()
        whatsapp_phone_number_id = request.form.get("whatsapp_phone_number_id", "").strip()
        try:
            execute_db(
                "UPDATE schools SET whatsapp_access_token = ?, whatsapp_phone_number_id = ? WHERE id = ?",
                (whatsapp_access_token, whatsapp_phone_number_id, school_id)
            )
            flash("WhatsApp settings updated successfully.", "success")
        except Exception:
            flash("Failed to save WhatsApp settings. Columns may not exist in database yet.", "warning")

    elif action == "save_general_settings":
        school_email = request.form.get("school_email", "").strip()
        school_phone = request.form.get("school_phone", "").strip()
        school_address = request.form.get("school_address", "").strip()
        school_website = request.form.get("school_website", "").strip()
        try:
            execute_db(
                "UPDATE schools SET school_email = ?, school_phone = ?, school_address = ?, school_website = ? WHERE id = ?",
                (school_email, school_phone, school_address, school_website, school_id)
            )
            flash("General settings updated successfully.", "success")
        except Exception:
            flash("Failed to save general settings. Columns may not exist in database yet.", "warning")

    if session.get("role") == ROLE_SUPERADMIN:
        return redirect(url_for("admin_settings", school_id=school_id))
    return redirect(url_for("admin_settings"))


@app.route("/students")
@login_required
@admin_required
def students():
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    if user_role == ROLE_SUPERADMIN:
        school_id = request.args.get("school_id", type=int)
        if school_id:
            students = query_db("SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id WHERE students.school_id = ? ORDER BY students.grade, students.section, students.name", (school_id,))
            grades = query_db("SELECT DISTINCT grade FROM students WHERE school_id = ? AND grade IS NOT NULL ORDER BY grade", (school_id,))
            sections = query_db("SELECT DISTINCT section FROM students WHERE school_id = ? AND section IS NOT NULL ORDER BY section", (school_id,))
            custom_sections = query_db("SELECT name FROM school_sections WHERE school_id = ? ORDER BY name", (school_id,))
            custom_grades = query_db("SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name", (school_id,))
        else:
            students = query_db("SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id ORDER BY students.grade, students.section, students.name")
            grades = query_db("SELECT DISTINCT grade FROM students WHERE grade IS NOT NULL ORDER BY grade")
            sections = query_db("SELECT DISTINCT section FROM students WHERE section IS NOT NULL ORDER BY section")
            custom_sections = []
            custom_grades = []
    else:
        students = query_db("SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id WHERE students.school_id = ? ORDER BY students.grade, students.section, students.name", (user_school_id,))
        grades = query_db("SELECT DISTINCT grade FROM students WHERE school_id = ? AND grade IS NOT NULL ORDER BY grade", (user_school_id,))
        sections = query_db("SELECT DISTINCT section FROM students WHERE school_id = ? AND section IS NOT NULL ORDER BY section", (user_school_id,))
        custom_sections = query_db("SELECT name FROM school_sections WHERE school_id = ? ORDER BY name", (user_school_id,))
        custom_grades = query_db("SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name", (user_school_id,))

    # Combine existing with custom
    grade_list = [g["grade"] for g in grades]
    for cg in custom_grades:
        if cg["name"] not in grade_list:
            grade_list.append(cg["name"])
    grades = [{"grade": g} for g in grade_list]

    section_list = [s["section"] for s in sections]
    for cs in custom_sections:
        if cs["name"] not in section_list:
            section_list.append(cs["name"])
    sections = [{"section": s} for s in section_list]

    return render_template("students.html", students=students, grades=grades, sections=sections)


@app.route("/view_student/<int:student_id>")
@login_required
def view_student(student_id):
    student = query_db("SELECT students.*, schools.school_code FROM students JOIN schools ON students.school_id = schools.id WHERE students.id = ?", (student_id,), one=True)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students"))
    
    # Get grades for this student
    grades_raw = query_db("SELECT subject, class_test, midterm_exam, class_score, final_exam, total_score, grade, remark, term, created_at FROM grades WHERE student_id = ? ORDER BY term DESC, subject", (student_id,))
    
    # Format grades for template
    grades = []
    for g in grades_raw:
        # Use total_score as the score, assume max is 100
        grades.append({
            'subject': g['subject'],
            'score': g['total_score'] if g['total_score'] is not None else 0,
            'max_score': 100,
            'term': g['term'],
            'created_at': g['created_at'],
            'grade': g['grade'],  # Keep the letter grade if needed elsewhere
            'remark': g['remark']
        })
    
    # Get attendances for this student (no created_at column in attendances table)
    attendances = query_db("SELECT date, status FROM attendances WHERE student_id = ? ORDER BY date DESC", (student_id,))
    
    # Calculate attendance statistics
    present_count = len([a for a in attendances if a['status'] == 'present']) if attendances else 0
    absent_count = len([a for a in attendances if a['status'] == 'absent']) if attendances else 0
    
    return render_template("view_student.html", student=student, grades=grades, attendances=attendances, present_count=present_count, absent_count=absent_count)


@app.route("/admin/edit_student/<int:student_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_student(student_id):
    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students"))

    if session.get("role") != ROLE_SUPERADMIN and student["school_id"] != session.get("school_id"):
        flash("You can only edit students from your own school.", "warning")
        return redirect(url_for("students"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_number = request.form.get("student_number", "").strip()
        grade = request.form.get("grade", "").strip()
        section = request.form.get("section", "").strip()
        email = request.form.get("email", "").strip()
        date_of_birth = request.form.get("date_of_birth", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        address = request.form.get("address", "").strip() or None
        guardian_name = request.form.get("guardian_name", "").strip() or None
        emergency_contact = request.form.get("emergency_contact", "").strip() or None
        allergies = request.form.get("allergies", "").strip() or None
        blood_group = request.form.get("blood_group", "").strip() or None
        medical_notes = request.form.get("medical_notes", "").strip() or None
        parent_name = request.form.get("parent_name", "").strip() or None
        parent_contact = request.form.get("parent_contact", "").strip() or None
        parent_email = request.form.get("parent_email", "").strip() or None
        parent_user_id = request.form.get("parent_user_id", "").strip() or None
        active = 1 if request.form.get("active") == "1" else 0

        if not name or not student_number:
            flash("Student name and number are required.", "warning")
            return redirect(url_for("edit_student", student_id=student_id))

        existing = query_db(
            "SELECT id FROM students WHERE student_number = ? AND id != ?",
            (student_number, student_id),
            one=True,
        )
        if existing:
            flash("Student number already exists. Please use a different number.", "warning")
            return redirect(url_for("edit_student", student_id=student_id))

        query_db(
            """
            UPDATE students
            SET name = ?, student_number = ?, grade = ?, section = ?, email = ?,
                date_of_birth = ?, gender = ?, address = ?, parent_name = ?,
                parent_contact = ?, parent_email = ?, guardian_name = ?,
                emergency_contact = ?, allergies = ?, blood_group = ?,
                medical_notes = ?, active = ?, parent_user_id = ?
            WHERE id = ?
            """,
            (
                name, student_number, grade, section, email,
                date_of_birth, gender, address, parent_name,
                parent_contact, parent_email, guardian_name,
                emergency_contact, allergies, blood_group,
                medical_notes, active, parent_user_id, student_id,
            ),
            commit=True,
        )
        flash(f"Student {name} updated successfully.", "success")
        return redirect(url_for("view_student", student_id=student_id))

    if session.get("role") == ROLE_SUPERADMIN:
        schools = query_db("SELECT * FROM schools ORDER BY name")
    else:
        schools = query_db("SELECT * FROM schools WHERE id = ? ORDER BY name", (session.get("school_id"),))
    parent_users = query_db(
        "SELECT id, name, email, login_code FROM users WHERE school_id = ? AND role = ? AND active = 1 ORDER BY name",
        (student["school_id"], ROLE_PARENT),
    )
    return render_template("admin/edit_student.html", student=student, schools=schools, parent_users=parent_users)


@app.route("/admin/delete_student/<int:student_id>", methods=["POST"])
@login_required
@admin_required
def delete_student(student_id):
    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students"))

    if session.get("role") != ROLE_SUPERADMIN and student["school_id"] != session.get("school_id"):
        flash("You can only deactivate students from your own school.", "warning")
        return redirect(url_for("students"))

    query_db("UPDATE students SET active = 0 WHERE id = ?", (student_id,), commit=True)
    flash(f"Student {student['name']} has been deactivated.", "success")
    return redirect(url_for("students"))


@app.route("/admin/restore_student/<int:student_id>", methods=["POST"])
@login_required
@admin_required
def restore_student(student_id):
    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students"))

    if session.get("role") != ROLE_SUPERADMIN and student["school_id"] != session.get("school_id"):
        flash("You can only restore students from your own school.", "warning")
        return redirect(url_for("students"))

    query_db("UPDATE students SET active = 1 WHERE id = ?", (student_id,), commit=True)
    flash(f"Student {student['name']} has been restored.", "success")
    return redirect(url_for("students"))


@app.route("/admin/create_user", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    if request.method == "GET":
        return render_template("admin/create_user.html")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", ROLE_TEACHER)
    school_id = request.form.get("school_id")
    login_code = request.form.get("login_code", "").strip()
    privileges_list = request.form.getlist("privileges")
    privileges = ",".join(privileges_list) if privileges_list else ""

    # Prevent creating students through this form - use dedicated student creation form
    if role == ROLE_STUDENT:
        flash("Student creation is not allowed through this form. Please use the dedicated 'Create a New Student' section below.", "danger")
        return redirect(url_for("admin_panel"))

    if role == ROLE_SUPERADMIN and session.get("role") != ROLE_SUPERADMIN:
        flash("Only super admin can create a super admin account.", "warning")
        return redirect(url_for("admin_panel"))

    # For non-superadmin, force school_id to be the admin's school (prevent cross-school assignment)
    if session.get("role") != ROLE_SUPERADMIN:
        school_id = session.get("school_id")
    else:
        # Superadmin must select a school for non-superadmin users
        if not school_id and role != ROLE_SUPERADMIN:
            flash("School is required for this user type.", "warning")
            return redirect(url_for("admin_panel"))

    if not name or not login_code:
        flash("Name and login code are required.", "warning")
        return redirect(url_for("admin_panel"))

    existing = query_db("SELECT id FROM users WHERE login_code = ?", (login_code,), one=True)
    if existing:
        flash("Login code already exists. Choose a different code.", "warning")
        return redirect(url_for("admin_panel"))

    query_db(
        "INSERT INTO users (name, email, role, school_id, login_code, password_hash, privileges) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, email, role, school_id, login_code, generate_password_hash(login_code), privileges),
        commit=True,
    )
    
    # Get the newly created user ID
    new_user = query_db("SELECT id FROM users WHERE login_code = ?", (login_code,), one=True)
    
    # If role is teacher, create teacher assignment
    if role == ROLE_TEACHER and new_user:
        grade = request.form.get("assign_grade", "").strip() or None
        section = request.form.get("assign_section", "").strip() or None
        subject = request.form.get("assign_subject", "").strip() or None
        responsibility = request.form.get("assign_responsibility", "").strip()
        is_primary = 1 if request.form.get("assign_is_primary") else 0
        
        if responsibility:
            # Check for duplicate assignment
            existing_assignment = query_db(
                "SELECT id FROM teacher_assignments WHERE teacher_id = ? AND grade = ? AND section = ? AND subject = ? AND active = 1",
                (new_user["id"], grade, section, subject),
                one=True,
            )
            if not existing_assignment:
                query_db(
                    """
                    INSERT INTO teacher_assignments
                    (teacher_id, school_id, grade, section, subject, responsibility, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_user["id"], school_id, grade, section, subject, responsibility, is_primary),
                    commit=True,
                )
    
    flash(f"User {name} created successfully.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user_to_delete = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user_to_delete:
        flash("User not found.", "danger")
        return redirect(url_for("admin_panel"))
    
    if user_to_delete["id"] == session.get("user_id"):
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin_panel"))
    
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    if user_role == ROLE_ADMIN and user_to_delete["school_id"] != user_school_id:
        flash("You can only delete users from your own school.", "warning")
        return redirect(url_for("admin_panel"))
    
    if user_to_delete["role"] == ROLE_SUPERADMIN and user_role != ROLE_SUPERADMIN:
        flash("Only superadmin can delete superadmin accounts.", "warning")
        return redirect(url_for("admin_panel"))
    
    query_db("UPDATE users SET active = 0 WHERE id = ?", (user_id,), commit=True)
    flash("User " + user_to_delete["name"] + " has been deactivated.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/restore_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def restore_user(user_id):
    user_to_restore = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user_to_restore:
        flash("User not found.", "danger")
        return redirect(url_for("admin_panel"))
    
    # Check school access for admins
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    if user_role == ROLE_ADMIN and user_to_restore["school_id"] != user_school_id:
        flash("You can only restore users from your own school.", "warning")
        return redirect(url_for("admin_panel"))
    
    query_db("UPDATE users SET active = 1 WHERE id = ?", (user_id,), commit=True)
    flash("User " + user_to_restore["name"] + " has been restored.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_multiple_users", methods=["POST"])
@login_required
@admin_required
def delete_multiple_users():
    user_ids = request.form.getlist('user_ids')
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    if not user_ids:
        flash("No users selected.", "warning")
        return redirect(url_for("admin_panel"))
    
    # Prevent self-deletion
    if str(session.get("user_id")) in user_ids:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin_panel"))
    
    deactivated_count = 0
    for user_id in user_ids:
        user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
        if user:
            # Check permissions
            if user_role == ROLE_ADMIN and user["school_id"] != user_school_id:
                continue
            if user["role"] == ROLE_SUPERADMIN and user_role != ROLE_SUPERADMIN:
                continue
            
            query_db("UPDATE users SET active = 0 WHERE id = ?", (user_id,), commit=True)
            deactivated_count += 1
    
    flash(f"{deactivated_count} user(s) deactivated successfully.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/restore_multiple_users", methods=["POST"])
@login_required
@admin_required
def restore_multiple_users():
    user_ids = request.form.getlist('user_ids')
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    if not user_ids:
        flash("No users selected.", "warning")
        return redirect(url_for("admin_panel"))
    
    restored_count = 0
    for user_id in user_ids:
        user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
        if user:
            # Check permissions
            if user_role == ROLE_ADMIN and user["school_id"] != user_school_id:
                continue
            if user["role"] == ROLE_SUPERADMIN and user_role != ROLE_SUPERADMIN:
                continue
            
            query_db("UPDATE users SET active = 1 WHERE id = ?", (user_id,), commit=True)
            restored_count += 1
    
    flash(f"{restored_count} user(s) restored successfully.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/edit_user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin_panel"))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", user["role"])
        login_code = request.form.get("login_code", "").strip()
        privileges_list = request.form.getlist("privileges")
        privileges = ",".join(privileges_list) if privileges_list else ""
        
        # Prevent changing to student role - students are created separately
        if role == ROLE_STUDENT:
            flash("Cannot change user role to student. Students must be created through the student registration form.", "danger")
            return redirect(url_for("edit_user", user_id=user_id))
        
        # Prevent non-superadmins from creating superadmins
        if role == ROLE_SUPERADMIN and session.get("role") != ROLE_SUPERADMIN:
            flash("Only super admin can create a super admin account.", "warning")
            return redirect(url_for("admin_panel"))
        
        # Prevent non-superadmins from editing superadmins
        if user["role"] == ROLE_SUPERADMIN and session.get("role") != ROLE_SUPERADMIN:
            flash("Only super admin can edit super admin accounts.", "warning")
            return redirect(url_for("admin_panel"))
        
        if not name or not login_code:
            flash("Name and login code are required.", "warning")
            return redirect(url_for("edit_user", user_id=user_id))
        
        # Check if login code is being changed to an existing one
        if login_code != user["login_code"]:
            existing = query_db("SELECT id FROM users WHERE login_code = ? AND id != ?", (login_code, user_id), one=True)
            if existing:
                flash("Login code already exists. Choose a different code.", "warning")
                return redirect(url_for("edit_user", user_id=user_id))
        
        query_db(
            """UPDATE users 
               SET name = ?, email = ?, role = ?, login_code = ?, privileges = ? 
               WHERE id = ?""",
            (name, email, role, login_code, privileges, user_id),
            commit=True,
        )
        flash(f"User {name} updated successfully.", "success")
        return redirect(url_for("admin_panel"))
    
    # GET request - show edit form
    schools = query_db("SELECT * FROM schools ORDER BY name")
    return render_template("edit_user.html", user=user, schools=schools)


@app.route("/admin/view_teacher/<int:user_id>")
@login_required
@admin_required
def view_teacher(user_id):
    # Get teacher details
    teacher = query_db("SELECT * FROM users WHERE id = ? AND role = 'teacher'", (user_id,), one=True)
    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect(url_for("admin_panel"))
    
    # Get teacher's assignments
    teacher_assignments = query_db(
        """
        SELECT ta.*, u.name AS teacher_name
        FROM teacher_assignments ta
        JOIN users u ON ta.teacher_id = u.id
        WHERE ta.teacher_id = ? AND ta.active = 1
        ORDER BY ta.grade, ta.section, ta.subject
        """,
        (user_id,),
    )
    
    # Get assignments created by this teacher
    created_assignments = query_db(
        """
        SELECT a.*, u.name AS teacher_name
        FROM assignments a
        JOIN users u ON a.assigned_by = u.id
        WHERE a.assigned_by = ? AND a.is_active = 1
        ORDER BY a.due_date ASC
        """,
        (user_id,),
    )
    
    return render_template(
        "view_teacher.html",
        teacher=teacher,
        teacher_assignments=teacher_assignments,
        created_assignments=created_assignments,
    )


@app.route("/admin/create_student", methods=["GET", "POST"])
@login_required
@admin_required
def create_student():
    if request.method == "GET":
        # GET request - show create student form
        user_role = session.get("role")
        user_school_id = session.get("school_id")

        if user_role == ROLE_SUPERADMIN:
            schools = query_db("SELECT * FROM schools ORDER BY name")
            school_id = request.args.get("school_id", type=int)
        else:
            schools = query_db("SELECT * FROM schools WHERE id = ? ORDER BY name", (user_school_id,))
            school_id = user_school_id

        # Get school-specific sections and grade levels for dropdown
        if school_id:
            try:
                custom_sections = query_db("SELECT name FROM school_sections WHERE school_id = ? ORDER BY name", (school_id,))
            except Exception:
                custom_sections = []
            try:
                custom_grades = query_db("SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name", (school_id,))
            except Exception:
                custom_grades = []
        else:
            custom_sections = []
            custom_grades = []
        parent_users = query_db(
            "SELECT id, name, email, login_code FROM users WHERE school_id = ? AND role = ? AND active = 1 ORDER BY name",
            (school_id, ROLE_PARENT),
        ) if school_id else []
        return render_template("admin/create_student.html", schools=schools, school_id=school_id, custom_sections=custom_sections, custom_grades=custom_grades, parent_users=parent_users)
    name = request.form.get("name", "").strip()
    student_number = request.form.get("student_number", "").strip()
    school_id = request.form.get("school_id")
    grade = request.form.get("grade", "").strip()
    section = request.form.get("section", "").strip()
    email = request.form.get("email", "").strip()
    
    # New comprehensive fields
    date_of_birth = request.form.get("date_of_birth", "").strip() or None
    gender = request.form.get("gender", "").strip() or None
    address = request.form.get("address", "").strip() or None

    guardian_name = request.form.get("guardian_name", "").strip() or None
    emergency_contact = request.form.get("emergency_contact", "").strip() or None
    allergies = request.form.get("allergies", "").strip() or None
    blood_group = request.form.get("blood_group", "").strip() or None
    medical_notes = request.form.get("medical_notes", "").strip() or None
    parent_name = request.form.get("parent_name", "").strip() or None
    parent_contact = request.form.get("parent_contact", "").strip() or None
    parent_email = request.form.get("parent_email", "").strip() or None
    parent_user_id = request.form.get("parent_user_id", "").strip() or None
    active = 1 if request.form.get("active") == "1" else 0

    if not name or not student_number or not school_id:
        flash("Student name, number, and school are required.", "warning")
        return redirect(url_for("admin_panel"))
    
    existing = query_db("SELECT id FROM students WHERE student_number = ?", (student_number,), one=True)
    if existing:
        flash("Student number already exists. Please use a different number.", "warning")
        return redirect(url_for("admin_panel"))
 
    query_db(
         """
         INSERT INTO students (
             name, student_number, school_id, grade, section, email,
             date_of_birth, gender, address, parent_name, parent_contact, parent_email,
             guardian_name, emergency_contact, allergies, blood_group, medical_notes,
             parent_user_id
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         """,
         (
             name, student_number, school_id, grade, section, email,
             date_of_birth, gender, address, parent_name, parent_contact, parent_email,
             guardian_name, emergency_contact, allergies, blood_group, medical_notes,
             parent_user_id,
         ),
         commit=True,
     )
    flash(f"Student {name} created successfully.", "success")
    return redirect(url_for("admin_panel"))


# New Feature Routes

@app.route("/announcements")
@login_required
def announcements():
    school_id = session.get("school_id")
    user_role = session.get("role")

    # Filter announcements based on user role and target audience
    if user_role == ROLE_TEACHER:
        target_filter = "target_audience IN ('all', 'teachers')"
    elif user_role == ROLE_PARENT:
        target_filter = "target_audience IN ('all', 'parents')"
    else:
        target_filter = "1=1"  # Admins and superadmins see all
    
    announcements = query_db(
        f"""
        SELECT a.*, u.name AS creator_name
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.school_id = ? AND a.is_active = 1 AND ({target_filter})
        ORDER BY
            CASE a.priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            a.created_at DESC
        """,
        (school_id,)
    )
    print(f"DEBUG announcements: found {len(announcements) if announcements else 0} for school_id={school_id}")

    return render_template("announcements.html", announcements=announcements)


@app.route("/events")
@login_required
def events():
    school_id = session.get("school_id")
    events = query_db(
        """
        SELECT e.*, u.name AS creator_name
        FROM events e
        JOIN users u ON e.created_by = u.id
        WHERE e.school_id = ? AND e.is_active = 1
        ORDER BY e.event_date ASC, e.start_time ASC
        """,
        (school_id,)
    )

    return render_template("events.html", events=events)


@app.route("/announcements/create", methods=["GET", "POST"])
@login_required
def create_announcement():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        target_audience = request.form.get("target_audience", "all")
        priority = request.form.get("priority", "normal")
        expires_at = request.form.get("expires_at", "").strip()
        delivery_method = request.form.get("delivery_method", "app")
        
        if not title or not content:
            flash("Title and content are required.", "danger")
            return render_template("create_announcement.html")
        
        school_id = session.get("school_id")
        user_id = session.get("user_id")
        
        query_db(
            """INSERT INTO announcements 
               (title, content, school_id, created_by, target_audience, priority, expires_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, content, school_id, user_id, target_audience, priority, 
             expires_at if expires_at else None),
            commit=True
        )
        
        # Verify insert
        verify = query_db("SELECT id, title FROM announcements WHERE school_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1", (school_id,), one=True)
        print(f"Created announcement: {verify}")
        
        # Handle all delivery methods
        results = {"errors": []}
        
        if delivery_method in ("email", "all"):
            sender_name = query_db("SELECT name FROM users WHERE id = ?", (user_id,), one=True)
            sender_name = sender_name["name"] if sender_name else "School Administration"
            summary = f"*{title}*\n\n{content}"
            if target_audience == "all":
                summary += f"\n\nAudience: All students, teachers, and parents"
            elif target_audience == "students":
                summary += f"\n\nAudience: Students"
            elif target_audience == "teachers":
                summary += f"\n\nAudience: Teachers"
            elif target_audience == "parents":
                summary += f"\n\nAudience: Parents"
            
            users = query_db("SELECT id, name, email FROM users WHERE school_id = ? AND active = 1", (school_id,))
            for u in users:
                if u.get("email"):
                    send_email(u["email"], title, summary, sender_name=sender_name)

        if delivery_method in ("whatsapp", "all"):
            students = query_db("SELECT s.parent_contact FROM students s WHERE s.school_id = ? AND s.active = 1 AND s.parent_contact IS NOT NULL AND s.parent_contact != ''", (school_id,))
            for student in students:
                phone = student.get("parent_contact")
                if phone:
                    data = {
                        "messaging_product": "whatsapp",
                        "to": normalize_phone_number(phone),
                        "type": "text",
                        "text": {"preview_url": False, "body": f"{title}\n\n{content}"},
                    }
                    success, error = send_whatsapp_api_message(data)
                    if not success:
                        results["errors"].append(f"WhatsApp failed for {phone}: {error}")
                        print(f"WhatsApp error for {phone}: {error}")

        if delivery_method in ("text", "all"):
            students = query_db("SELECT s.parent_contact FROM students s WHERE s.school_id = ? AND s.active = 1 AND s.parent_contact IS NOT NULL AND s.parent_contact != ''", (school_id,))
            for student in students:
                sent, error = send_text_message(student["parent_contact"], f"{title}\n\n{content}")
                if not sent:
                    results["errors"].append(f"SMS failed for {student['parent_contact']}: {error}")

        if delivery_method in ("app", "all"):
            all_users = query_db("SELECT id FROM users WHERE school_id = ? AND active = 1", (school_id,))
            for u in all_users:
                query_db(
                    "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
                    (user_id, u["id"], school_id, title, content, "app"),
                    commit=True,
                )
        
        if results["errors"]:
            for error in results["errors"]:
                flash(error, "warning")
        
        flash("Announcement created successfully.", "success")
        return redirect(url_for("announcements"))
    
    return render_template("create_announcement.html")


@app.route("/announcements/delete/<int:announcement_id>", methods=["POST"])
@login_required
@admin_required
def delete_announcement(announcement_id):
    announcement = query_db("SELECT * FROM announcements WHERE id = ?", (announcement_id,), one=True)
    if not announcement:
        flash("Announcement not found.", "danger")
        return redirect(url_for("announcements"))
    if session.get("role") != ROLE_SUPERADMIN and announcement["school_id"] != session.get("school_id"):
        flash("You can only delete announcements from your own school.", "warning")
        return redirect(url_for("announcements"))
    query_db("UPDATE announcements SET is_active = 0 WHERE id = ?", (announcement_id,), commit=True)
    flash("Announcement deleted successfully.", "success")
    return redirect(url_for("announcements"))


@app.route("/events/create", methods=["GET", "POST"])
@login_required
def create_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        location = request.form.get("location", "").strip()
        event_type = request.form.get("event_type", "general")
        delivery_method = request.form.get("delivery_method", "app")
        
        if not title or not event_date:
            flash("Title and event date are required.", "danger")
            return render_template("create_event.html")
        
        school_id = session.get("school_id")
        user_id = session.get("user_id")
        
        query_db(
            """INSERT INTO events 
               (title, description, school_id, created_by, event_date, start_time, end_time, location, event_type) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, school_id, user_id, event_date, 
             start_time if start_time else None,
             end_time if end_time else None,
             location if location else None, event_type),
            commit=True
        )
        
        results = {"errors": []}

        if delivery_method in ("email", "all"):
            sender_name = query_db("SELECT name FROM users WHERE id = ?", (user_id,), one=True)
            sender_name = sender_name["name"] if sender_name else "School Administration"
            location_text = f"\nLocation: {location}" if location else ""
            message_text = f"*{title}*\nDate: {event_date}\n{location_text}\n\n{description if description else ''}"
            users = query_db("SELECT id, name, email FROM users WHERE school_id = ? AND active = 1", (school_id,))
            for u in users:
                if u.get("email"):
                    send_email(u["email"], title, message_text, sender_name=sender_name)

        if delivery_method in ("whatsapp", "all"):
            students = query_db("SELECT s.parent_contact FROM students s WHERE s.school_id = ? AND s.active = 1 AND s.parent_contact IS NOT NULL AND s.parent_contact != ''", (school_id,))
            for student in students:
                phone = student.get("parent_contact")
                if phone:
                    data = {
                        "messaging_product": "whatsapp",
                        "to": normalize_phone_number(phone),
                        "type": "text",
                        "text": {"preview_url": False, "body": f"{title}\n\n{message_text}"},
                    }
                    success, error = send_whatsapp_api_message(data)
                    if not success:
                        results["errors"].append(f"WhatsApp failed for {phone}: {error}")

        if delivery_method in ("text", "all"):
            students = query_db("SELECT s.parent_contact FROM students s WHERE s.school_id = ? AND s.active = 1 AND s.parent_contact IS NOT NULL AND s.parent_contact != ''", (school_id,))
            for student in students:
                phone = student.get("parent_contact")
                if phone:
                    send_text_message(phone, message_text)

        if delivery_method in ("app", "all"):
            all_users = query_db("SELECT id FROM users WHERE school_id = ? AND active = 1", (school_id,))
            for u in all_users:
                query_db(
                    "INSERT INTO messages (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
                    (user_id, u["id"], school_id, title, description or title, "app"),
                    commit=True,
                )
        
        if results["errors"]:
            for error in results["errors"]:
                flash(error, "warning")
        
        flash("Event created successfully.", "success")
        return redirect(url_for("events"))
    
    return render_template("create_event.html")


@app.route("/events/delete/<int:event_id>", methods=["POST"])
@login_required
@admin_required
def delete_event(event_id):
    event = query_db("SELECT * FROM events WHERE id = ?", (event_id,), one=True)
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("events"))
    if session.get("role") != ROLE_SUPERADMIN and event["school_id"] != session.get("school_id"):
        flash("You can only delete events from your own school.", "warning")
        return redirect(url_for("events"))
    query_db("UPDATE events SET is_active = 0 WHERE id = ?", (event_id,), commit=True)
    flash("Event deleted successfully.", "success")
    return redirect(url_for("events"))
    
    return render_template("create_event.html")


def _assignment_recipient_query(school_id, grade=None, section=None):
    student_columns = has_table_columns("students", {"parent_user_id"})
    parent_user_column = "s.parent_user_id" if "parent_user_id" in student_columns else "NULL AS parent_user_id"
    query = (
        f"SELECT s.id, s.name, s.parent_email, s.parent_contact, {parent_user_column} "
        "FROM students s "
        "WHERE s.school_id = ? AND s.active = 1 "
        "AND (s.parent_email IS NOT NULL AND s.parent_email != '' "
        "OR s.parent_contact IS NOT NULL AND s.parent_contact != ''"
    )
    args = [school_id]
    if "parent_user_id" in student_columns:
        query += " OR s.parent_user_id IS NOT NULL"
    query += ")"
    if grade:
        query += " AND s.grade = ?"
        args.append(grade)
    if section:
        query += " AND s.section = ?"
        args.append(section)
    return query, tuple(args)


def _build_assignment_message(assignment, sender_name):
    target_grade = assignment.get("grade")
    target_section = assignment.get("section")
    class_label = ", ".join([v for v in [target_grade, target_section] if v]) or "Whole School"
    message_body = (
        f"Assignment: {assignment['title']}\n"
        f"Subject: {assignment.get('subject') or 'Not specified'}\n"
        f"Class: {class_label}\n"
        f"Due Date: {assignment['due_date']}"
    )
    if assignment.get("description"):
        message_body += f"\n\nDescription:\n{assignment['description']}"
    message_body += f"\n\nBest regards,\n{sender_name}"
    return message_body


def _send_assignment_notifications(assignment, sender_name, delivery_method):
    students, args = _assignment_recipient_query(
        assignment["school_id"],
        assignment.get("grade"),
        assignment.get("section"),
    )
    students = query_db(students, args)
    results = {
        "students": len(students),
        "app": 0,
        "email": 0,
        "whatsapp": 0,
        "app_skipped": 0,
        "email_skipped": 0,
        "whatsapp_skipped": 0,
        "errors": [],
    }

    if not students:
        results["errors"].append("No students matched this assignment.")
        return results

    if delivery_method in ("app", "all"):
        for student in students:
            parent_user_id = student.get("parent_user_id")
            if not parent_user_id:
                results["app_skipped"] += 1
                continue
            try:
                query_db(
                    """
                    INSERT INTO messages
                        (sender_id, recipient_id, school_id, subject, body, read_at, delivery_method, student_id, external_recipient_name)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
                    """,
                    (
                        session.get("user_id"),
                        parent_user_id,
                        assignment["school_id"],
                        f"Assignment: {assignment['title']}",
                        _build_assignment_message(assignment, sender_name),
                        "app",
                        student["id"],
                        student.get("name") or "Parent",
                    ),
                    commit=True,
                )
                results["app"] += 1
            except Exception as exc:
                results["errors"].append(f"App message failed for {student.get('name')}: {exc}")

    if delivery_method in ("email", "all"):
        for student in students:
            parent_email = (student.get("parent_email") or "").strip()
            if not parent_email:
                results["email_skipped"] += 1
                continue
            success, error = send_email(
                parent_email,
                f"Assignment: {assignment['title']}",
                _build_assignment_message(assignment, sender_name),
                sender_name=sender_name,
            )
            if success:
                results["email"] += 1
            else:
                results["errors"].append(f"Email failed for {parent_email}: {error}")

    if delivery_method in ("whatsapp", "all"):
        if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            results["whatsapp_skipped"] = sum(1 for student in students if (student.get("parent_contact") or "").strip())
            results["errors"].append("WhatsApp Business API is not configured.")
        else:
            for student in students:
                phone = (student.get("parent_contact") or "").strip()
                if not phone:
                    results["whatsapp_skipped"] += 1
                    continue
                data = {
                    "messaging_product": "whatsapp",
                    "to": normalize_phone_number(phone),
                    "type": "text",
                    "text": {"preview_url": False, "body": _build_assignment_message(assignment, sender_name)},
                }
                success, error = send_whatsapp_api_message(data)
                if success:
                    results["whatsapp"] += 1
                else:
                    results["errors"].append(f"WhatsApp failed for {phone}: {error}")

    return results


def _assignment_results_flash(title, results):
    parts = [
        f"Assignment '{title}' created.",
        f"Matched students: {results['students']}.",
        f"App messages: {results['app']}",
        f"Emails: {results['email']}",
        f"WhatsApp: {results['whatsapp']}",
    ]
    if results["app_skipped"] or results["email_skipped"] or results["whatsapp_skipped"]:
        parts.append(
            "Skipped contacts: "
            f"app {results['app_skipped']}, email {results['email_skipped']}, WhatsApp {results['whatsapp_skipped']}."
        )
    if results["errors"]:
        flash(" ".join(parts) + " Issues: " + " | ".join(results["errors"][:3]), "warning")
    else:
        flash(" ".join(parts), "success")


@app.route("/assignments")
@login_required
def assignments():
    school_id = session.get("school_id")
    user_role = session.get("role")
    
    # Teachers and admins see all assignments
    assignments = query_db(
        """
        SELECT a.*, u.name AS teacher_name
        FROM assignments a
        LEFT JOIN users u ON a.assigned_by = u.id
        WHERE a.school_id = ? AND a.is_active = 1
        ORDER BY a.due_date ASC
        """,
        (school_id,)
    )
    
    # Fetch grades and sections for the assignment creation form
    grades = query_db(
        "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
        (school_id,),
    )
    sections = query_db(
        "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
        (school_id,),
    )
    # Fetch subjects from settings
    school_subjects = []
    try:
        school_subjects = query_db(
            "SELECT name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        seen = set()
        unique_subjects = []
        for s in (school_subjects or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_subjects.append(s)
        school_subjects = unique_subjects
    except Exception:
        pass

    return render_template("assignments.html", assignments=assignments, grades=grades, sections=sections, school_subjects=school_subjects)


@app.route("/assignments/create", methods=["GET", "POST"])
@login_required
def create_assignment():
    if request.method == "GET":
        school_id = session.get("school_id")
        grades = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,),
        )
        sections = query_db(
            "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,),
        )
        school_subjects = []
        try:
            school_subjects = query_db(
                "SELECT name FROM school_subjects WHERE school_id = ? ORDER BY name",
                (school_id,)
            )
            seen = set()
            unique_subjects = []
            for s in (school_subjects or []):
                name = s.get("name")
                if name not in seen:
                    seen.add(name)
                    unique_subjects.append(s)
            school_subjects = unique_subjects
        except Exception:
            pass
        return render_template("create_assignment.html", grades=grades, sections=sections, school_subjects=school_subjects)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    subject = request.form.get("subject", "").strip()
    grade = request.form.get("grade", "").strip() or None
    section = request.form.get("section", "").strip() or None
    due_date = request.form.get("due_date", "").strip()
    delivery_method = request.form.get("delivery_method", "app")
    
    if not title or not subject or not due_date:
        flash("Title, subject, and due date are required.", "warning")
        return redirect(url_for("assignments"))
    
    assigned_by = session.get("user_id")
    school_id = session.get("school_id")
    
    user = query_db("SELECT * FROM users WHERE id = ?", (assigned_by,), one=True)
    if not user or user["role"] not in [ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPERADMIN]:
        flash("Only teachers and admins can create assignments.", "danger")
        return redirect(url_for("assignments"))
    
    file_path = None
    file_name = None
    uploaded = request.files.get("assignment_file")
    if uploaded and uploaded.filename != "":
        if not _allowed_file(uploaded.filename, ALLOWED_ASSIGNMENT_EXTENSIONS):
            flash("Invalid file type. Allowed: PDF, DOC, DOCX, TXT, ZIP, RAR.", "danger")
            return redirect(url_for("assignments"))
        _ensure_upload_dirs()
        ext = uploaded.filename.rsplit(".", 1)[1].lower()
        file_name = f"assignment_{secure_filename(uploaded.filename)}"
        file_path = f"uploads/{file_name}"
        uploaded.save(os.path.join(UPLOAD_FOLDER, file_name))
    
    query_db(
        """
        INSERT INTO assignments
        (title, description, subject, grade, section, school_id, assigned_by, due_date, file_path, file_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title, description, subject, grade, section, school_id, assigned_by, due_date, file_path, file_name),
        commit=True,
    )
    
    if delivery_method in ("email", "whatsapp", "all"):
        sender_name = user["name"]
        target_grade = grade
        target_section = section
        class_label = ", ".join([v for v in [target_grade, target_section] if v]) or "Whole School"
        message_body = (
            f"New Assignment: {title}\n"
            f"Subject: {subject}\n"
            f"Class: {class_label}\n"
            f"Due Date: {due_date}"
        )
        if description:
            message_body += f"\n\nDescription:\n{description}"
        message_body += f"\n\nBest regards,\n{sender_name}"

        student_query = (
            "SELECT DISTINCT s.parent_email, s.parent_contact "
            "FROM students s "
            "WHERE s.school_id = ? AND s.active = 1 "
            "AND (s.parent_email IS NOT NULL AND s.parent_email != '' "
            "OR s.parent_contact IS NOT NULL AND s.parent_contact != '')"
        )
        student_args: list = [school_id]
        if target_grade:
            student_query += " AND s.grade = ?"
            student_args.append(target_grade)
        if target_section:
            student_query += " AND s.section = ?"
            student_args.append(target_section)

        students = query_db(student_query, tuple(student_args))

        if delivery_method in ("email", "all"):
            for student in students:
                parent_email = (student.get("parent_email") or "").strip()
                if parent_email:
                    send_email(parent_email, f"Assignment: {title}", message_body, sender_name=sender_name)

        if delivery_method in ("whatsapp", "all"):
            for student in students:
                phone = (student.get("parent_contact") or "").strip()
                if phone:
                    data = {
                        "messaging_product": "whatsapp",
                        "to": normalize_phone_number(phone),
                        "type": "text",
                        "text": {"preview_url": False, "body": message_body},
                    }
                    send_whatsapp_api_message(data)

    flash(f"Assignment '{title}' created and sent successfully.", "success")
    return redirect(url_for("assignments"))


@app.route("/assignments/download/<int:assignment_id>")
@login_required
def download_assignment_file(assignment_id):
    assignment = query_db("SELECT * FROM assignments WHERE id = ?", (assignment_id,), one=True)
    if not assignment or not assignment.get("file_path"):
        flash("File not available.", "warning")
        return redirect(url_for("assignments"))
    rel = assignment["file_path"]
    folder, filename = os.path.split(rel)
    abs_folder = os.path.join(BASE_DIR, "static", folder)
    return send_from_directory(abs_folder, filename, as_attachment=True, download_name=assignment.get("file_name") or filename)


@app.route("/assignments/send/<int:assignment_id>", methods=["POST"])
@login_required
def send_assignment(assignment_id):
    delivery_method = request.form.get("delivery_method", "all")

    assignment = query_db("SELECT * FROM assignments WHERE id = ?", (assignment_id,), one=True)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("assignments"))

    school_id = assignment["school_id"]
    if session.get("role") != ROLE_SUPERADMIN and school_id != session.get("school_id"):
        flash("You can only send assignments from your own school.", "warning")
        return redirect(url_for("assignments"))

    user = query_db("SELECT * FROM users WHERE id = ?", (session.get("user_id"),), one=True)
    sender_name = user["name"] if user else "School Administration"

    target_grade = assignment.get("grade")
    target_section = assignment.get("section")
    class_label = ", ".join([v for v in [target_grade, target_section] if v]) or "Whole School"

    message_body = (
        f"Assignment: {assignment['title']}\n"
        f"Subject: {assignment['subject']}\n"
        f"Class: {class_label}\n"
        f"Due Date: {assignment['due_date']}"
    )
    if assignment.get("description"):
        message_body += f"\n\nDescription:\n{assignment['description']}"
    message_body += f"\n\nBest regards,\n{sender_name}"

    student_query = (
        "SELECT DISTINCT s.parent_email, s.parent_contact "
        "FROM students s "
        "WHERE s.school_id = ? AND s.active = 1 "
        "AND (s.parent_email IS NOT NULL AND s.parent_email != '' "
        "OR s.parent_contact IS NOT NULL AND s.parent_contact != '')"
    )
    student_args: list = [school_id]
    if target_grade:
        student_query += " AND s.grade = ?"
        student_args.append(target_grade)
    if target_section:
        student_query += " AND s.section = ?"
        student_args.append(target_section)

    students = query_db(student_query, tuple(student_args))
    email_count = 0
    whatsapp_count = 0
    skipped_no_contact = 0
    asked = 0

    if delivery_method in ("email", "all"):
        for student in students:
            asked += 1
            parent_email = (student.get("parent_email") or "").strip()
            if not parent_email:
                skipped_no_contact += 1
                continue
            success, _ = send_email(parent_email, f"Assignment: {assignment['title']}", message_body, sender_name=sender_name)
            if success:
                email_count += 1

    if delivery_method in ("whatsapp", "all"):
        for student in students:
            asked += 1
            phone = (student.get("parent_contact") or "").strip()
            if not phone:
                skipped_no_contact += 1
                continue
            data = {
                "messaging_product": "whatsapp",
                "to": normalize_phone_number(phone),
                "type": "text",
                "text": {"preview_url": False, "body": message_body},
            }
            success, _ = send_whatsapp_api_message(data)
            if success:
                whatsapp_count += 1

    if skipped_no_contact:
        flash(
            f"Assignment sent to {email_count} emails and {whatsapp_count} WhatsApp messages. "
            f"{skipped_no_contact} students had no contact details.",
            "info",
        )
    else:
        flash(f"Assignment successfully sent to {class_label}.", "success")
    return redirect(url_for("assignments"))


@app.route("/assignments/delete/<int:assignment_id>", methods=["POST"])
@login_required
@admin_required
def delete_assignment(assignment_id):
    assignment = query_db("SELECT * FROM assignments WHERE id = ?", (assignment_id,), one=True)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("assignments"))
    if session.get("role") != ROLE_SUPERADMIN and assignment["school_id"] != session.get("school_id"):
        flash("You can only delete assignments from your own school.", "warning")
        return redirect(url_for("assignments"))
    query_db("UPDATE assignments SET is_active = 0 WHERE id = ?", (assignment_id,), commit=True)
    flash(f"Assignment '{assignment['title']}' deleted successfully.", "success")
    return redirect(url_for("assignments"))


@app.route("/timetable")
@login_required
def timetable():
    school_id = session.get("school_id")

    # Get all active teachers for the dropdown
    teachers = query_db(
        "SELECT * FROM users WHERE school_id = ? AND role = 'teacher' AND active = 1 ORDER BY name",
        (school_id,),
    )

    # Teachers and admins see all timetable entries
    timetable_entries = query_db(
        """
        SELECT t.*, u.name AS teacher_name
        FROM timetable t
        JOIN users u ON t.teacher_id = u.id
        WHERE t.school_id = ? AND t.is_active = 1
        ORDER BY t.grade ASC, t.section ASC, t.day_of_week ASC, t.start_time ASC
        """,
        (school_id,)
    )

    # Group by grade/section and build grid (days as columns, time slots as rows)
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    timetable_by_class = {}
    for entry in timetable_entries:
        key = f"{entry['grade']} - {entry['section']}"
        if key not in timetable_by_class:
            timetable_by_class[key] = {'entries': [], 'days': DAY_NAMES, 'time_slots': set()}
        timetable_by_class[key]['entries'].append(entry)
        timetable_by_class[key]['time_slots'].add(entry['start_time'])

    # Sort time slots for each class
    for key in timetable_by_class:
        timetable_by_class[key]['time_slots'] = sorted(timetable_by_class[key]['time_slots'])

    return render_template("timetable.html", timetable_by_class=timetable_by_class, teachers=teachers)


@app.route("/timetable/create", methods=["POST"])
@login_required
@teacher_required
def create_timetable():
    """Create a new timetable entry"""
    subject = request.form.get("subject", "").strip()
    teacher_id = request.form.get("teacher_id", "").strip()
    grade = request.form.get("grade", "").strip()
    section = request.form.get("section", "").strip()
    day_of_week = request.form.get("day_of_week", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()

    if not subject or not teacher_id or not grade or not section or not day_of_week or not start_time or not end_time:
        flash("All fields are required.", "warning")
        return redirect(url_for("timetable"))

    try:
        day_of_week_int = int(day_of_week)
        if day_of_week_int < 0 or day_of_week_int > 6:
            raise ValueError()
    except ValueError:
        flash("Invalid day of week.", "warning")
        return redirect(url_for("timetable"))

    teacher = query_db(
        "SELECT * FROM users WHERE id = ? AND role = 'teacher' AND school_id = ? AND active = 1",
        (teacher_id, session.get("school_id")),
        one=True,
    )
    if not teacher:
        flash("Invalid teacher selected.", "danger")
        return redirect(url_for("timetable"))

    query_db(
        """INSERT INTO timetable
           (subject, teacher_id, grade, section, school_id, day_of_week, start_time, end_time)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            subject,
            teacher_id,
            grade,
            section,
            session.get("school_id"),
            day_of_week_int,
            start_time,
            end_time,
        ),
        commit=True,
    )
    flash("Timetable entry created successfully.", "success")
    return redirect(url_for("timetable"))


@app.route("/timetable/delete/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def delete_timetable_entry(entry_id):
    entry = query_db("SELECT * FROM timetable WHERE id = ?", (entry_id,), one=True)
    if not entry:
        flash("Timetable entry not found.", "danger")
        return redirect(url_for("timetable"))
    if session.get("role") != ROLE_SUPERADMIN and entry["school_id"] != session.get("school_id"):
        flash("You can only delete entries from your own school.", "warning")
        return redirect(url_for("timetable"))
    query_db("UPDATE timetable SET is_active = 0 WHERE id = ?", (entry_id,), commit=True)
    flash("Timetable entry deleted successfully.", "success")
    return redirect(url_for("timetable"))


@app.route("/library")
@app.route("/inventory")
@login_required
@admin_or_teacher_required
def library():
    school_id = session.get("school_id")
    user_role = session.get("role", "").lower()
    search_query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()

    query = """
        SELECT * FROM library_books
        WHERE school_id = ? AND is_active = 1
    """
    params = [school_id]

    if search_query:
        query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        params.extend([f"%{search_query}%"] * 3)

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    query += " ORDER BY category ASC, title ASC"

    books = query_db(query, params)

    # Get unique categories for filter dropdown
    categories = query_db(
        "SELECT DISTINCT category FROM library_books WHERE school_id = ? AND is_active = 1 AND category IS NOT NULL ORDER BY category ASC",
        (school_id,)
    )

    # Get existing ISBNs for autocomplete dropdown
    existing_isbns = query_db(
        "SELECT DISTINCT isbn FROM library_books WHERE school_id = ? AND is_active = 1 AND isbn IS NOT NULL ORDER BY isbn ASC",
        (school_id,)
    )

    # Get existing titles for autocomplete dropdown
    existing_titles = query_db(
        "SELECT DISTINCT title FROM library_books WHERE school_id = ? AND is_active = 1 AND title IS NOT NULL ORDER BY title ASC",
        (school_id,)
    )

    return render_template("library.html", books=books, search_query=search_query, category_filter=category_filter, categories=categories, existing_isbns=existing_isbns, existing_titles=existing_titles, user_role=user_role)



@app.route("/library/add", methods=["POST"])
@login_required
@admin_required
def add_book():
    """Add a new school inventory item."""
    school_id = session.get("school_id")

    title = (request.form.get("item_name") or request.form.get("title", "")).strip()
    author = (request.form.get("supplier") or request.form.get("author", "")).strip()
    isbn = (request.form.get("item_code") or request.form.get("isbn", "")).strip() or None
    category = request.form.get("category", "").strip() or None
    description = request.form.get("description", "").strip() or None
    quantity = request.form.get("quantity", "1").strip()
    stock_status = request.form.get("stock_status", "available").strip()

    # Validate stock_status
    valid_statuses = {"available", "low", "out", "unavailable"}
    if stock_status not in valid_statuses:
        stock_status = "available"

    # Validate required fields
    if not title or not author:
        flash("Item name and supplier/brand are required fields.", "warning")
        return redirect(url_for("library"))

    # Validate quantity
    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError()
    except ValueError:
        flash("Quantity must be a positive number.", "warning")
        return redirect(url_for("library"))

    # Check for duplicate ISBN if provided
    if isbn:
        existing = query_db(
            "SELECT id FROM library_books WHERE isbn = ? AND school_id = ? AND is_active = 1",
            (isbn, school_id),
            one=True,
        )
        if existing:
            flash("An inventory item with this code already exists.", "danger")
            return redirect(url_for("library"))

    query_db(
        """
        INSERT INTO library_books
            (title, author, isbn, category, school_id, quantity, stock_status, is_active, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            title,
            author,
            isbn,
            category,
            school_id,
            quantity,
            stock_status,
            description,
        ),
        commit=True,
    )

    flash(f'"{title}" has been added to inventory successfully.', "success")
    return redirect(url_for("library"))


@app.route("/inventory/update_stock/<int:book_id>", methods=["POST"])
@app.route("/library/update_stock/<int:book_id>", methods=["POST"])
@login_required
@admin_required
def update_stock(book_id):
    """Update stock status and quantity for an inventory item."""
    school_id = session.get("school_id")

    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book:
        flash("Inventory item not found.", "danger")
        return redirect(url_for("library"))

    stock_status = request.form.get("stock_status", "").strip()
    quantity = request.form.get("quantity", "").strip()

    # Validate stock_status
    valid_statuses = {"available", "low", "out", "unavailable"}
    if stock_status not in valid_statuses:
        flash("Invalid stock status.", "warning")
        return redirect(url_for("library"))

    # Validate quantity
    try:
        qty = int(quantity)
        if qty < 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash("Quantity must be a valid non-negative number.", "warning")
        return redirect(url_for("library"))

    # Use the explicitly selected status â€” never auto-overwrite user choice
    query_db(
        "UPDATE library_books SET quantity = ?, stock_status = ? WHERE id = ?",
        (qty, stock_status, book_id),
        commit=True,
    )

    status_label = {
        "available": "Available",
        "low": "Low Stock",
        "out": "Out of Stock",
        "unavailable": "No Longer Available",
    }
    flash(f'Stock status for "{book["title"]}" updated to {status_label.get(stock_status, stock_status)}.', "success")
    return redirect(url_for("library"))


# â”€â”€â”€ Library Upload Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def _ensure_upload_dirs():
    for folder in (UPLOAD_FOLDER, AUDIO_FOLDER, COVER_FOLDER):
        os.makedirs(folder, exist_ok=True)


# â”€â”€â”€ Library Upload Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route("/library/upload", methods=["POST"])
@login_required
@admin_required
def upload_book_file():
    """Upload a soft-copy file (PDF / EPUB / DOCX / TXT) for an existing book entry."""
    school_id = session.get("school_id")
    book_id = request.form.get("book_id", type=int)
    if not book_id:
        flash("No book selected.", "warning")
        return redirect(url_for("library"))

    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("library"))

    uploaded = request.files.get("book_file")
    if not uploaded or uploaded.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("library"))

    if not _allowed_file(uploaded.filename, ALLOWED_BOOK_EXTENSIONS):
        flash(
            "Invalid file type. Allowed: PDF, EPUB, MOBI, DOC, DOCX, TXT.",
            "danger",
        )
        return redirect(url_for("library"))

    _ensure_upload_dirs()
    ext = uploaded.filename.rsplit(".", 1)[1].lower()
    filename = f"book_{book_id}_{secure_filename(uploaded.filename)}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    uploaded.save(save_path)

    query_db(
        "UPDATE library_books SET file_path = ? WHERE id = ?",
        (f"uploads/{filename}", book_id),
        commit=True,
    )
    flash(f'Soft copy uploaded for "{book["title"]}".', "success")
    return redirect(url_for("library"))


@app.route("/library/upload_audio/<int:book_id>", methods=["POST"])
@login_required
@admin_required
def upload_audio(book_id):
    """Upload an audio file (MP3 / WAV / OGG / M4A) for a book."""
    school_id = session.get("school_id")
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("library"))

    uploaded = request.files.get("audio_file")
    if not uploaded or uploaded.filename == "":
        flash("No audio file selected.", "warning")
        return redirect(url_for("library"))

    if not _allowed_file(uploaded.filename, ALLOWED_AUDIO_EXTENSIONS):
        flash(
            "Invalid audio type. Allowed: MP3, WAV, OGG, M4A, AAC.",
            "danger",
        )
        return redirect(url_for("library"))

    _ensure_upload_dirs()
    filename = f"audio_{book_id}_{secure_filename(uploaded.filename)}"
    save_path = os.path.join(AUDIO_FOLDER, filename)
    uploaded.save(save_path)

    query_db(
        "UPDATE library_books SET audio_path = ? WHERE id = ?",
        (f"uploads/audio/{filename}", book_id),
        commit=True,
    )
    flash(f'Audio uploaded for "{book["title"]}".', "success")
    return redirect(url_for("library"))


@app.route("/library/upload_cover/<int:book_id>", methods=["POST"])
@login_required
@admin_required
def upload_cover(book_id):
    """Upload a cover image for a book."""
    school_id = session.get("school_id")
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("library"))

    uploaded = request.files.get("cover_file")
    if not uploaded or uploaded.filename == "":
        flash("No image selected.", "warning")
        return redirect(url_for("library"))

    if not _allowed_file(uploaded.filename, ALLOWED_IMAGE_EXTENSIONS):
        flash("Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.", "danger")
        return redirect(url_for("library"))

    _ensure_upload_dirs()
    filename = f"cover_{book_id}_{secure_filename(uploaded.filename)}"
    save_path = os.path.join(COVER_FOLDER, filename)
    uploaded.save(save_path)

    query_db(
        "UPDATE library_books SET cover_image = ? WHERE id = ?",
        (f"uploads/covers/{filename}", book_id),
        commit=True,
    )
    flash(f'Cover image uploaded for "{book["title"]}".', "success")
    return redirect(url_for("library"))


@app.route("/library/delete/<int:book_id>", methods=["POST"])
@login_required
@admin_required
def delete_book(book_id):
    "Soft-delete a library book entry."
    school_id = session.get("school_id")
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("library"))

    query_db(
        "UPDATE library_books SET is_active = 0 WHERE id = ?",
        (book_id,),
        commit=True,
    )
    flash(f'"{book["title"]}" has been removed from the library.', "success")
    return redirect(url_for("library"))


@app.route("/library/download/<int:book_id>")
@login_required
def download_book(book_id):
    "Serve the uploaded soft-copy file for download."
    school_id = session.get("school_id")
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book or not book["file_path"]:
        flash("File not available.", "warning")
        return redirect(url_for("library"))

    rel = book["file_path"]  # e.g. "uploads/book_3_myfile.pdf"
    folder, filename = os.path.split(rel)
    abs_folder = os.path.join(BASE_DIR, "static", folder)
    return send_from_directory(abs_folder, filename, as_attachment=True)


@app.route("/library/serve_audio/<int:book_id>")
@login_required
def serve_audio(book_id):
    school_id = session.get("school_id")
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND school_id = ? AND is_active = 1",
        (book_id, school_id),
        one=True,
    )
    if not book or not book["audio_path"]:
        flash("Audio not available.", "warning")
        return redirect(url_for("library"))

    rel = book["audio_path"]  # e.g. "uploads/audio/audio_3_chapter1.mp3"
    folder, filename = os.path.split(rel)
    abs_folder = os.path.join(BASE_DIR, "static", folder)
    return send_from_directory(abs_folder, filename)


@app.route("/library/serve_cover/<int:book_id>")
def serve_cover(book_id):
    "Serve the cover image for a book."
    book = query_db(
        "SELECT * FROM library_books WHERE id = ? AND is_active = 1",
        (book_id,),
        one=True,
    )
    if not book or not book["cover_image"]:
        return "", 404
    rel = book["cover_image"]
    folder, filename = os.path.split(rel)
    abs_folder = os.path.join(BASE_DIR, "static", folder)
    return send_from_directory(abs_folder, filename)




# Bulk Upload Books Route
@app.route("/library/bulk_upload", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_upload_books():
    "Bulk upload books from a CSV file."
    school_id = session.get("school_id")
    
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        csv_file = request.files["csv_file"]
        if csv_file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        # Check file extension
        if not csv_file.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        import csv
        import io
        
        try:
            # Read CSV content
            stream = io.StringIO(csv_file.stream.read().decode("utf-8"))
            reader = csv.DictReader(stream)
            
            added_count = 0
            skipped_count = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):
                title = (row.get("title") or row.get("Title") or "").strip()
                author = (row.get("author") or row.get("Author") or "").strip()
                isbn = (row.get("isbn") or row.get("ISBN") or "").strip() or None
                category = (row.get("category") or row.get("Category") or "").strip() or None
                description = (row.get("description") or row.get("Description") or "").strip() or None
                quantity = (row.get("quantity") or row.get("Quantity") or "1").strip()
                
                if not title or not author:
                    errors.append(f"Row {row_num}: Missing title or author")
                    skipped_count += 1
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity < 1:
                        quantity = 1
                except ValueError:
                    quantity = 1
                
                existing = query_db(
                    "SELECT id FROM library_books WHERE school_id = ? AND title = ? AND author = ? AND is_active = 1",
                    (school_id, title, author),
                    one=True
                )
                
                if existing:
                    errors.append(f"Row {row_num}: Book '{title}' already exists")
                    skipped_count += 1
                    continue
                
                query_db(
                    "INSERT INTO library_books (school_id, title, author, isbn, category, description, quantity, stock_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (school_id, title, author, isbn, category, description, quantity, "available"),
                    commit=True
                )
                added_count += 1
            
            if added_count > 0:
                flash(f"Successfully added {added_count} book(s) to the library.", "success")
            if skipped_count > 0:
                flash(f"Skipped {skipped_count} row(s).", "warning")
            if errors:
                for error in errors[:10]:
                    flash(error, "warning")
            
            return redirect(url_for("library"))
            
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return redirect(url_for("bulk_upload_books"))
    
    return render_template("bulk_upload_books.html")

# Teaching Plan Routes
@app.route("/teaching_plans")
@login_required
@teacher_required
def teaching_plans():
    school_id = session.get("school_id")
    teacher_id = session.get("user_id")
    
    teaching_plans = query_db(
        "SELECT tp.* FROM teaching_plans tp WHERE tp.school_id = ? AND tp.is_active = 1 ORDER BY tp.created_at DESC",
        (school_id,)
    )
    
    return render_template("teaching_plans.html", teaching_plans=teaching_plans)


@app.route("/create_teaching_plan", methods=["GET", "POST"])
@login_required
@teacher_required
def create_teaching_plan():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        grade = request.form.get("grade", "").strip()
        section = request.form.get("section", "").strip()
        description = request.form.get("description", "").strip()
        objectives = request.form.get("objectives", "").strip()
        content = request.form.get("content", "").strip()
        resources = request.form.get("resources", "").strip()
        activities = request.form.get("activities", "").strip()
        assessment_methods = request.form.get("assessment_methods", "").strip()
        duration = request.form.get("duration", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        plan_date = request.form.get("plan_date", "").strip()
        status = request.form.get("status", "draft").strip()
        
        if not title or not subject or not grade or not section:
            flash("Title, subject, grade, and section are required.", "warning")
            return redirect(url_for("create_teaching_plan"))
        
        try:
            duration_int = int(duration) if duration else None
        except ValueError:
            duration_int = None
        
        query_db(
            "INSERT INTO teaching_plans (school_id, teacher_id, title, subject, grade, section, description, objectives, content, resources, activities, assessment_methods, duration, start_date, end_date, plan_date, status, is_active, week_number, week_ending, period_duration, day_of_week, strand, sub_strand, content_standard, indicator, performance_indicator, core_competencies, keywords, tlm, lesson_references, starter_activities, main_activities, formative_assessment, plenary_reflection, teacher_reflection, attachment_path, attachment_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.get("school_id"),
                session.get("user_id"),
                title,
                subject,
                grade,
                section,
                description,
                objectives,
                content,
                resources,
                activities,
                assessment_methods,
                duration_int,
                start_date if start_date else None,
                end_date if end_date else None,
                plan_date if plan_date else None,
                status,
                request.form.get("week_number", "").strip() or None,
                request.form.get("week_ending", "").strip() or None,
                request.form.get("period_duration", "").strip() or None,
                request.form.get("day_of_week", "").strip() or None,
                request.form.get("strand", "").strip(),
                request.form.get("sub_strand", "").strip(),
                request.form.get("content_standard", "").strip(),
                request.form.get("indicator", "").strip(),
                request.form.get("performance_indicator", "").strip(),
                request.form.get("core_competencies", "").strip(),
                request.form.get("keywords", "").strip(),
                request.form.get("tlm", "").strip(),
                request.form.get("references", "").strip(),
                request.form.get("starter_activities", "").strip(),
                request.form.get("main_activities", "").strip(),
                request.form.get("formative_assessment", "").strip(),
                request.form.get("plenary_reflection", "").strip(),
                request.form.get("teacher_reflection", "").strip(),
                None,
                None,
            ),
            commit=True
        )

        attachment_path = None
        attachment_name = None
        uploaded = request.files.get("plan_attachment")
        if uploaded and uploaded.filename != "":
            if not _allowed_file(uploaded.filename, ALLOWED_ASSIGNMENT_EXTENSIONS):
                flash("Invalid file type. Allowed: PDF, DOC, DOCX, TXT, ZIP, RAR.", "danger")
                return redirect(url_for("create_teaching_plan"))
            _ensure_upload_dirs()
            attachment_name = f"plan_{secure_filename(uploaded.filename)}"
            attachment_path = f"uploads/{attachment_name}"
            uploaded.save(os.path.join(UPLOAD_FOLDER, attachment_name))
            
            if attachment_path:
                last_id_row = query_db("SELECT last_insert_rowid()", one=True)
                last_id = last_id_row[0] if last_id_row else None
                execute_db(
                    "UPDATE teaching_plans SET attachment_path = ?, attachment_name = ? WHERE id = ?",
                    (attachment_path, attachment_name, last_id)
                )

        flash("Teaching plan created successfully!", "success")
        return redirect(url_for("teaching_plans"))
    
    # GET request - show form with dropdowns
    school_id = session.get("school_id")
    school_subjects = []
    try:
        school_subjects = query_db(
            "SELECT name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        seen = set()
        unique_subjects = []
        for s in (school_subjects or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_subjects.append(s)
        school_subjects = unique_subjects
    except Exception:
        pass
    grade_levels = []
    try:
        grade_levels = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,)
        )
        seen = set()
        unique_grades = []
        for g in (grade_levels or []):
            name = g.get("name")
            if name not in seen:
                seen.add(name)
                unique_grades.append(g)
        grade_levels = unique_grades
    except Exception:
        pass
    sections = []
    try:
        sections = query_db(
            "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        seen = set()
        unique_sections = []
        for s in (sections or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_sections.append(s)
        sections = unique_sections
    except Exception:
        pass
    return render_template("create_teaching_plan.html", school_subjects=school_subjects, grade_levels=grade_levels, sections=sections)

@app.route("/edit_teaching_plan/<int:plan_id>", methods=["GET", "POST"])
@login_required
@teacher_required
def edit_teaching_plan(plan_id):
    school_id = session.get("school_id")
    
    plan = query_db(
        "SELECT tp.* FROM teaching_plans tp WHERE tp.id = ? AND tp.school_id = ?",
        (plan_id, school_id),
        one=True
    )
    
    if not plan:
        flash("Teaching plan not found or access denied.", "danger")
        return redirect(url_for("teaching_plans"))
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        grade = request.form.get("grade", "").strip()
        section = request.form.get("section", "").strip()
        description = request.form.get("description", "").strip()
        objectives = request.form.get("objectives", "").strip()
        content = request.form.get("content", "").strip()
        resources = request.form.get("resources", "").strip()
        activities = request.form.get("activities", "").strip()
        assessment_methods = request.form.get("assessment_methods", "").strip()
        duration = request.form.get("duration", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        status = request.form.get("status", "draft").strip()
        
        if not title or not subject or not grade or not section:
            flash("Title, subject, grade, and section are required.", "warning")
            return redirect(url_for("edit_teaching_plan", plan_id=plan_id))
        
        try:
            duration_int = int(duration) if duration else None
        except ValueError:
            duration_int = None
        
        attachment_path = plan.get("attachment_path")
        attachment_name = plan.get("attachment_name")
        uploaded = request.files.get("plan_attachment")
        if uploaded and uploaded.filename != "":
            if not _allowed_file(uploaded.filename, ALLOWED_ASSIGNMENT_EXTENSIONS):
                flash("Invalid file type. Allowed: PDF, DOC, DOCX, TXT, ZIP, RAR.", "danger")
                return redirect(url_for("edit_teaching_plan", plan_id=plan_id))
            _ensure_upload_dirs()
            attachment_name = f"plan_{secure_filename(uploaded.filename)}"
            attachment_path = f"uploads/{attachment_name}"
            uploaded.save(os.path.join(UPLOAD_FOLDER, attachment_name))
        
        query_db(
        'UPDATE teaching_plans SET subject = ?, grade = ?, section = ?, title = ?, description = ?, objectives = ?, content = ?, resources = ?, activities = ?, assessment_methods = ?, duration = ?, start_date = ?, end_date = ?, status = ?, week_number = ?, week_ending = ?, period_duration = ?, day_of_week = ?, strand = ?, sub_strand = ?, content_standard = ?, indicator = ?, performance_indicator = ?, core_competencies = ?, keywords = ?, tlm = ?, lesson_references = ?, starter_activities = ?, main_activities = ?, formative_assessment = ?, plenary_reflection = ?, teacher_reflection = ?, attachment_path = ?, attachment_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (
                subject,
                grade,
                section,
                title,
                description,
                objectives,
                content,
                resources,
                activities,
                assessment_methods,
                duration_int,
                start_date if start_date else None,
                end_date if end_date else None,
                status,
                request.form.get("week_number", "").strip() or None,
                request.form.get("week_ending", "").strip() or None,
                request.form.get("period_duration", "").strip() or None,
                request.form.get("day_of_week", "").strip() or None,
                request.form.get("strand", "").strip(),
                request.form.get("sub_strand", "").strip(),
                request.form.get("content_standard", "").strip(),
                request.form.get("indicator", "").strip(),
                request.form.get("performance_indicator", "").strip(),
                request.form.get("core_competencies", "").strip(),
                request.form.get("keywords", "").strip(),
                request.form.get("tlm", "").strip(),
                request.form.get("references", "").strip(),
                request.form.get("starter_activities", "").strip(),
                request.form.get("main_activities", "").strip(),
                request.form.get("formative_assessment", "").strip(),
                request.form.get("plenary_reflection", "").strip(),
                request.form.get("teacher_reflection", "").strip(),
                attachment_path,
                attachment_name,
                plan_id
            ),
            commit=True
        )
        
        flash("Teaching plan updated successfully!", "success")
        return redirect(url_for("view_teaching_plan", plan_id=plan_id))
    
    # GET request - show form with current data
    school_subjects = []
    try:
        school_subjects = query_db(
            "SELECT name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        seen = set()
        unique_subjects = []
        for s in (school_subjects or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_subjects.append(s)
        school_subjects = unique_subjects
    except Exception:
        pass
    grade_levels = []
    try:
        grade_levels = query_db(
            "SELECT name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
            (school_id,)
        )
        seen = set()
        unique_grades = []
        for g in (grade_levels or []):
            name = g.get("name")
            if name not in seen:
                seen.add(name)
                unique_grades.append(g)
        grade_levels = unique_grades
    except Exception:
        pass
    sections = []
    try:
        sections = query_db(
            "SELECT name FROM school_sections WHERE school_id = ? ORDER BY name",
            (school_id,)
        )
        seen = set()
        unique_sections = []
        for s in (sections or []):
            name = s.get("name")
            if name not in seen:
                seen.add(name)
                unique_sections.append(s)
        sections = unique_sections
    except Exception:
        pass
    return render_template("edit_teaching_plan.html", plan=plan, school_subjects=school_subjects, grade_levels=grade_levels, sections=sections)


@app.route("/view_teaching_plan/<int:plan_id>")
@login_required
def view_teaching_plan(plan_id):
    school_id = session.get("school_id")
    user_role = session.get("role")

    plan = query_db(
        "SELECT tp.* FROM teaching_plans tp WHERE tp.id = ? AND tp.school_id = ?",
        (plan_id, school_id),
        one=True
    )

    if not plan:
        flash("Teaching plan not found or access denied.", "danger")
        return redirect(url_for("teaching_plans"))

    if user_role not in (ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_TEACHER):
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("view_teaching_plan.html", plan=plan)


@app.route("/teaching_plans/approve/<int:plan_id>", methods=["POST"])
@login_required
@admin_required
def approve_teaching_plan(plan_id):
    # Admin approves or declines a teaching plan, with optional notes
    school_id = session.get("school_id")
    admin_id = session.get("user_id")

    plan = query_db(
        "SELECT tp.* FROM teaching_plans tp WHERE tp.id = ? AND tp.school_id = ?",
        (plan_id, school_id),
        one=True,
    )
    if not plan:
        flash("Teaching plan not found.", "danger")
        return redirect(url_for("teaching_plans"))

    action = request.form.get("action", "").strip()
    admin_notes = request.form.get("admin_notes", "").strip() or None

    if action not in ("approve", "decline"):
        flash("Invalid action.", "warning")
        return redirect(url_for("view_teaching_plan", plan_id=plan_id))

    new_status = "approved" if action == "approve" else "declined"

    query_db(
        "UPDATE teaching_plans SET admin_approved = ?, admin_notes = ? WHERE id = ?",
        (new_status, admin_notes, plan_id),
        commit=True,
    )

    action_word = "approved" if action == "approve" else "declined"
    flash(f'Teaching plan "{plan["title"]}" has been {action_word}.', "success")
    return redirect(url_for("view_teaching_plan", plan_id=plan_id))


@app.route("/teaching_plans/delete/<int:plan_id>", methods=["POST"])
@login_required
@admin_required
def delete_teaching_plan(plan_id):
    plan = query_db("SELECT * FROM teaching_plans WHERE id = ?", (plan_id,), one=True)
    if not plan:
        flash("Teaching plan not found.", "danger")
        return redirect(url_for("teaching_plans"))
    if session.get("role") != ROLE_SUPERADMIN and plan["school_id"] != session.get("school_id"):
        flash("You can only delete plans from your own school.", "warning")
        return redirect(url_for("teaching_plans"))
    query_db("UPDATE teaching_plans SET is_active = 0 WHERE id = ?", (plan_id,), commit=True)
    flash(f'Teaching plan "{plan["title"]}" deleted successfully.', "success")
    return redirect(url_for("teaching_plans"))


@app.route("/teaching_plans/download/<int:plan_id>")
@login_required
def download_teaching_plan_attachment(plan_id):
    plan = query_db("SELECT * FROM teaching_plans WHERE id = ?", (plan_id,), one=True)
    if not plan or not plan.get("attachment_path"):
        flash("Attachment not found.", "warning")
        return redirect(url_for("view_teaching_plan", plan_id=plan_id))
    rel = plan["attachment_path"]
    folder, filename = os.path.split(rel)
    abs_folder = os.path.join(BASE_DIR, "static", folder)
    return send_from_directory(abs_folder, filename, as_attachment=True, download_name=plan.get("attachment_name") or filename)


@app.route("/admin/teacher_assignments")
@login_required
@admin_required
def teacher_assignments():
    user_role = session.get("role")
    user_school_id = session.get("school_id")
    
    # Superadmin sees all assignments; regular admins see only their school's
    if user_role == ROLE_SUPERADMIN:
        school_id = request.args.get("school_id", type=int)
        if school_id:
            assignments = query_db(
                "SELECT ta.*, u.name AS teacher_name, u.email AS teacher_email FROM teacher_assignments ta JOIN users u ON ta.teacher_id = u.id WHERE ta.school_id = ? AND ta.active = 1 ORDER BY ta.grade, ta.section, ta.subject",
                (school_id,)
            )
            teachers = query_db(
                "SELECT * FROM users WHERE role = 'teacher' AND school_id = ? AND active = 1 ORDER BY name",
                (school_id,)
            )
            school_subjects = query_db(
                "SELECT id, name FROM school_subjects WHERE school_id = ? ORDER BY name",
                (school_id,)
            )
            grades = query_db(
                "SELECT id, name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
                (school_id,)
            )
            sections = query_db(
                "SELECT id, name FROM school_sections WHERE school_id = ? ORDER BY name",
                (school_id,)
            )
        else:
            assignments = query_db(
                "SELECT ta.*, u.name AS teacher_name, u.email AS teacher_email FROM teacher_assignments ta JOIN users u ON ta.teacher_id = u.id WHERE ta.active = 1 ORDER BY ta.school_id, ta.grade, ta.section, ta.subject",
            )
            teachers = query_db(
                "SELECT * FROM users WHERE role = 'teacher' AND active = 1 ORDER BY school_id, name"
            )
            school_subjects = query_db(
                "SELECT id, name FROM school_subjects ORDER BY name"
            )
            grades = query_db(
                "SELECT id, name FROM school_grade_levels ORDER BY sort_order, name"
            )
            sections = query_db(
                "SELECT id, name FROM school_sections ORDER BY name"
            )
    else:
        assignments = query_db(
            "SELECT ta.*, u.name AS teacher_name, u.email AS teacher_email FROM teacher_assignments ta JOIN users u ON ta.teacher_id = u.id WHERE ta.school_id = ? AND ta.active = 1 ORDER BY ta.grade, ta.section, ta.subject",
            (user_school_id,)
        )
        teachers = query_db(
            "SELECT * FROM users WHERE role = 'teacher' AND school_id = ? AND active = 1 ORDER BY name",
            (user_school_id,),
        )
        school_subjects = query_db(
            "SELECT id, name FROM school_subjects WHERE school_id = ? ORDER BY name",
            (user_school_id,),
        )
    grades = query_db(
        "SELECT id, name FROM school_grade_levels WHERE school_id = ? ORDER BY sort_order, name",
        (user_school_id,),
    )
    sections = query_db(
        "SELECT id, name FROM school_sections WHERE school_id = ? ORDER BY name",
        (user_school_id,),
    )

    assignments_by_teacher = {}
    for assignment in assignments or []:
        teacher_id = assignment["teacher_id"]
        if teacher_id not in assignments_by_teacher:
            assignments_by_teacher[teacher_id] = {
                "teacher_id": teacher_id,
                "teacher_name": assignment["teacher_name"],
                "teacher_email": assignment["teacher_email"],
                "assignments": [],
            }
        assignments_by_teacher[teacher_id]["assignments"].append(assignment)
    
    return render_template(
        "teacher_assignments.html",
        assignments=assignments,
        assignment_groups=list(assignments_by_teacher.values()),
        teachers=teachers,
        grades=grades,
        sections=sections,
        school_subjects=school_subjects,
    )


@app.route("/admin/create_teacher_assignment", methods=["POST"])
@login_required
@admin_required
def create_teacher_assignment():
    teacher_id = request.form.get("teacher_id")
    responsibility = request.form.get("responsibility", "").strip()
    is_primary = 1 if request.form.get("is_primary") else 0
    grades = request.form.getlist("class_grade")
    sections = request.form.getlist("class_section")
    subjects = request.form.getlist("class_subject")

    class_rows = []
    for index in range(max(len(grades), len(sections), len(subjects))):
        row = {
            "grade": (grades[index] if index < len(grades) else "").strip() or None,
            "section": (sections[index] if index < len(sections) else "").strip() or None,
            "subject": (subjects[index] if index < len(subjects) else "").strip() or None,
        }
        if any(row.values()):
            class_rows.append(row)
    
    if not teacher_id or not responsibility or not class_rows:
        flash("Teacher, responsibility, and at least one class are required.", "warning")
        return redirect(url_for("teacher_assignments"))
    
    # Verify teacher exists and is active
    teacher = query_db(
        "SELECT * FROM users WHERE id = ? AND role = 'teacher' AND active = 1",
        (teacher_id,),
        one=True,
    )
    if not teacher:
        flash("Invalid teacher selected.", "danger")
        return redirect(url_for("teacher_assignments"))
    
    # Determine school_id based on role
    user_role = session.get("role")
    if user_role == ROLE_SUPERADMIN:
        # Superadmin: use teacher's school
        school_id = teacher["school_id"]
        if not school_id:
            flash("Teacher must belong to a school.", "danger")
            return redirect(url_for("teacher_assignments"))
    else:
        # Regular admin: verify teacher belongs to admin's school and use admin's school
        if teacher["school_id"] != session.get("school_id"):
            flash("Teacher does not belong to your school.", "warning")
            return redirect(url_for("teacher_assignments"))
        school_id = session.get("school_id")
    
    existing_assignments = query_db(
        "SELECT grade, section, subject FROM teacher_assignments WHERE teacher_id = ? AND active = 1",
        (teacher_id,),
    )
    existing_keys = {
        (assignment["grade"], assignment["section"], assignment["subject"])
        for assignment in existing_assignments
    }
    submitted_keys = set()
    for row in class_rows:
        key = (row["grade"], row["section"], row["subject"])
        if key in existing_keys or key in submitted_keys:
            flash("One or more selected class/subject combinations already exist for this teacher.", "warning")
            return redirect(url_for("teacher_assignments"))
        submitted_keys.add(key)

    insert_params = [
        (
            teacher_id,
            school_id,
            row["grade"],
            row["section"],
            row["subject"],
            responsibility,
            is_primary if index == 0 else 0,
        )
        for index, row in enumerate(class_rows)
    ]
    db = get_db()
    cursor = db.executemany(
        "INSERT INTO teacher_assignments (teacher_id, school_id, grade, section, subject, responsibility, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
        insert_params,
    )
    try:
        db.commit()
    finally:
        cursor.close()

    flash(f"{len(class_rows)} assignment(s) created for {teacher['name']}.", "success")
    return redirect(url_for("teacher_assignments"))


@app.route("/admin/delete_teacher_assignment/<int:assignment_id>", methods=["POST"])
@login_required
@admin_required
def delete_teacher_assignment(assignment_id):
    user_role = session.get("role")
    
    if user_role == ROLE_SUPERADMIN:
        # Superadmin can delete any assignment
        assignment = query_db(
            "SELECT * FROM teacher_assignments WHERE id = ?",
            (assignment_id,),
            one=True,
        )
    else:
        # Regular admin: filter by school_id
        assignment = query_db(
            "SELECT * FROM teacher_assignments WHERE id = ? AND school_id = ?",
            (assignment_id, session.get("school_id")),
            one=True,
        )
    
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("teacher_assignments"))
    
    query_db("UPDATE teacher_assignments SET active = 0 WHERE id = ?", (assignment_id,), commit=True)
    flash("Assignment has been deactivated.", "success")
    return redirect(url_for("teacher_assignments"))


@app.route("/admin/restore_teacher_assignment/<int:assignment_id>", methods=["POST"])
@login_required
@admin_required
def restore_teacher_assignment(assignment_id):
    user_role = session.get("role")
    
    if user_role == ROLE_SUPERADMIN:
        # Superadmin can restore any assignment
        assignment = query_db(
            "SELECT * FROM teacher_assignments WHERE id = ?",
            (assignment_id,),
            one=True,
        )
    else:
        # Regular admin: filter by school_id
        assignment = query_db(
            "SELECT * FROM teacher_assignments WHERE id = ? AND school_id = ?",
            (assignment_id, session.get("school_id")),
            one=True,
        )
    
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("teacher_assignments"))
    
    query_db("UPDATE teacher_assignments SET active = 1 WHERE id = ?", (assignment_id,), commit=True)
    flash("Assignment has been restored.", "success")
    return redirect(url_for("teacher_assignments"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


def _register_init_db():
    if init_db not in (app.before_request_funcs.get(None) or []):
        app.before_request(init_db)

_register_init_db()

# Import and register inventory blueprint
from inventory_routes import inventory_bp
app.register_blueprint(inventory_bp)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0")

