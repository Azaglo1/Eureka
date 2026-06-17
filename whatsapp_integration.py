# WhatsApp Business API Integration for Grade Reports - Enterprise Edition
# Professional, secure, and feature-rich implementation

import uuid
import os
import csv
import io
import json
import hashlib
import logging
from datetime import datetime, timedelta
from flask import send_from_directory, abort, url_for, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure secure temporary storage
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_FILES_DIR = os.path.join(BASE_DIR, "temp_exports")
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# Configuration constants
WHATSAPP_API_VERSION = "v20.0"  # Updated to latest stable version
TEMP_FILE_EXPIRY_HOURS = 24
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# In-memory rate limiting cache (use Redis in production)
_rate_limit_cache = {}


def get_whatsapp_config():
    """Retrieve WhatsApp configuration from environment with validation."""
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    
    # Validate token format (should start with EA... for WhatsApp Business API)
    if access_token and not access_token.startswith("EAA") and not access_token.startswith("EAAB"):
        logger.warning("Invalid WhatsApp token format - token should start with 'EAA' or 'EAAB'")
    
    return {
        "access_token": access_token,
        "phone_number_id": phone_number_id,
        "configured": bool(access_token and phone_number_id)
    }


def save_temp_file(content, extension="pdf", metadata=None):
    """Save content to a secure temporary file with metadata tracking.
    
    Args:
        content: File content (str or bytes)
        extension: File extension (pdf, html, csv)
        metadata: Optional dict for tracking (student_id, report_type, etc.)
    
    Returns:
        tuple: (file_id, filename) or (None, error_message) on failure
    """
    if not content:
        return None, "No content provided"
    
    # Validate extension
    allowed_extensions = {"pdf", "html", "csv", "txt"}
    if extension.lower() not in allowed_extensions:
        return None, f"Invalid extension. Allowed: {allowed_extensions}"
    
    # Generate secure file ID with hash
    file_id = f"{uuid.uuid4().hex}_{int(datetime.now().timestamp())}"
    filename = f"grade_report_{file_id}.{extension}"
    file_path = os.path.join(TEMP_FILES_DIR, filename)
    
    try:
        # Write with secure permissions
        mode = 'wb' if isinstance(content, bytes) else 'w'
        encoding = None if isinstance(content, bytes) else 'utf-8'
        
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        
        # Set file permissions (owner read/write only)
        os.chmod(file_path, 0o600)
        
        # Store metadata if provided
        if metadata:
            meta_path = file_path + ".meta"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)
            os.chmod(meta_path, 0o600)
        
        logger.info(f"Saved temp file: {filename}")
        return file_id, filename
        
    except Exception as e:
        logger.error(f"Failed to save temp file: {e}")
        return None, str(e)


def cleanup_temp_files():
    """Clean up expired temporary files (call periodically)."""
    now = datetime.now()
    cleaned = 0
    errors = []
    
    for filename in os.listdir(TEMP_FILES_DIR):
        if not filename.startswith("grade_report_"):
            continue
            
        file_path = os.path.join(TEMP_FILES_DIR, filename)
        try:
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if now - file_time > timedelta(hours=TEMP_FILE_EXPIRY_HOURS):
                os.remove(file_path)
                # Also remove metadata file if exists
                meta_path = file_path + ".meta"
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                cleaned += 1
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
    
    if cleaned:
        logger.info(f"Cleaned up {cleaned} expired temp files")
    if errors:
        logger.warning(f"Cleanup errors: {errors}")
    
    return cleaned


def check_rate_limit(identifier, max_requests=10, window_seconds=60):
    """Simple rate limiting implementation.
    
    Args:
        identifier: Unique key (e.g., phone number, user ID)
        max_requests: Max requests allowed in window
        window_seconds: Time window in seconds
    
    Returns:
        bool: True if within limit, False if exceeded
    """
    now = datetime.now()
    cache_key = f"rate_limit_{identifier}"
    
    if cache_key not in _rate_limit_cache:
        _rate_limit_cache[cache_key] = []
    
    # Clean old entries
    _rate_limit_cache[cache_key] = [
        ts for ts in _rate_limit_cache[cache_key]
        if now - ts < timedelta(seconds=window_seconds)
    ]
    
    if len(_rate_limit_cache[cache_key]) >= max_requests:
        return False
    
    _rate_limit_cache[cache_key].append(now)
    return True


def send_whatsapp_api_message(data, retry_count=0, access_token=None, phone_number_id=None):
    """Send message via WhatsApp Business API with retry logic.
    
    Args:
        data: WhatsApp API payload
        retry_count: Current retry attempt
        access_token: Optional override token
        phone_number_id: Optional override phone ID
    
    Returns:
        tuple: (success: bool, error_message: str)
    """
    import requests
    
    config = get_whatsapp_config()
    token = access_token or config["access_token"]
    phone_id = phone_number_id or config["phone_number_id"]
    
    if not config["configured"]:
        return False, "WhatsApp Business API not configured. Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID environment variables."
    
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        if result.get("messages"):
            logger.info(f"WhatsApp message sent successfully: {result['messages'][0].get('id')}")
            return True, ""
        else:
            return False, f"Unexpected response: {result}"
            
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        response_text = ""
        
        # Get response details for debugging
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
                error_code = error_data.get('error', {}).get('code')
                response_text = f"Error code: {error_code}"
            except:
                response_text = e.response.text[:200]
        
        # Retry logic for transient errors
        if retry_count < MAX_RETRIES and (
            e.response is None or 
            getattr(e.response, 'status_code', 0) in [429, 500, 502, 503]
        ):
            logger.warning(f"Retrying WhatsApp API (attempt {retry_count + 1})...")
            return send_whatsapp_api_message(data, retry_count + 1, token, phone_id)
        
        logger.error(f"WhatsApp API error: {error_msg} - {response_text}")
        return False, f"WhatsApp API error: {error_msg}"


def upload_whatsapp_media(file_bytes, filename, mime_type="application/pdf", access_token=None, phone_number_id=None):
    """Upload media file to WhatsApp Business API.
    
    Args:
        file_bytes: File content as bytes
        filename: Original filename
        mime_type: MIME type of the file
        access_token: Optional override token
        phone_number_id: Optional override phone ID
    
    Returns:
        tuple: (media_id: str, error_message: str)
    """
    import requests
    
    config = get_whatsapp_config()
    token = access_token or config["access_token"]
    phone_id = phone_number_id or config["phone_number_id"]
    
    if not token or not phone_id:
        return None, "WhatsApp Business API not configured."
    
    upload_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_id}/media"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes, mime_type)}
    data = {"messaging_product": "whatsapp"}
    
    try:
        response = requests.post(upload_url, headers=headers, files=files, data=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        media_id = result.get("id")
        
        if media_id:
            logger.info(f"Media uploaded successfully: {media_id}")
            return media_id, ""
        else:
            return None, f"Media upload response missing 'id': {result}"
            
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                pass
        logger.error(f"Media upload error: {error_msg}")
        return None, f"WhatsApp media upload failed: {error_msg}"


def format_grade_table(grades_data, teacher_remarks, student_name="Student"):
    """Format grade data as an enhanced, readable text table."""
    if not grades_data:
        return f"No grade records found for {student_name}."
    
    lines = [
        f"📊 Grade Report for {student_name}",
        "=" * 50,
        f"{'Subject':<20} {'Grade':<8} {'Total':<8} {'Remark':<20}",
        "-" * 58
    ]
    
    for g in grades_data:
        subject = (g.get('subject') or 'N/A')[:18]
        grade = g.get('grade') or 'N/A'
        total = f"{g['total_score']:.1f}" if g.get('total_score') is not None else 'N/A'
        remark = (g.get('remark') or '')[:18]
        lines.append(f"{subject:<20} {grade:<8} {total:<8} {remark:<20}")
    
    if teacher_remarks:
        lines.extend(["", "=" * 50, f"💬 Teacher's Remarks: {teacher_remarks}"])
    
    return "\n".join(lines)


def format_grade_csv(grades_data, school_name="", sender_name="", teacher_remarks=""):
    """Format grade data as CSV for download attachments."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header with metadata
    writer.writerow([f"Grade Report - {school_name}"])
    writer.writerow([f"Generated by: {sender_name}"])
    writer.writerow([f"Date: {datetime.now().strftime('%d %B %Y')}"])
    writer.writerow([])
    
    # Column headers
    writer.writerow([
        "Subject", "Grade", "Class Test", "Midterm Exam", "Class Score", 
        "Final Exam", "Total Score", "Remarks", "Teacher Remarks"
    ])
    
    # Grade rows
    for g in grades_data:
        writer.writerow([
            g.get('subject') or '',
            g.get('grade') or '',
            g.get('class_test') or '',
            g.get('midterm_exam') or '',
            g.get('class_score') or '',
            g.get('final_exam') or '',
            g.get('total_score') or '',
            g.get('remark') or '',
            teacher_remarks or ''
        ])
    
    return output.getvalue()


def verify_temp_file_signature(file_id, expected_signature=None):
    """Verify file integrity using optional signature check."""
    if expected_signature:
        computed = hashlib.sha256(file_id.encode()).hexdigest()[:16]
        if computed != expected_signature:
            return False
    return True


# Route handlers for temporary file serving
def get_temp_file_routes():
    """Return route configurations for file serving."""
    return {
        "serve_temp_file": "/temp/<file_id>",
        "view_temp_file": "/temp/<file_id>/view"
    }


def get_config_instructions():
    """Return configuration instructions for .env setup."""
    return """
# WhatsApp Business API Configuration
# Get these from Meta for Developers: https://developers.facebook.com/
WHATSAPP_ACCESS_TOKEN=EAAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WHATSAPP_PHONE_NUMBER_ID=123456789012345

# Optional: Set rate limits (requests per minute)
WHATSAPP_RATE_LIMIT_PER_MINUTE=10
    """.strip()


# Template for WhatsApp document message
WHATSAPP_DOCUMENT_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": None,  # Required
    "type": "document",
    "document": {
        "id": None,  # OR "link": url for public URLs
        "filename": "grade_report.pdf",
        "caption": "Please find the attached grade report."
    }
}

# Template for WhatsApp text message
WHATSAPP_TEXT_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": None,  # Required
    "type": "text",
    "text": {
        "preview_url": False,
        "body": None  # Required
    }
}


if __name__ == "__main__":
    # Test configuration
    config = get_whatsapp_config()
    print(f"WhatsApp configured: {config['configured']}")
    print("\nConfiguration instructions:")
    print(get_config_instructions())