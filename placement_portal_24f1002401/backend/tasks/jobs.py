import csv
import re
import smtplib
import urllib.request
from collections import defaultdict
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


def _plain_text(body):
    text = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _send_notification(subject, body, to_email=None, use_webhook=True):
    """Save a local copy always; optionally email (SMTP) and/or Google Chat webhook."""
    _ensure_dirs()
    recipient = to_email or ADMIN_EMAIL
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject)[:40]
    path = NOTIFICATIONS_FOLDER / f"{stamp}_{safe}.txt"
    path.write_text(f"TO: {recipient}\nSUBJECT: {subject}\n\n{body}", encoding="utf-8")

    if use_webhook and GCHAT_WEBHOOK_URL:
        try:
            import json as _json

            payload = _json.dumps({"text": subject + "\n" + _plain_text(body)}).encode("utf-8")
            req = urllib.request.Request(
                GCHAT_WEBHOOK_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:
            path.write_text(
                path.read_text(encoding="utf-8") + f"\n\nWebhook error: {exc}",
                encoding="utf-8",
            )

    if SMTP_HOST and recipient:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER or "noreply@ppa.local"
            msg["To"] = recipient
            is_html = "<html" in body.lower()
            if is_html:
                msg.attach(MIMEText(_plain_text(body), "plain"))
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception as exc:
            path.write_text(
                path.read_text(encoding="utf-8") + f"\n\nSMTP error: {exc}",
                encoding="utf-8",
            )

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
        return {"sent": 0, "students": 0, "notification": path}

    by_student = defaultdict(list)
    for email, name, job_title, company_name, deadline in rows:
        by_student[(email, name or "Student")].append((job_title, company_name, deadline))

    student_paths = []
    for (email, name), items in by_student.items():
        lines = [
            f"Hi {name},",
            "",
            "Reminder: these placement drive application deadlines are coming up:",
            "",
        ]
        for job_title, company_name, deadline in items:
            lines.append(f"- '{job_title}' at {company_name} closes on {deadline}")
        lines.extend(["", "Please apply or complete your application before the deadline.", "", "- Placement Portal"])
        student_paths.append(
            _send_notification(
                "Placement Portal - Application deadline reminder",
                "\n".join(lines),
                email,
                use_webhook=False,
            )
        )

    digest_lines = [f"Deadline reminders for {today.isoformat()} (sent to {len(by_student)} students):", ""]
    for email, name, job_title, company_name, deadline in rows:
        digest_lines.append(
            f"- {name} ({email}): '{job_title}' at {company_name} closes on {deadline}"
        )
    admin_path = _send_notification(
        "Placement Portal - Daily reminder digest",
        "\n".join(digest_lines),
        ADMIN_EMAIL,
        use_webhook=True,
    )
    return {
        "sent": len(rows),
        "students": len(by_student),
        "student_notifications": student_paths,
        "notification": admin_path,
    }


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
      <p>Report period: <strong>{stats['period_label']}</strong>
         ({stats['period_start']} to {stats['period_end']})</p>
      <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
      <ul>
        <li>Drives conducted (deadline in period, approved/closed): {stats['drives']}</li>
        <li>Students applied (unique): {stats['students_applied']}</li>
        <li>Total applications: {stats['applications']}</li>
        <li>Students selected: {stats['selected']}</li>
        <li>Approved companies (overall): {stats['companies']}</li>
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

    from models.database import find_user_by_id, get_applications_export_rows, get_student_profile

    _ensure_dirs()
    profile = get_student_profile(user_id)
    user_row = find_user_by_id(user_id)
    student_email = user_row[1] if user_row else None
    student_name = profile[2] if profile else ""
    rows = get_applications_export_rows(student_profile_id)
    filename = f"applications_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORT_FOLDER / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Student ID",
                "Student Name",
                "Company Name",
                "Drive Title",
                "Application Status",
                "Application Date",
                "Interview Date",
            ]
        )
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
        (
            f"Hi {student_name or 'Student'},\n\n"
            f"Your placement application history export is ready.\n"
            f"Filename: {filename}\n"
            f"Rows exported: {len(rows)}\n\n"
            f"Download it from your Student Dashboard (Export CSV) or "
            f"/api/exports/{filename}\n"
        ),
        student_email or ADMIN_EMAIL,
        use_webhook=False,
    )
    return {
        "success": True,
        "filename": filename,
        "filepath": str(filepath),
        "alert": alert,
        "count": len(rows),
        "notified": student_email or ADMIN_EMAIL,
    }
