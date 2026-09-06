import os
import socket
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from db_utils import connect_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SUPERADMIN_SECRET_KEY", os.environ.get("FLASK_SECRET_KEY", "change-me-in-production"))

ROLE_SUPERADMIN = "superadmin"
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_PARENT = "parent"
ROLE_STUDENT = "student"

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = connect_db()
    return db


def init_db():
    """Create all required tables in Postgres if they don't exist yet."""
    db = get_db()
    cur = db.execute("SELECT 1")

    try:
        cur.execute("ALTER TABLE schools ADD COLUMN IF NOT EXISTS active INTEGER NOT NULL DEFAULT 1")
    except Exception:
        db.rollback()
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schools (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            school_code TEXT NOT NULL UNIQUE,
            description TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL,
            school_id INTEGER,
            login_code TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            privileges TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            student_number TEXT UNIQUE,
            school_id INTEGER NOT NULL,
            grade TEXT,
            section TEXT,
            email TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            school_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            target_audience TEXT NOT NULL DEFAULT 'all',
            priority TEXT NOT NULL DEFAULT 'normal',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (school_id) REFERENCES schools(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            school_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            event_type TEXT NOT NULL DEFAULT 'general',
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (school_id) REFERENCES schools(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS school_sections (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS school_grade_levels (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
        """
    )

    db.commit()

# Auto-initialise the database on first run / after a factory reset
app.before_request(init_db)

def query_db(query, args=(), one=False, commit=False):
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows

def superadmin_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("superadmin_id"):
            flash("Super Admin access required. Please login.", "warning")
            return redirect(url_for("superadmin_login"))
        return view(**kwargs)
    return wrapped_view

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
        g._database = None

@app.route("/")
def root_redirect():
    if session.get("superadmin_id"):
        return redirect(url_for("superadmin_panel"))
    return redirect(url_for("superadmin_login"))

@app.route("/superadmin/login", methods=["GET", "POST"])
def superadmin_login():
    if request.method == "POST":
        login_code = request.form.get("login_code")
        user = query_db(
            "SELECT * FROM users WHERE role = ? AND login_code = ? AND active = 1",
            (ROLE_SUPERADMIN, login_code),
            one=True
        )
        if user:
            session["superadmin_id"] = user["id"]
            session["superadmin_name"] = user["name"]
            return redirect(url_for("superadmin_panel"))
        flash("Invalid credentials", "danger")
    return render_template("superadmin_login.html")

@app.route("/superadmin/logout")
def superadmin_logout():
    session.clear()
    return redirect(url_for("superadmin_login"))

@app.route("/superadmin")
@superadmin_login_required
def superadmin_panel():
    school_count = query_db("SELECT COUNT(*) AS total FROM schools WHERE active = 1", one=True)["total"]
    user_count = query_db("SELECT COUNT(*) AS total FROM users WHERE role = ?", (ROLE_SUPERADMIN,), one=True)["total"]
    total_users = query_db("SELECT COUNT(*) AS total FROM users", one=True)["total"]
    total_students = query_db("SELECT COUNT(*) AS total FROM students WHERE active = 1", one=True)["total"]
    schools = query_db("SELECT * FROM schools WHERE active = 1 ORDER BY name")

    return render_template(
        "superadmin/panel.html",
        school_count=school_count,
        user_count=user_count,
        total_users=total_users,
        total_students=total_students,
        schools=schools,
    )

# ==================== SCHOOL MANAGEMENT ====================

@app.route("/superadmin/schools")
@superadmin_login_required
def superadmin_schools():
    schools = query_db("SELECT * FROM schools ORDER BY active DESC, name")
    return render_template("superadmin/schools.html", schools=schools)

@app.route("/superadmin/schools/create", methods=["GET", "POST"])
@superadmin_login_required
def superadmin_create_school():
    if request.method == "POST":
        name = request.form.get("name")
        school_code = request.form.get("school_code")
        description = request.form.get("description", "")
        school_email = request.form.get("school_email", "").strip()
        school_phone = request.form.get("school_phone", "").strip()
        school_address = request.form.get("school_address", "").strip()
        school_website = request.form.get("school_website", "").strip()
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

        # Check if school code already exists
        existing = query_db("SELECT id FROM schools WHERE school_code = ?", (school_code,), one=True)
        if existing:
            flash("School code already exists", "danger")
            return render_template("superadmin/create_school.html")

        query_db(
            "INSERT INTO schools (name, school_code, description, school_email, school_phone, school_address, school_website, smtp_server, smtp_port, smtp_email, smtp_password, sender_name, twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, whatsapp_access_token, whatsapp_phone_number_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, school_code, description, school_email, school_phone, school_address, school_website, smtp_server, smtp_port, smtp_email, smtp_password, sender_name, twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, whatsapp_access_token, whatsapp_phone_number_id),
            commit=True
        )
        flash(f"School '{name}' created successfully", "success")
        return redirect(url_for("superadmin_schools"))

    return render_template("superadmin/create_school.html")

@app.route("/superadmin/schools/<int:school_id>")
@superadmin_login_required
def superadmin_view_school(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_schools"))

    # Get school statistics (works for deactivated schools too)
    student_count = query_db(
        "SELECT COUNT(*) AS total FROM students WHERE school_id = ? AND active = 1",
        (school_id,), one=True
    )["total"]

    teacher_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ? AND role = ? AND active = 1",
        (school_id, ROLE_TEACHER), one=True
    )["total"]

    admin_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ? AND role = ? AND active = 1",
        (school_id, ROLE_ADMIN), one=True
    )["total"]

    users = query_db(
        "SELECT * FROM users WHERE school_id = ? ORDER BY role, name",
        (school_id,)
    )

    return render_template(
        "superadmin/view_school.html",
        school=school,
        student_count=student_count,
        admin_count=admin_count,
        teacher_count=teacher_count,
        users=users
    )

@app.route("/superadmin/schools/<int:school_id>/edit", methods=["GET", "POST"])
@superadmin_login_required
def superadmin_edit_school(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_schools"))

    if request.method == "POST":
        name = request.form.get("name")
        school_code = request.form.get("school_code")
        description = request.form.get("description", "")
        school_email = request.form.get("school_email", "").strip()
        school_phone = request.form.get("school_phone", "").strip()
        school_address = request.form.get("school_address", "").strip()
        school_website = request.form.get("school_website", "").strip()
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

        # Check if school code already exists (for different school)
        existing = query_db(
            "SELECT id FROM schools WHERE school_code = ? AND id != ?",
            (school_code, school_id), one=True
        )
        if existing:
            flash("School code already exists", "danger")
            return render_template("superadmin/edit_school.html", school=school)

        query_db(
            "UPDATE schools SET name = ?, school_code = ?, description = ?, school_email = ?, school_phone = ?, school_address = ?, school_website = ?, smtp_server = ?, smtp_port = ?, smtp_email = ?, smtp_password = ?, sender_name = ?, twilio_account_sid = ?, twilio_auth_token = ?, twilio_from_number = ?, twilio_messaging_service_sid = ?, whatsapp_access_token = ?, whatsapp_phone_number_id = ? WHERE id = ?",
            (name, school_code, description, school_email, school_phone, school_address, school_website, smtp_server, smtp_port, smtp_email, smtp_password, sender_name, twilio_account_sid, twilio_auth_token, twilio_from_number, twilio_messaging_service_sid, whatsapp_access_token, whatsapp_phone_number_id, school_id),
            commit=True
        )
        flash(f"School '{name}' updated successfully", "success")
        return redirect(url_for("superadmin_view_school", school_id=school_id))

    return render_template("superadmin/edit_school.html", school=school)

@app.route("/superadmin/schools/reactivate/<int:school_id>", methods=["POST"])
@superadmin_login_required
def superadmin_reactivate_school(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_schools"))

    if school["active"]:
        flash("School is already active.", "info")
        return redirect(url_for("superadmin_schools"))

    query_db("UPDATE schools SET active = 1 WHERE id = ?", (school_id,), commit=True)
    flash(f"School '{school['name']}' has been reactivated.", "success")
    return redirect(url_for("superadmin_schools"))


@app.route("/superadmin/schools/<int:school_id>/delete", methods=["POST"])
@superadmin_login_required
def superadmin_delete_school(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_schools"))

    if not school["active"]:
        flash("School is already deactivated.", "info")
        return redirect(url_for("superadmin_schools"))

    # Soft delete - set inactive (users and data remain intact for potential future restore)
    query_db("UPDATE schools SET active = 0 WHERE id = ?", (school_id,), commit=True)
    flash(f"School '{school['name']}' has been deactivated.", "success")
    return redirect(url_for("superadmin_schools"))


@app.route("/superadmin/schools/<int:school_id>/permanently_delete", methods=["POST"])
@superadmin_login_required
def superadmin_permanently_delete_school(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_schools"))

    try:
        db = get_db()
        cur = db.cursor()

        cur.execute(
            """
            SELECT table_name FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'school_id'
            AND table_name != 'schools'
            """
        )
        tables_with_school_id = [r["table_name"] for r in cur.fetchall()]

        for table in tables_with_school_id:
            cur.execute(f"DELETE FROM {table} WHERE school_id = %s", (school_id,))

        cur.execute("SELECT id FROM students WHERE school_id = %s", (school_id,))
        student_ids = [r["id"] for r in cur.fetchall()]

        if student_ids:
            cur.execute(
                """
                SELECT table_name FROM information_schema.columns
                WHERE table_schema = 'public' AND column_name = 'student_id'
                """
            )
            student_ref_tables = [r["table_name"] for r in cur.fetchall()]
            for table in student_ref_tables:
                for sid in student_ids:
                    cur.execute(f"DELETE FROM {table} WHERE student_id = %s", (sid,))

            cur.execute("DELETE FROM students WHERE school_id = %s", (school_id,))

        cur.execute("SELECT id FROM users WHERE school_id = %s", (school_id,))
        user_ids = [r["id"] for r in cur.fetchall()]

        if user_ids:
            user_ref_columns = [
                "user_id",
                "sender_id",
                "recipient_id",
                "created_by",
                "teacher_id",
                "recorded_by",
                "assigned_by",
            ]
            for col in user_ref_columns:
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND column_name = %s
                    """,
                    (col,),
                )
                ref_tables = [r["table_name"] for r in cur.fetchall()]
                for table in ref_tables:
                    for uid in user_ids:
                        cur.execute(f"DELETE FROM {table} WHERE {col} = %s", (uid,))

            cur.execute("DELETE FROM users WHERE school_id = %s", (school_id,))

        cur.execute("DELETE FROM schools WHERE id = %s", (school_id,))
        db.commit()
        cur.close()

        flash(
            f"School '{school['name']}' and ALL associated data have been permanently deleted.",
            "success",
        )
    except Exception as e:
        flash(f"Error permanently deleting school: {str(e)}", "danger")

    return redirect(url_for("superadmin_schools"))


# ==================== SCHOOL PORTAL ====================

@app.route("/superadmin/school_portal/<int:school_id>")
@superadmin_login_required
def superadmin_school_portal(school_id):
    school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
    if not school:
        flash("School not found", "danger")
        return redirect(url_for("superadmin_panel"))

    # Get statistics (accessible even for deactivated schools — superadmin may need to review)
    student_count = query_db(
        "SELECT COUNT(*) AS total FROM students WHERE school_id = ? AND active = 1",
        (school_id,), one=True
    )["total"]

    teacher_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ? AND role = ? AND active = 1",
        (school_id, ROLE_TEACHER), one=True
    )["total"]

    admin_count = query_db(
        "SELECT COUNT(*) AS total FROM users WHERE school_id = ? AND role = ? AND active = 1",
        (school_id, ROLE_ADMIN), one=True
    )["total"]

    today = date.today().isoformat()
    attendance_today = query_db(
        "SELECT COUNT(*) AS total FROM attendances WHERE school_id = ? AND date = ? AND status = 'present'",
        (school_id, today), one=True
    )["total"]

    # Recent announcements
    recent_announcements = query_db(
        """
        SELECT a.*, u.name AS created_by_name
        FROM announcements a
        JOIN users u ON a.created_by = u.id
        WHERE a.school_id = ? AND a.is_active = 1
        ORDER BY a.created_at DESC
        LIMIT 5
        """,
        (school_id,)
    )

    # Recent events
    recent_events = query_db(
        """
        SELECT e.*, u.name AS created_by_name
        FROM events e
        JOIN users u ON e.created_by = u.id
        WHERE e.school_id = ? AND e.is_active = 1 AND e.event_date >= %s
        ORDER BY e.event_date ASC
        LIMIT 5
        """,
        (school_id, today,)
    )

    # Recent grades
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
        (school_id,)
    )

    return render_template(
        "superadmin/school_portal.html",
        school=school,
        student_count=student_count,
        teacher_count=teacher_count,
        admin_count=admin_count,
        attendance_today=attendance_today,
        recent_announcements=recent_announcements,
        recent_events=recent_events,
        recent_grades=recent_grades,
    )

# ==================== USER MANAGEMENT ====================

@app.route("/superadmin/users")
@superadmin_login_required
def superadmin_users():
    users = query_db(
        "SELECT u.*, s.name as school_name FROM users u LEFT JOIN schools s ON u.school_id = s.id WHERE s.active IS NULL OR s.active = 1 ORDER BY u.role, u.name"
    )
    schools = query_db("SELECT * FROM schools WHERE active = 1 ORDER BY name")
    return render_template("superadmin/users.html", users=users, schools=schools)

@app.route("/superadmin/users/create", methods=["GET", "POST"])
@superadmin_login_required
def superadmin_create_user():
    schools = query_db("SELECT * FROM schools WHERE active = 1 ORDER BY name")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email", "")
        role = request.form.get("role")
        school_id = request.form.get("school_id") or None
        login_code = request.form.get("login_code")
        password = request.form.get("password")

        # Check if login_code already exists
        existing = query_db("SELECT id FROM users WHERE login_code = ?", (login_code,), one=True)
        if existing:
            flash("Login code already exists", "danger")
            return render_template("superadmin/create_user.html", schools=schools)

        password_hash = generate_password_hash(password)

        query_db(
            "INSERT INTO users (name, email, role, school_id, login_code, password_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, role, school_id, login_code, password_hash),
            commit=True
        )
        flash(f"User '{name}' created successfully", "success")
        return redirect(url_for("superadmin_users"))

    return render_template("superadmin/create_user.html", schools=schools)

@app.route("/superadmin/users/<int:user_id>/edit", methods=["GET", "POST"])
@superadmin_login_required
def superadmin_edit_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_users"))

    schools = query_db("SELECT * FROM schools WHERE active = 1 ORDER BY name")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email", "")
        role = request.form.get("role")
        school_id = request.form.get("school_id") or None
        login_code = request.form.get("login_code")
        password = request.form.get("password")

        # Check if login_code already exists (for different user)
        existing = query_db(
            "SELECT id FROM users WHERE login_code = ? AND id != ?",
            (login_code, user_id), one=True
        )
        if existing:
            flash("Login code already exists", "danger")
            return render_template("superadmin/edit_user.html", user=user, schools=schools)

        if password:
            password_hash = generate_password_hash(password)
            query_db(
                "UPDATE users SET name = ?, email = ?, role = ?, school_id = ?, login_code = ?, password_hash = ? WHERE id = ?",
                (name, email, role, school_id, login_code, password_hash, user_id),
                commit=True
            )
        else:
            query_db(
                "UPDATE users SET name = ?, email = ?, role = ?, school_id = ?, login_code = ? WHERE id = ?",
                (name, email, role, school_id, login_code, user_id),
                commit=True
            )

        flash(f"User '{name}' updated successfully", "success")
        return redirect(url_for("superadmin_users"))

    return render_template("superadmin/edit_user.html", user=user, schools=schools)

@app.route("/superadmin/users/<int:user_id>/delete", methods=["POST"])
@superadmin_login_required
def superadmin_delete_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_users"))

    # Don't allow deleting superadmin users
    if user["role"] == ROLE_SUPERADMIN:
        flash("Cannot delete superadmin users", "danger")
        return redirect(url_for("superadmin_users"))

    query_db("UPDATE users SET active = 0 WHERE id = ?", (user_id,), commit=True)
    flash(f"User '{user['name']}' has been deactivated", "success")
    return redirect(url_for("superadmin_users"))

@app.route("/superadmin/users/<int:user_id>/reactivate", methods=["POST"])
@superadmin_login_required
def superadmin_reactivate_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_users"))

    if user["active"]:
        flash("User is already active.", "info")
        return redirect(url_for("superadmin_users"))

    query_db("UPDATE users SET active = 1 WHERE id = ?", (user_id,), commit=True)
    flash(f"User '{user['name']}' has been reactivated.", "success")
    return redirect(url_for("superadmin_users"))


@app.route("/superadmin/users/<int:user_id>/permanently_delete", methods=["POST"])
@superadmin_login_required
def superadmin_permanently_delete_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_users"))

    if user["role"] == ROLE_SUPERADMIN:
        flash("Cannot permanently delete superadmin users", "danger")
        return redirect(url_for("superadmin_users"))

    if user["id"] == session.get("superadmin_id"):
        flash("You cannot permanently delete your own account.", "warning")
        return redirect(url_for("superadmin_users"))

    try:
        db = get_db()
        cur = db.cursor()

        user_ref_columns = [
            "user_id",
            "sender_id",
            "recipient_id",
            "created_by",
            "teacher_id",
            "recorded_by",
            "assigned_by",
        ]
        for col in user_ref_columns:
            cur.execute(
                """
                SELECT table_name FROM information_schema.columns
                WHERE table_schema = 'public' AND column_name = %s
                """,
                (col,),
            )
            ref_tables = [r["table_name"] for r in cur.fetchall()]
            for table in ref_tables:
                cur.execute(f"DELETE FROM {table} WHERE {col} = %s", (user_id,))

        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
        cur.close()

        flash(
            f"User '{user['name']}' and ALL associated data have been permanently deleted.",
            "success",
        )
    except Exception as e:
        flash(f"Error permanently deleting user: {str(e)}", "danger")

    return redirect(url_for("superadmin_users"))


@app.route("/superadmin/suspend_user/<int:user_id>", methods=["POST"])
@superadmin_login_required
def suspend_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_panel"))

    if user["id"] == session.get("superadmin_id"):
        flash("You cannot suspend your own account.", "warning")
        return redirect(url_for("superadmin_panel"))

    query_db("UPDATE users SET active = 0 WHERE id = ?", (user_id,), commit=True)
    flash(f"User '{user['name']}' has been suspended", "success")
    return redirect(url_for("superadmin_panel"))

@app.route("/superadmin/remove_user/<int:user_id>", methods=["POST"])
@superadmin_login_required
def remove_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_panel"))

    if user["id"] == session.get("superadmin_id"):
        flash("You cannot remove your own account.", "warning")
        return redirect(url_for("superadmin_panel"))

    try:
        query_db("DELETE FROM users WHERE id = ?", (user_id,), commit=True)
        flash(f"User '{user['name']}' has been permanently removed", "success")
    except Exception as e:
        flash(f"Error removing user: {str(e)}", "danger")

    return redirect(url_for("superadmin_panel"))

@app.route("/superadmin/update_user_school", methods=["POST"])
@superadmin_login_required
def update_user_school():
    user_id = request.form.get("user_id")
    school_id = request.form.get("school_id")

    if not user_id:
        flash("User ID is required", "warning")
        return redirect(url_for("superadmin_panel"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_panel"))

    if user["role"] == ROLE_SUPERADMIN:
        flash("Cannot modify school assignment for superadmin users", "warning")
        return redirect(url_for("superadmin_panel"))

    if school_id:
        school = query_db("SELECT * FROM schools WHERE id = ?", (school_id,), one=True)
        if not school:
            flash("School not found", "danger")
            return redirect(url_for("superadmin_panel"))

        query_db(
            "UPDATE users SET school_id = ? WHERE id = ?",
            (school_id, user_id),
            commit=True,
        )
        flash(f"User '{user['name']}' assigned to school '{school['name']}'", "success")
    else:
        query_db(
            "UPDATE users SET school_id = NULL WHERE id = ?",
            (user_id,),
            commit=True,
        )
        flash(f"User '{user['name']}' removed from school assignment", "success")

    return redirect(url_for("superadmin_panel"))

@app.route("/superadmin/remove_user_school/<int:user_id>", methods=["POST"])
@superadmin_login_required
def remove_user_school(user_id):
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("superadmin_panel"))

    if user["role"] == ROLE_SUPERADMIN:
        flash("Cannot modify school assignment for superadmin users", "warning")
        return redirect(url_for("superadmin_panel"))

    query_db(
        "UPDATE users SET school_id = NULL WHERE id = ?",
        (user_id,),
        commit=True,
    )
    flash(f"User '{user['name']}' removed from school assignment", "success")
    return redirect(url_for("superadmin_panel"))

# ==================== BULK USER IMPORT ====================

@app.route("/superadmin/users/import", methods=["GET", "POST"])
@superadmin_login_required
def superadmin_import_users():
    """Bulk import users from CSV file"""
    if request.method == "POST":
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash("No file selected", "danger")
            return redirect(request.url)

        file = request.files['csv_file']
        if file.filename == '':
            flash("No file selected", "danger")
            return redirect(request.url)

        if not file.filename.endswith('.csv'):
            flash("Only CSV files are allowed", "danger")
            return redirect(request.url)

        # Check if this is a confirmation
        confirm = request.form.get('confirm') == '1'

        try:
            # Read and parse CSV
            import csv
            import io
            from werkzeug.utils import secure_filename

            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)

            # Validate required columns
            required_fields = {'name', 'email', 'role', 'login_code'}
            if not required_fields.issubset(reader.fieldnames):
                missing = required_fields - set(reader.fieldnames or [])
                flash(f"Missing required columns: {', '.join(missing)}", "danger")
                return redirect(request.url)

            # Read all rows
            rows = list(reader)
            if not rows:
                flash("CSV file is empty", "warning")
                return redirect(request.url)

            if len(rows) > 1000:
                flash("Maximum 1000 users per import", "danger")
                return redirect(request.url)

            # If not confirming, validate and show preview
            if not confirm:
                preview_data = []
                errors = []
                warnings = []

                for i, row in enumerate(rows, 1):
                    user_data = {
                        'name': (row.get('name') or '').strip(),
                        'email': (row.get('email') or '').strip() or None,
                        'role': (row.get('role') or '').strip().lower(),
                        'login_code': (row.get('login_code') or '').strip(),
                        'school_id': row.get('school_id', '').strip() or None,
                        'password': (row.get('password') or '').strip(),
                        'student_number': (row.get('student_number') or '').strip() or None,
                        'grade': (row.get('grade') or '').strip() or None,
                        'section': (row.get('section') or '').strip() or None,
                    }

                    # Validate required fields
                    if not user_data['name']:
                        user_data['error'] = "Name is required"
                        errors.append(f"Row {i}: Name is required")
                        preview_data.append(user_data)
                        continue

                    if not user_data['login_code']:
                        user_data['error'] = "Login code is required"
                        errors.append(f"Row {i}: Login code is required")
                        preview_data.append(user_data)
                        continue

                    # Validate role
                    valid_roles = [ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_TEACHER, ROLE_PARENT, ROLE_STUDENT]
                    if user_data['role'] not in valid_roles:
                        user_data['error'] = f"Invalid role. Must be one of: {', '.join(valid_roles)}"
                        errors.append(f"Row {i}: Invalid role '{user_data['role']}'")
                        preview_data.append(user_data)
                        continue

                    # Check for duplicate login_code in DB
                    existing = query_db("SELECT id FROM users WHERE login_code = ?", (user_data['login_code'],), one=True)
                    if existing:
                        user_data['error'] = "Login code already exists"
                        errors.append(f"Row {i}: Login code '{user_data['login_code']}' already exists")
                        preview_data.append(user_data)
                        continue

                    # Check for duplicate login_code in CSV
                    dup_check = [r for r in rows[:i-1] if (r.get('login_code') or '').strip() == user_data['login_code']]
                    if dup_check:
                        user_data['error'] = "Duplicate login code in CSV"
                        errors.append(f"Row {i}: Duplicate login code '{user_data['login_code']}'")
                        preview_data.append(user_data)
                        continue

                    # Validate school_id for non-superadmin roles
                    if user_data['role'] != ROLE_SUPERADMIN and not user_data['school_id']:
                        user_data['warning'] = "School ID recommended for this role"
                        warnings.append(f"Row {i}: No school_id for {user_data['role']}")

                    # Validate student-specific fields
                    if user_data['role'] == ROLE_STUDENT:
                        if not user_data['student_number']:
                            user_data['error'] = "Student number required for student role"
                            errors.append(f"Row {i}: Student number required for student role")
                            preview_data.append(user_data)
                            continue

                        # Check duplicate student_number in DB
                        existing_student = query_db("SELECT id FROM students WHERE student_number = ?", (user_data['student_number'],), one=True)
                        if existing_student:
                            user_data['error'] = "Student number already exists"
                            errors.append(f"Row {i}: Student number '{user_data['student_number']}' already exists")
                            preview_data.append(user_data)
                            continue

                    # Generate password if not provided
                    if not user_data['password']:
                        import secrets
                        import string
                        alphabet = string.ascii_letters + string.digits
                        user_data['password'] = ''.join(secrets.choice(alphabet) for _ in range(12))

                    user_data['password_display'] = user_data['password']  # For preview only
                    preview_data.append(user_data)

                session["pending_user_import"] = preview_data
                return render_template(
                    "superadmin/users_import.html",
                    preview_data=preview_data,
                    errors=errors,
                    warnings=warnings
                )

            # If confirming, actually create the users
            else:
                pending_rows = session.pop("pending_user_import", None)

                if not pending_rows:
                    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                    reader = csv.DictReader(stream)
                    pending_rows = []
                    for row in reader:
                        pending_rows.append({
                            'name': (row.get('name') or '').strip(),
                            'email': (row.get('email') or '').strip() or None,
                            'role': (row.get('role') or '').strip().lower(),
                            'login_code': (row.get('login_code') or '').strip(),
                            'school_id': row.get('school_id', '').strip() or None,
                            'password': (row.get('password') or '').strip(),
                            'student_number': (row.get('student_number') or '').strip() or None,
                            'grade': (row.get('grade') or '').strip() or None,
                            'section': (row.get('section') or '').strip() or None,
                        })

                if not pending_rows:
                    flash("No pending import data. Upload and preview a CSV before confirming.", "warning")
                    return redirect(url_for("superadmin_import_users"))

                success_count = 0
                failed_count = 0
                import_errors = []

                db = get_db()
                cur = db.cursor()
                try:
                    for i, user_data in enumerate(pending_rows, 1):
                        try:
                            if user_data.get("error"):
                                import_errors.append(f"Row {i}: {user_data['error']}")
                                failed_count += 1
                                continue

                            name = user_data.get('name') or ''
                            email = user_data.get('email')
                            role = (user_data.get('role') or '').lower()
                            login_code = user_data.get('login_code') or ''
                            school_id = user_data.get('school_id') or None
                            password = user_data.get('password') or ''
                            student_number = user_data.get('student_number')
                            grade = user_data.get('grade') or None
                            section = user_data.get('section') or None

                            if not name or not login_code:
                                import_errors.append(f"Row {i}: Missing required fields")
                                failed_count += 1
                                continue

                            if role not in [ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_TEACHER, ROLE_PARENT, ROLE_STUDENT]:
                                import_errors.append(f"Row {i}: Invalid role '{role}'")
                                failed_count += 1
                                continue

                            existing = query_db("SELECT id FROM users WHERE login_code = ?", (login_code,), one=True)
                            if existing:
                                import_errors.append(f"Row {i}: Login code '{login_code}' already exists")
                                failed_count += 1
                                continue

                            if role == ROLE_STUDENT and student_number:
                                existing_student = query_db("SELECT id FROM students WHERE student_number = ?", (student_number,), one=True)
                                if existing_student:
                                    import_errors.append(f"Row {i}: Student number '{student_number}' already exists")
                                    failed_count += 1
                                    continue

                            if not password:
                                import secrets
                                import string
                                alphabet = string.ascii_letters + string.digits
                                password = ''.join(secrets.choice(alphabet) for _ in range(12))

                            password_hash = generate_password_hash(password)
                            cur.execute(
                                """
                                INSERT INTO users (name, email, role, school_id, login_code, password_hash, privileges)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (name, email, role, school_id, login_code, password_hash, '')
                            )

                            if role == ROLE_STUDENT and student_number:
                                cur.execute(
                                    """
                                    INSERT INTO students (name, student_number, school_id, grade, section, email)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (name, student_number, school_id, grade, section, email)
                                )

                            success_count += 1

                        except Exception as e:
                            db.rollback()
                            import_errors.append(f"Row {i}: {str(e)}")
                            failed_count += 1

                    db.commit()
                finally:
                    cur.close()

                flash(f"Import complete: {success_count} succeeded, {failed_count} failed", "success" if failed_count == 0 else "warning")
                return render_template(
                    "superadmin/users_import.html",
                    import_result={'success': success_count, 'failed': failed_count, 'errors': import_errors}
                )

        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return redirect(request.url)

    # GET request - show upload form
    return render_template("superadmin/users_import.html")


@app.route("/superadmin/users/template")
@superadmin_login_required
def download_user_template():
    """Download CSV template for bulk user import"""
    import csv
    import io

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'name', 'email', 'role', 'login_code', 'password',
        'school_id', 'student_number', 'grade', 'section'
    ])

    # Example rows
    writer.writerow([
        'John Doe', 'john@example.com', 'teacher', 'T001', '',
        '1', '', '', ''
    ])
    writer.writerow([
        'Jane Smith', 'jane@example.com', 'student', 'S001', '',
        '1', 'STU001', '10', 'A'
    ])
    writer.writerow([
        'Parent Name', 'parent@example.com', 'parent', 'P001', '',
        '1', '', '', ''
    ])

    # Create response
    from flask import Response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=user_import_template.csv'
        }
    )

# ==================== STATISTICS ====================

@app.route("/superadmin/statistics")
@superadmin_login_required
def superadmin_statistics():
    stats = {
        "total_schools": query_db("SELECT COUNT(*) AS total FROM schools WHERE active = 1", one=True)["total"],
        "total_users": query_db("SELECT COUNT(*) AS total FROM users u LEFT JOIN schools s ON u.school_id = s.id WHERE s.active IS NULL OR s.active = 1", one=True)["total"],
        "total_students": query_db("SELECT COUNT(*) AS total FROM students st LEFT JOIN schools s ON st.school_id = s.id WHERE st.active = 1 AND (s.active IS NULL OR s.active = 1)", one=True)["total"],
        "total_admins": query_db("SELECT COUNT(*) AS total FROM users u LEFT JOIN schools s ON u.school_id = s.id WHERE u.role = ? AND (s.active IS NULL OR s.active = 1)", (ROLE_ADMIN,), one=True)["total"],
        "total_teachers": query_db("SELECT COUNT(*) AS total FROM users u LEFT JOIN schools s ON u.school_id = s.id WHERE u.role = ? AND (s.active IS NULL OR s.active = 1)", (ROLE_TEACHER,), one=True)["total"],
        "total_parents": query_db("SELECT COUNT(*) AS total FROM users u LEFT JOIN schools s ON u.school_id = s.id WHERE u.role = ? AND (s.active IS NULL OR s.active = 1)", (ROLE_PARENT,), one=True)["total"],
    }

    users_per_school = query_db(
        "SELECT s.name, COUNT(u.id) as user_count FROM schools s LEFT JOIN users u ON s.id = u.school_id AND (u.school_id IS NULL OR (SELECT active FROM schools WHERE id = u.school_id) = 1) WHERE s.active = 1 GROUP BY s.id ORDER BY s.name"
    )

    students_per_school = query_db(
        "SELECT s.name, COUNT(st.id) as student_count FROM schools s LEFT JOIN students st ON st.school_id = s.id WHERE s.active = 1 GROUP BY s.id ORDER BY s.name"
    )

    return render_template(
        "superadmin/statistics.html",
        stats=stats,
        users_per_school=users_per_school,
        students_per_school=students_per_school
    )

# ==================== CLEANUP ====================

@app.route("/superadmin/cleanup_users", methods=["POST"])
@superadmin_login_required
def cleanup_users():
    """Delete all users except superadmins - USE WITH EXTREME CAUTION"""
    try:
        non_superadmins = query_db("SELECT id FROM users WHERE role != ?", (ROLE_SUPERADMIN,))

        deleted_count = 0
        for user in non_superadmins:
            try:
                query_db("DELETE FROM users WHERE id = ?", (user["id"],), commit=True)
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting user {user['id']}: {e}")
                continue

        flash(f"Successfully deleted {deleted_count} non-superadmin users.", "success")
    except Exception as e:
        flash(f"Error during cleanup: {str(e)}", "danger")

    return redirect(url_for("superadmin_panel"))

# One-time initialization route to create first superadmin (only works if no users exist)
@app.route("/init", methods=["GET", "POST"])
def init_system():
    # Check if any users exist
    user_count = query_db("SELECT COUNT(*) AS total FROM users", one=True)["total"]
    if user_count > 0:
        flash("System already initialized. Users exist in the database.", "warning")
        return redirect(url_for("superadmin_login"))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        login_code = request.form.get("login_code", "").strip()
        
        if not name or not login_code:
            flash("Name and login code are required.", "warning")
            return redirect(request.url)
        
        # Create superadmin with no school
        query_db(
            "INSERT INTO users (name, email, role, school_id, login_code, password_hash, privileges) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, email, ROLE_SUPERADMIN, None, login_code, generate_password_hash(login_code), "manage_users,manage_content,view_reports,teacher_access"),
            commit=True,
        )
        flash("Superadmin created successfully! You can now login.", "success")
        return redirect(url_for("superadmin_login"))
    
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>System Initialization</title></head>
    <body style="font-family: sans-serif; max-width: 500px; margin: 50px auto; padding: 20px;">
        <h1>System Initialization</h1>
        <p>No users found. Create the first Superadmin account:</p>
        <form method="post">
            <div style="margin-bottom: 1rem;">
                <label>Name:<br>
                    <input type="text" name="name" required style="width: 100%; padding: 8px;">
                </label>
            </div>
            <div style="margin-bottom: 1rem;">
                <label>Email (optional):<br>
                    <input type="email" name="email" style="width: 100%; padding: 8px;">
                </label>
            </div>
            <div style="margin-bottom: 1rem;">
                <label>Login Code (password):<br>
                    <input type="text" name="login_code" required style="width: 100%; padding: 8px;">
                </label>
            </div>
            <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer;">Create Superadmin</button>
        </form>
    </body>
    </html>
    '''


if __name__ == "__main__":
    port = int(os.environ.get("SUPERADMIN_PORT", 8080))
    host = os.environ.get("SUPERADMIN_HOST", "0.0.0.0")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    local_ip = get_local_ip()
    print(f"Superadmin portal running on:")
    print(f"  Local PC: http://127.0.0.1:{port}/superadmin/login")
    print(f"  Mobile/Other devices: http://{local_ip}:{port}/superadmin/login")
    app.run(host=host, port=port, debug=debug_mode)