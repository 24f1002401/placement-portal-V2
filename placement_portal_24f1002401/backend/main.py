import sys
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename

# Ensure backend root is on path when running as script
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from auth_utils import create_access_token, role_required, get_current_user
from cache_utils import cache_get, cache_set, cache_delete_prefix
from config import ALLOWED_RESUME_EXTENSIONS, EXPORT_FOLDER, UPLOAD_FOLDER
from models.database import (
    create_tables,
    create_default_admin,
    find_user_by_email,
    create_student_user,
    create_company_user,
    create_placement_drive,
    get_company_profile_by_user,
    get_approved_drives_for_student,
    get_student_profile,
    create_application,
    get_all_drives_with_company,
    set_drive_status,
    get_all_companies,
    set_company_status,
    get_all_students,
    set_drive_status_for_company,
    get_all_applications_with_details,
    get_applications_for_student,
    update_student_profile,
    get_drives_for_company_user,
    set_student_active,
    get_admin_stats,
    student_is_eligible_for_drive,
    get_drive_by_id,
    set_student_resume,
    get_applications_for_company_drive,
    update_application_status,
    company_owns_application,
)

# Jinja entry: backend/templates ; Vue CDN UI: frontend/static
app = Flask(
    __name__,
    static_folder=str(PROJECT_ROOT / "frontend" / "static"),
    static_url_path="/static",
    template_folder="templates",
)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
EXPORT_FOLDER.mkdir(parents=True, exist_ok=True)


create_tables()
create_default_admin()


@app.route("/")
def index_page():
    return render_template("index.html")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/hello")
def hello():
    return jsonify({"message": "Backend working with DB"})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON payload"}), 400

    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if not email or not password or not role:
        return jsonify({"success": False, "error": "Missing email, password or role"}), 400

    user = find_user_by_email(email)
    if user is None:
        return jsonify({"success": False, "error": "User not found"}), 400

    user_id, db_email, db_password, db_role, is_active = user

    if password != db_password:
        return jsonify({"success": False, "error": "Wrong password"}), 400
    if db_role != role:
        return jsonify({"success": False, "error": "Role mismatch"}), 400
    if not is_active:
        return jsonify({"success": False, "error": "User is inactive"}), 400

    if db_role == "company":
        profile = get_company_profile_by_user(user_id)
        if not profile:
            return jsonify({"success": False, "error": "Company profile not found"}), 400
        if profile[2] == "pending":
            return jsonify({"success": False, "error": "Company awaiting admin approval"}), 400
        if profile[2] in ("rejected", "blacklisted"):
            return jsonify({"success": False, "error": f"Company is {profile[2]}"}), 400

    token = create_access_token(user_id, db_role, db_email)
    payload = {
        "success": True,
        "user_id": user_id,
        "role": db_role,
        "token": token,
    }

    if db_role == "student":
        row = get_student_profile(user_id)
        if not row:
            return jsonify({"success": False, "error": "Student profile not found"}), 400
        payload["student_name"] = row[2]

    return jsonify(payload), 200


@app.route("/api/register/student", methods=["POST"])
def register_student():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")
    branch = data.get("branch")
    cgpa = data.get("cgpa")
    year = data.get("year")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    if find_user_by_email(email) is not None:
        return jsonify({"success": False, "error": "Email already registered"}), 400

    try:
        user_id = create_student_user(email, password, name, branch, cgpa, year)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    cache_delete_prefix("admin:stats")
    cache_delete_prefix("admin:students")
    return jsonify({"success": True, "user_id": user_id})


@app.route("/api/register/company", methods=["POST"])
def register_company():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    company_name = data.get("company_name")
    hr_contact = data.get("hr_contact")
    website = data.get("website")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    if find_user_by_email(email) is not None:
        return jsonify({"success": False, "error": "Email already registered"}), 400

    try:
        user_id = create_company_user(email, password, company_name, hr_contact, website)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    cache_delete_prefix("admin:stats")
    cache_delete_prefix("admin:companies")
    return jsonify({"success": True, "user_id": user_id})


@app.route("/api/admin/stats", methods=["GET"])
@role_required("admin")
def admin_stats():
    cached = cache_get("admin:stats")
    if cached is not None:
        return jsonify({"success": True, "stats": cached, "cached": True})
    stats = get_admin_stats()
    cache_set("admin:stats", stats)
    return jsonify({"success": True, "stats": stats, "cached": False})


@app.route("/api/admin/drives", methods=["GET"])
@role_required("admin")
def admin_list_drives():
    search = request.args.get("search", "")
    cache_key = f"admin:drives:{search}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"success": True, "drives": cached, "cached": True})

    rows = get_all_drives_with_company(search=search)
    drives = [
        {
            "drive_id": r[0],
            "company_name": r[1],
            "job_title": r[2],
            "status": r[3],
            "deadline": r[4],
        }
        for r in rows
    ]
    cache_set(cache_key, drives)
    return jsonify({"success": True, "drives": drives, "cached": False})


@app.route("/api/admin/approve_drive", methods=["POST"])
@role_required("admin")
def admin_approve_drive():
    data = request.get_json() or {}
    drive_id = data.get("drive_id")
    if not drive_id:
        return jsonify({"success": False, "error": "drive_id required"}), 400
    set_drive_status(drive_id, "approved")
    cache_delete_prefix("admin:drives")
    cache_delete_prefix("admin:stats")
    return jsonify({"success": True})


@app.route("/api/admin/reject_drive", methods=["POST"])
@role_required("admin")
def admin_reject_drive():
    data = request.get_json() or {}
    drive_id = data.get("drive_id")
    if not drive_id:
        return jsonify({"success": False, "error": "drive_id required"}), 400
    set_drive_status(drive_id, "rejected")
    cache_delete_prefix("admin:drives")
    cache_delete_prefix("admin:stats")
    return jsonify({"success": True})


@app.route("/api/admin/companies", methods=["GET"])
@role_required("admin")
def admin_list_companies():
    search = request.args.get("search", "")
    cache_key = f"admin:companies:{search}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"success": True, "companies": cached, "cached": True})

    rows = get_all_companies(search=search)
    companies = [
        {
            "company_id": r[0],
            "company_name": r[1],
            "status": r[2],
            "hr_contact": r[3],
            "website": r[4],
        }
        for r in rows
    ]
    cache_set(cache_key, companies)
    return jsonify({"success": True, "companies": companies, "cached": False})


@app.route("/api/admin/approve_company", methods=["POST"])
@role_required("admin")
def admin_approve_company():
    data = request.get_json() or {}
    company_id = data.get("company_id")
    if not company_id:
        return jsonify({"success": False, "error": "company_id required"}), 400
    set_company_status(company_id, "approved")
    cache_delete_prefix("admin:companies")
    cache_delete_prefix("admin:stats")
    return jsonify({"success": True})


@app.route("/api/admin/reject_company", methods=["POST"])
@role_required("admin")
def admin_reject_company():
    data = request.get_json() or {}
    company_id = data.get("company_id")
    if not company_id:
        return jsonify({"success": False, "error": "company_id required"}), 400
    set_company_status(company_id, "rejected")
    cache_delete_prefix("admin:companies")
    return jsonify({"success": True})


@app.route("/api/admin/blacklist_company", methods=["POST"])
@role_required("admin")
def admin_blacklist_company():
    data = request.get_json() or {}
    company_id = data.get("company_id")
    if not company_id:
        return jsonify({"success": False, "error": "company_id required"}), 400
    set_company_status(company_id, "blacklisted")
    set_drive_status_for_company(company_id, "cancelled")
    cache_delete_prefix("admin:")
    return jsonify({"success": True})


@app.route("/api/admin/students", methods=["GET"])
@role_required("admin")
def admin_list_students():
    search = request.args.get("search", "")
    cache_key = f"admin:students:{search}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"success": True, "students": cached, "cached": True})

    rows = get_all_students(search=search)
    students = [
        {
            "student_profile_id": r[0],
            "name": r[1],
            "branch": r[2],
            "cgpa": r[3],
            "year": r[4],
            "is_active": bool(r[5]),
            "email": r[6],
        }
        for r in rows
    ]
    cache_set(cache_key, students)
    return jsonify({"success": True, "students": students, "cached": False})


@app.route("/api/admin/blacklist_student", methods=["POST"])
@role_required("admin")
def admin_blacklist_student():
    data = request.get_json() or {}
    student_profile_id = data.get("student_profile_id")
    if not student_profile_id:
        return jsonify({"success": False, "error": "student_profile_id required"}), 400
    set_student_active(student_profile_id, False)
    cache_delete_prefix("admin:students")
    cache_delete_prefix("admin:stats")
    return jsonify({"success": True})


@app.route("/api/admin/applications", methods=["GET"])
@role_required("admin")
def admin_list_applications():
    rows = get_all_applications_with_details()
    apps = [
        {
            "application_id": r[0],
            "student_name": r[1],
            "branch": r[2],
            "drive_id": r[3],
            "job_title": r[4],
            "company_name": r[5],
            "applied_on": r[6],
            "status": r[7],
            "interview_date": r[8],
        }
        for r in rows
    ]
    return jsonify({"success": True, "applications": apps})


@app.route("/api/company/profile", methods=["GET"])
@role_required("company")
def company_profile():
    user = request.current_user
    profile = get_company_profile_by_user(user["user_id"])
    if not profile:
        return jsonify({"success": False, "error": "Company profile not found"}), 404
    return jsonify({
        "success": True,
        "profile": {
            "company_id": profile[0],
            "company_name": profile[1],
            "approval_status": profile[2],
            "hr_contact": profile[3],
            "website": profile[4],
        },
    })


@app.route("/api/company/create_drive", methods=["POST"])
@role_required("company")
def company_create_drive():
    user = request.current_user
    data = request.get_json() or {}
    profile = get_company_profile_by_user(user["user_id"])
    if profile is None:
        return jsonify({"success": False, "error": "Company profile not found"}), 400
    if profile[2] != "approved":
        return jsonify({"success": False, "error": "Company not approved by admin"}), 400

    drive_id = create_placement_drive(
        profile[0],
        data.get("job_title"),
        data.get("job_description"),
        data.get("eligibility_branch"),
        data.get("eligibility_cgpa"),
        data.get("eligibility_year"),
        data.get("application_deadline"),
    )
    cache_delete_prefix("admin:drives")
    cache_delete_prefix("admin:stats")
    return jsonify({"success": True, "drive_id": drive_id})


@app.route("/api/company/drives")
@role_required("company")
def api_company_drives():
    user = request.current_user
    rows = get_drives_for_company_user(user["user_id"])
    upcoming, closed = [], []
    for d in rows:
        drive = {
            "id": d[0],
            "job_title": d[1],
            "job_description": d[2],
            "status": d[3],
            "applicant_count": d[4],
        }
        if d[3] == "closed":
            closed.append(drive)
        else:
            upcoming.append(drive)
    return jsonify({
        "success": True,
        "upcoming_drives": upcoming,
        "closed_drives": closed,
    })


@app.route("/api/company/close_drive", methods=["POST"])
@role_required("company")
def company_close_drive():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    drive_id = data.get("drive_id")
    if not drive_id:
        return jsonify({"success": False, "error": "drive_id required"}), 400

    rows = get_drives_for_company_user(user["user_id"])
    if not any(d[0] == drive_id for d in rows):
        return jsonify({"success": False, "error": "Drive not found for this company"}), 400

    set_drive_status(drive_id, "closed")
    cache_delete_prefix("admin:drives")
    return jsonify({"success": True})


@app.route("/api/company/applications", methods=["GET"])
@role_required("company")
def company_applications():
    user = request.current_user
    drive_id = request.args.get("drive_id", type=int)
    rows = get_applications_for_company_drive(user["user_id"], drive_id)
    apps = [
        {
            "application_id": r[0],
            "student_name": r[1],
            "branch": r[2],
            "cgpa": r[3],
            "job_title": r[4],
            "status": r[5],
            "applied_on": r[6],
            "interview_date": r[7],
            "interview_notes": r[8],
            "drive_id": r[9],
            "resume_path": r[10],
        }
        for r in rows
    ]
    return jsonify({"success": True, "applications": apps})


@app.route("/api/company/update_application", methods=["POST"])
@role_required("company")
def company_update_application():
    user = request.current_user
    data = request.get_json() or {}
    application_id = data.get("application_id")
    status = (data.get("status") or "").lower()
    interview_date = data.get("interview_date")
    interview_notes = data.get("interview_notes")

    allowed = {"applied", "shortlisted", "selected", "rejected"}
    if not application_id or status not in allowed:
        return jsonify({"success": False, "error": "Valid application_id and status required"}), 400
    if not company_owns_application(user["user_id"], application_id):
        return jsonify({"success": False, "error": "Application not found for this company"}), 404

    ok = update_application_status(application_id, status, interview_date, interview_notes)
    if not ok:
        return jsonify({"success": False, "error": "Update failed"}), 400
    return jsonify({"success": True})


@app.route("/api/student/drives")
@role_required("student")
def api_student_drives():
    user = request.current_user
    search = request.args.get("search", "")
    rows = get_approved_drives_for_student(user["user_id"], search=search)
    drives = [
        {
            "id": d[0],
            "job_title": d[1],
            "company_name": d[2],
            "application_deadline": d[3],
            "status": d[4],
        }
        for d in rows
    ]
    return jsonify({"success": True, "drives": drives})


@app.route("/api/student/apply_drive", methods=["POST"])
@role_required("student")
def student_apply_drive():
    user = request.current_user
    data = request.get_json() or {}
    drive_id = data.get("drive_id")
    if not drive_id:
        return jsonify({"success": False, "error": "drive_id required"}), 400

    row = get_student_profile(user["user_id"])
    if row is None:
        return jsonify({"success": False, "error": "Student profile not found"}), 400

    drive = get_drive_by_id(drive_id)
    if not drive or drive[3] != "approved":
        return jsonify({"success": False, "error": "Drive not available"}), 400

    if drive[4]:
        try:
            if date.today() > date.fromisoformat(str(drive[4])[:10]):
                return jsonify({"success": False, "error": "Application deadline passed"}), 400
        except ValueError:
            pass

    if not student_is_eligible_for_drive(user["user_id"], drive_id):
        return jsonify({"success": False, "error": "Not eligible for this drive"}), 400

    created = create_application(row[0], drive_id, date.today().isoformat())
    if not created:
        return jsonify({"success": False, "error": "Already applied to this drive"}), 400

    cache_delete_prefix("admin:stats")
    return jsonify({"success": True})


@app.route("/api/student/applications", methods=["GET"])
@role_required("student")
def student_applications():
    user = request.current_user
    row = get_student_profile(user["user_id"])
    if not row:
        return jsonify({"success": False, "error": "Student profile not found"}), 400

    rows = get_applications_for_student(row[0])
    apps = [
        {
            "application_id": r[0],
            "job_title": r[1],
            "company_name": r[2],
            "status": r[3] or "applied",
            "applied_on": r[4],
            "interview_date": r[5],
        }
        for r in rows
    ]
    return jsonify({"success": True, "applications": apps})


@app.route("/api/student/profile")
@role_required("student")
def api_get_student_profile():
    user = request.current_user
    row = get_student_profile(user["user_id"])
    if not row:
        return jsonify({"success": False, "error": "Student profile not found"}), 404
    return jsonify({
        "success": True,
        "profile": {
            "full_name": row[2],
            "branch": row[3],
            "cgpa": row[4],
            "year": row[5],
            "resume_path": row[6],
            "email": user.get("email"),
        },
    })


@app.route("/api/student/profile/update", methods=["POST"])
@role_required("student")
def api_update_student_profile():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    ok = update_student_profile(
        user_id=user["user_id"],
        full_name=data.get("full_name"),
        branch=data.get("branch"),
        cgpa=data.get("cgpa"),
        year=data.get("year"),
    )
    if not ok:
        return jsonify({"success": False, "error": "Student profile not found or not updated"}), 400
    cache_delete_prefix("admin:students")
    return jsonify({"success": True})


@app.route("/api/student/resume", methods=["POST"])
@role_required("student")
def student_upload_resume():
    user = request.current_user
    if "resume" not in request.files:
        return jsonify({"success": False, "error": "resume file required"}), 400
    f = request.files["resume"]
    if not f.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    filename = secure_filename(f.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        return jsonify({"success": False, "error": "Only PDF/DOC/DOCX allowed"}), 400

    saved = f"user_{user['user_id']}_{filename}"
    path = UPLOAD_FOLDER / saved
    f.save(path)
    set_student_resume(user["user_id"], saved)
    return jsonify({"success": True, "resume_path": saved})


def _celery_available():
    try:
        from cache_utils import get_redis
        client = get_redis()
        return client is not None and client is not False
    except Exception:
        return False


@app.route("/api/student/export_csv", methods=["POST"])
@role_required("student")
def student_export_csv():
    user = request.current_user
    row = get_student_profile(user["user_id"])
    if not row:
        return jsonify({"success": False, "error": "Student profile not found"}), 400

    from tasks.jobs import export_student_applications_csv

    if _celery_available():
        try:
            async_result = export_student_applications_csv.delay(user["user_id"], row[0])
            return jsonify({
                "success": True,
                "task_id": async_result.id,
                "message": "Export started. You will get an alert when ready.",
            })
        except Exception:
            pass

    result = export_student_applications_csv.run(user["user_id"], row[0])
    return jsonify({
        "success": True,
        "task_id": None,
        "message": "Export completed (sync fallback).",
        "filename": result.get("filename"),
        "fallback": True,
    })


@app.route("/api/student/export_status/<task_id>", methods=["GET"])
@role_required("student")
def student_export_status(task_id):
    try:
        from tasks.celery_app import celery_app

        result = celery_app.AsyncResult(task_id)
        if result.state == "SUCCESS":
            return jsonify({"success": True, "status": "SUCCESS", "result": result.result})
        return jsonify({"success": True, "status": result.state})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/exports/<path:filename>")
@role_required("student", "admin")
def download_export(filename):
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        return jsonify({"success": False, "error": "Invalid filename"}), 400

    user = request.current_user
    if user["role"] == "student":
        prefix = f"applications_user_{user['user_id']}_"
        if not safe_name.startswith(prefix):
            return jsonify({"success": False, "error": "Forbidden"}), 403

    target = EXPORT_FOLDER / safe_name
    if not target.is_file():
        return jsonify({"success": False, "error": "File not found"}), 404
    return send_from_directory(EXPORT_FOLDER, safe_name, as_attachment=True)


@app.route("/api/jobs/run_daily_reminders", methods=["POST"])
@role_required("admin")
def run_daily_reminders():
    from tasks.jobs import send_daily_deadline_reminders

    if _celery_available():
        try:
            async_result = send_daily_deadline_reminders.delay()
            return jsonify({
                "success": True,
                "task_id": async_result.id,
                "message": "Daily reminders queued. Check backend/notifications/ for student + admin copies.",
            })
        except Exception:
            pass
    result = send_daily_deadline_reminders.run()
    return jsonify({
        "success": True,
        "result": result,
        "fallback": True,
        "message": (
            f"Reminders sent to {result.get('students', 0)} student(s). "
            f"Files saved under backend/notifications/."
        ),
    })


@app.route("/api/jobs/run_monthly_report", methods=["POST"])
@role_required("admin")
def run_monthly_report():
    from tasks.jobs import send_monthly_activity_report

    if _celery_available():
        try:
            async_result = send_monthly_activity_report.delay()
            return jsonify({
                "success": True,
                "task_id": async_result.id,
                "message": "Monthly report queued. Check backend/notifications/ (or admin email if SMTP set).",
            })
        except Exception:
            pass
    result = send_monthly_activity_report.run()
    stats = result.get("stats") or {}
    return jsonify({
        "success": True,
        "result": result,
        "fallback": True,
        "message": (
            f"Monthly report for {stats.get('period_label', 'period')} saved. "
            f"Open backend/notifications/ (or admin mailbox if SMTP is configured)."
        ),
    })


if __name__ == "__main__":
    app.run(debug=True)
