import csv
import smtplib
import urllib.request
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from tasks.celery_app import celery_app

import sys
from pathlib import Path as _P

_BACKEND = _P(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config import (
    ADMIN_EMAIL,
    EXPORT_FOLDER,
    GCHAT_WEBHOOK_URL,
    NOTIFICATIONS_FOLDER,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)


def _ensure_dirs():
    EXPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    NOTIFICATIONS_FOLDER.mkdir(parents=True, exist_ok=True)


def _send_notification(subject, body, to_email=None):
    """Send via SMTP / Google Chat webhook, and always save a local copy for demos."""
    _ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject)[:40]
    path = NOTIFICATIONS_FOLDER / f"{stamp}_{safe}.txt"
    path.write_text(f"TO: {to_email or ADMIN_EMAIL}\nSUBJECT: {subject}\n\n{body}", encoding="utf-8")

    if GCHAT_WEBHOOK_URL:
        try:
            import json as _json
            payload = _json.dumps({"text": subject + "\n" + body}).encode("utf-8")
            req = urllib.request.Request(
                GCHAT_WEBHOOK_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:
            path.write_text(path.read_text(encoding="utf-8") + f"\n\nWebhook error: {exc}", encoding="utf-8")

    if SMTP_HOST and to_email:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER or "noreply@ppa.local"
            msg["To"] = to_email
            msg.attach(MIMEText(body, "html" if "<html" in body.lower() else "plain"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception as exc:
            path.write_text(path.read_text(encoding="utf-8") + f"\n\nSMTP error: {exc}", encoding="utf-8")

    return str(path)


@celery_app.task(name="tasks.jobs.send_daily_deadline_reminders")
def send_daily_deadline_reminders():
    import sys
    from pathlib import Path as P

    backend = P(__file__).resolve().parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from models.database import get_upcoming_deadline_reminders

    today = date.today()
    rows = get_upcoming_deadline_reminders(within_days=3)
    if not rows:
        path = _send_notification(
            "Daily deadline reminders",
            f"No upcoming deadlines within 3 days as of {today.isoformat()}.",
            ADMIN_EMAIL,
        )
        return {"sent": 0, "notification": path}

    lines = [f"Deadline reminders for {today.isoformat()}:", ""]
    for email, name, job_title, company_name, deadline in rows:
        lines.append(
            f"- {name} ({email}): '{job_title}' at {company_name} closes on {deadline}"
        )
    body = "\n".join(lines)
    path = _send_notification("Placement Portal - Upcoming deadlines", body, ADMIN_EMAIL)
    return {"sent": len(rows), "notification": path}


@celery_app.task(name="tasks.jobs.send_monthly_activity_report")
def send_monthly_activity_report():
    import sys
    from pathlib import Path as P

    backend = P(__file__).resolve().parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from models.database import get_monthly_stats

    stats = get_monthly_stats()
    html = f"""
    <html><body>
      <h2>Monthly Placement Activity Report</h2>
      <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
      <ul>
        <li>Drives conducted (approved/closed): {stats['drives']}</li>
        <li>Total applications: {stats['applications']}</li>
        <li>Students selected: {stats['selected']}</li>
        <li>Active students: {stats['students']}</li>
        <li>Approved companies: {stats['companies']}</li>
      </ul>
    </body></html>
    """
    path = _send_notification("Monthly Placement Activity Report", html, ADMIN_EMAIL)
    return {"stats": stats, "notification": path}


@celery_app.task(name="tasks.jobs.export_student_applications_csv")
def export_student_applications_csv(user_id, student_profile_id):
    import sys
    from pathlib import Path as P

    backend = P(__file__).resolve().parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from models.database import get_applications_export_rows, get_student_profile

    _ensure_dirs()
    profile = get_student_profile(user_id)
    rows = get_applications_export_rows(student_profile_id)
    filename = f"applications_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORT_FOLDER / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Student ID", "Student Name", "Company Name", "Drive Title", "Application Status", "Application Date", "Interview Date"]
        )
        student_name = profile[2] if profile else ""
        for r in rows:
            writer.writerow(
                [
                    student_profile_id,
                    student_name,
                    r[0],
                    r[1],
                    r[2],
                    r[3],
                    r[4] or "",
                ]
            )

    alert = _send_notification(
        "CSV export ready",
        f"Your application history export is ready: {filename}",
        profile[2] if False else ADMIN_EMAIL,
    )
    # Prefer student email if available via users join — keep simple alert file for demo
    return {
        "success": True,
        "filename": filename,
        "filepath": str(filepath),
        "alert": alert,
        "count": len(rows),
    }
