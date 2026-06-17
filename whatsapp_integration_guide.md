# STEP-BY-STEP GUIDE: Adding WhatsApp Document Attachments to Your School Management System

## FILE: app.py

### 1. ADD THESE IMPORTS (near the top with other imports)
```python
# Add these to your existing imports section
import uuid
import os
import csv
import io
import requests
from datetime import datetime, timedelta
from flask import send_from_directory, abort, url_for
```

### 2. ADD THESE CONFIGURATIONS (after your existing configurations)
```python
# WhatsApp Business API Configuration
TEMP_FILES_DIR = os.path.join(BASE_DIR, "temp_exports")
os.makedirs(TEMP_FILES_DIR, exist_ok=True)
```

### 3. ADD THESE HELPER FUNCTIONS (anywhere in your app.py, e.g., after your existing functions)
```python
def save_temp_file(content, extension="csv"):
    """Save content to a secure temporary file and return download token"""
    file_id = str(uuid.uuid4())
    filename = f"grade_report_{file_id}.{extension}"
    file_path = os.path.join(TEMP_FILES_DIR, filename)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_id, filename

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

def send_whatsapp_api_message(data):
    """Send message via WhatsApp Business API"""
    # Get your WhatsApp Business API credentials from environment
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    
    if not access_token or not phone_number_id:
        return False, "WhatsApp Business API not configured. Please set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID environment variables."
    
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return True, ""
    except requests.exceptions.RequestException as e:
        return False, f"WhatsApp API error: {str(e)}"
```

### 4. ADD THIS ROUTE (anywhere with your other routes, e.g., near the end)
```python
@app.route("/temp/<file_id>")
@login_required
def serve_temp_file(file_id):
    """Serve temporary export files with validation"""
    # Prevent directory traversal
    if ".." in file_id or "/" in file_id or not file_id:
        abort(400)
    
    filename = f"grade_report_{file_id}.csv"
    file_path = os.path.join(TEMP_FILES_DIR, filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404)
    
    # Optional: Add expiration check here (uncomment if desired)
    # file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    # if datetime.now() - file_time > timedelta(hours=24):
    #     os.remove(file_path)  # Clean up expired file
    #     abort(404)
    
    return send_from_directory(TEMP_FILES_DIR, filename, as_attachment=True)
```

### 5. MODIFY YOUR send_grades FUNCTION (replace the WhatsApp section)
Find your existing send_grades function and REPLACE the WhatsApp section (around lines 2695-2704) with:

```python
    elif send_method == "whatsapp":
        if student.get("parent_contact"):
            # Generate CSV content for attachment
            csv_output = io.StringIO()
            csv_writer = csv.writer(csv_output)
            csv_writer.writerow(["Subject", "Grade", "Class Score", "Exam Score", "Total Score", "Remarks", "Teacher Remarks", "Term"])
            for g in grades_data:
                csv_writer.writerow([
                    g["subject"] or "",
                    g["grade"] or "",
                    g["class_score"] or "",
                    g["exam_score"] or "",
                    g["total_score"] or "",
                    g["remark"] or "",
                    teacher_remarks or "",
                    g["term"] or ""
                ])
            csv_content = csv_output.getvalue()
            
            # Save to temporary file
            file_id, filename = save_temp_file(csv_content, "csv")
            
            # Create secure download URL
            download_url = url_for('serve_temp_file', file_id=file_id, _external=True)
            
            # WhatsApp Business API message with document
            whatsapp_data = {
                "messaging_product": "whatsapp",
                "to": normalize_phone_number(student["parent_contact"]),
                "type": "document",
                "document": {
                    "link": download_url,
                    "filename": f"grade_report_{student['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                }
            }
            
            # Send via WhatsApp Business API
            success, error_msg = send_whatsapp_api_message(whatsapp_data)
            
            if success:
                flash(f"Grade report sent to {student['parent_contact']} via WhatsApp as document attachment.", "success")
            else:
                flash(f"Failed to send WhatsApp document: {error_msg}", "error")
        else:
            flash("Student has no parent contact number on file.", "warning")
```

### 6. ADD THESE ENVIRONMENT VARIABLES TO YOUR .env FILE
```
WHATSAPP_ACCESS_TOKEN=your_whatsapp_business_api_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id_here
```

### 7. INSTALL THE REQUIRED DEPENDENCY
```bash
pip install requests
```

### 8. SET UP PERIODIC CLEANUP (RECOMMENDED)
Add this to run periodically (e.g., via Windows Task Scheduler or cron job):
```python
# In a separate script or add to your application startup
from your_app_module import cleanup_temp_files
cleanup_temp_files()  # Call this every hour or so
```

## IMPORTANT NOTES

### Prerequisites You Must Have:
1. **Verified WhatsApp Business Account** (not a regular WhatsApp account)
2. **Approved access to WhatsApp Business API** (requires business verification through Meta/Facebook)
3. **A dedicated phone number** for your WhatsApp Business Account
4. **Server with public HTTPS endpoint** (required for WhatsApp webhooks, though not strictly needed for outgoing messages only)

### If You Don't Have WhatsApp Business API Access:
Consider this alternative approach:
1. Keep using **email for document delivery** (it works perfectly with CSV attachments)
2. Use **WhatsApp for notifications only**: Send a message like "Grade report has been sent to your email. Please check your inbox for the CSV attachment."
3. This is actually the **recommended approach** by many educational institutions as it:
   - Works reliably without complex API approvals
   - Ensures delivery (email is more universally accessible than WhatsApp)
   - Provides true document attachments via email
   - Avoids ongoing API costs and complexity

### Security Considerations:
1. **Never commit your WhatsApp API tokens to version control** - keep them in .env file only
2. **Validate file IDs** to prevent directory traversal attacks (already implemented)
3. **Consider adding school_id validation** to the serve_temp_file endpoint for multi-school setups
4. **Implement rate limiting** if you expect high volume (WhatsApp Business API has limits)
5. **Monitor your temporary storage** to ensure cleanup is working properly

## Testing Your Implementation:
1. Start your Flask application
2. Navigate to a student's grade view
3. Click "Send via WhatsApp"
4. If configured correctly, you should receive a WhatsApp message with a document attachment
5. Check your server logs for any errors
6. Verify temporary files are created in the temp_exports directory and cleaned up after 24 hours

## Troubleshooting:
- "WhatsApp Business API not configured": Check your .env file and environment variables
- "Failed to send WhatsApp API message": Check your WhatsApp Business Account status and permissions
- File not found errors: Verify the serve_temp_file route is correctly registered and accessible
- Permission errors: Ensure the web server user has write access to the temp_exports directory
```

This implementation provides a complete, secure way to send grade reports as actual document attachments via WhatsApp Business API, with proper file handling, security considerations, and cleanup mechanisms.