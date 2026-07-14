import sqlite3
from pathlib import Path

DB_NAME = "placement_portal.db"


def get_connection():
    db_path = Path(__file__).resolve().parent.parent / DB_NAME
    conn = sqlite3.connect(db_path)
    return conn


def _ensure_column(cur, table, column, col_type):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS student_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT,
            branch TEXT,
            cgpa REAL,
            year INTEGER,
            resume_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS company_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_name TEXT,
            hr_contact TEXT,
            website TEXT,
            approval_status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS placement_drive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            job_description TEXT,
            eligibility_branch TEXT,
            eligibility_cgpa REAL,
            eligibility_year INTEGER,
            application_deadline TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (company_id) REFERENCES company_profile(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS application (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            drive_id INTEGER NOT NULL,
            application_date TEXT,
            status TEXT DEFAULT 'applied',
            UNIQUE(student_id, drive_id),
            FOREIGN KEY (student_id) REFERENCES student_profile(id),
            FOREIGN KEY (drive_id) REFERENCES placement_drive(id)
        );
    """)

    _ensure_column(cur, "application", "interview_date", "TEXT")
    _ensure_column(cur, "application", "interview_notes", "TEXT")

    conn.commit()
    conn.close()


def create_default_admin():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE role = 'admin';")
    row = cur.fetchone()
    if row is None:
        cur.execute("""
            INSERT INTO users (email, password, role, is_active)
            VALUES (?, ?, ?, ?);
        """, ("admin@ppa.com", "admin123", "admin", 1))
        print("Default admin created: admin@ppa.com / admin123")
    else:
        print("Admin already exists with id:", row[0])
    conn.commit()
    conn.close()


def find_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, password, role, is_active FROM users WHERE email = ?;",
        (email,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def find_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, password, role, is_active FROM users WHERE id = ?;",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def create_student_user(email, password, name, branch, cgpa, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (email, password, role, is_active)
        VALUES (?, ?, 'student', 1);
    """, (email, password))
    user_id = cur.lastrowid
    cur.execute("""
        INSERT INTO student_profile (user_id, name, branch, cgpa, year)
        VALUES (?, ?, ?, ?, ?);
    """, (user_id, name, branch, cgpa, year))
    conn.commit()
    conn.close()
    return user_id


def create_company_user(email, password, company_name, hr_contact, website):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (email, password, role, is_active)
        VALUES (?, ?, 'company', 1);
    """, (email, password))
    user_id = cur.lastrowid
    cur.execute("""
        INSERT INTO company_profile (user_id, company_name, hr_contact, website)
        VALUES (?, ?, ?, ?);
    """, (user_id, company_name, hr_contact, website))
    conn.commit()
    conn.close()
    return user_id


def create_placement_drive(
    company_profile_id,
    job_title,
    job_description,
    eligibility_branch,
    eligibility_cgpa,
    eligibility_year,
    application_deadline,
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO placement_drive (
            company_id, job_title, job_description,
            eligibility_branch, eligibility_cgpa,
            eligibility_year, application_deadline, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending');
    """, (
        company_profile_id,
        job_title,
        job_description,
        eligibility_branch,
        eligibility_cgpa,
        eligibility_year,
        application_deadline,
    ))
    drive_id = cur.lastrowid
    conn.commit()
    conn.close()
    return drive_id


def get_company_profile_by_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company_name, approval_status, hr_contact, website
        FROM company_profile
        WHERE user_id = ?;
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_approved_drives_for_student(user_id, search=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, branch, cgpa, year
        FROM student_profile
        WHERE user_id = ?;
    """, (user_id,))
    profile = cur.fetchone()
    if profile is None:
        conn.close()
        return []

    _sid, _name, branch, cgpa, year = profile
    cur.execute("""
        SELECT d.id, d.job_title, c.company_name, d.application_deadline, d.status,
               d.eligibility_branch, d.eligibility_cgpa, d.eligibility_year
        FROM placement_drive d
        JOIN company_profile c ON d.company_id = c.id
        WHERE d.status = 'approved'
          AND c.approval_status = 'approved';
    """)
    rows = cur.fetchall()
    conn.close()

    student_branch = (branch or "").strip().upper()
    student_cgpa = float(cgpa) if cgpa is not None else 0.0
    student_year = int(year) if year is not None else 0
    q = (search or "").strip().lower()

    matched = []
    for row in rows:
        drive_id, job_title, company_name, deadline, status, elig_branch, elig_cgpa, elig_year = row

        if elig_branch and elig_branch.strip():
            allowed = [b.strip().upper() for b in elig_branch.replace("/", ",").split(",") if b.strip()]
            if student_branch not in allowed:
                continue
        if elig_cgpa is not None and student_cgpa < float(elig_cgpa):
            continue
        if elig_year is not None and int(elig_year) != 0 and student_year != int(elig_year):
            continue
        if q and q not in (job_title or "").lower() and q not in (company_name or "").lower():
            continue
        matched.append((drive_id, job_title, company_name, deadline, status))
    return matched


def get_student_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, name, branch, cgpa, year, resume_path
        FROM student_profile
        WHERE user_id = ?;
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def student_is_eligible_for_drive(user_id, drive_id):
    drives = get_approved_drives_for_student(user_id)
    return any(d[0] == drive_id for d in drives)


def get_drive_by_id(drive_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company_id, job_title, status, application_deadline
        FROM placement_drive WHERE id = ?;
    """, (drive_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_application(student_profile_id, drive_id, application_date):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO application (student_id, drive_id, application_date, status)
            VALUES (?, ?, ?, 'applied');
        """, (student_profile_id, drive_id, application_date))
        conn.commit()
        created = True
    except sqlite3.IntegrityError:
        created = False
    conn.close()
    return created


def get_all_drives_with_company(search=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, c.company_name, d.job_title, d.status, d.application_deadline
        FROM placement_drive d
        JOIN company_profile c ON d.company_id = c.id
        ORDER BY d.id DESC;
    """)
    rows = cur.fetchall()
    conn.close()
    q = (search or "").strip().lower()
    if not q:
        return rows
    return [
        r for r in rows
        if q in str(r[0]).lower() or q in (r[1] or "").lower() or q in (r[2] or "").lower()
    ]


def set_drive_status(drive_id, new_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE placement_drive SET status = ? WHERE id = ?;", (new_status, drive_id))
    conn.commit()
    conn.close()


def get_all_companies(search=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company_name, approval_status, hr_contact, website
        FROM company_profile
        ORDER BY company_name;
    """)
    rows = cur.fetchall()
    conn.close()
    q = (search or "").strip().lower()
    if not q:
        return rows
    return [
        r for r in rows
        if q in str(r[0]).lower() or q in (r[1] or "").lower() or q in (r[3] or "").lower()
    ]


def set_company_status(company_id, new_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE company_profile SET approval_status = ? WHERE id = ?;",
        (new_status, company_id),
    )
    conn.commit()
    conn.close()


def get_all_students(search=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.name, s.branch, s.cgpa, s.year, u.is_active, u.email
        FROM student_profile s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.name;
    """)
    rows = cur.fetchall()
    conn.close()
    q = (search or "").strip().lower()
    if not q:
        return rows
    return [
        r for r in rows
        if q in str(r[0]).lower()
        or q in (r[1] or "").lower()
        or q in (r[2] or "").lower()
        or q in (r[6] or "").lower()
    ]


def set_student_active(student_profile_id, is_active):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id FROM users u
        JOIN student_profile s ON s.user_id = u.id
        WHERE s.id = ?;
    """, (student_profile_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE users SET is_active = ? WHERE id = ?;",
            (1 if is_active else 0, row[0]),
        )
        conn.commit()
    conn.close()


def set_drive_status_for_company(company_id, new_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE placement_drive SET status = ? WHERE company_id = ?;",
        (new_status, company_id),
    )
    conn.commit()
    conn.close()


def get_drives_for_company_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.job_title, d.job_description, d.status,
               (SELECT COUNT(*) FROM application a WHERE a.drive_id = d.id) AS applicant_count
        FROM placement_drive d
        JOIN company_profile c ON d.company_id = c.id
        WHERE c.user_id = ?;
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_applications_with_details():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            a.id, s.name, s.branch, d.id, d.job_title, c.company_name,
            a.application_date, a.status, a.interview_date
        FROM application a
        JOIN student_profile s ON a.student_id = s.id
        JOIN placement_drive d ON a.drive_id = d.id
        JOIN company_profile c ON d.company_id = c.id
        ORDER BY a.id DESC;
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_applications_for_student(student_profile_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, d.job_title, c.company_name, a.status, a.application_date, a.interview_date
        FROM application a
        JOIN placement_drive d ON a.drive_id = d.id
        JOIN company_profile c ON d.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.id DESC;
    """, (student_profile_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_applications_export_rows(student_profile_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.company_name, d.job_title, a.status, a.application_date, a.interview_date
        FROM application a
        JOIN placement_drive d ON a.drive_id = d.id
        JOIN company_profile c ON d.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.id DESC;
    """, (student_profile_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_student_profile(user_id, full_name, branch, cgpa, year=None):
    conn = get_connection()
    cur = conn.cursor()
    if year is None:
        cur.execute("""
            UPDATE student_profile SET name = ?, branch = ?, cgpa = ?
            WHERE user_id = ?;
        """, (full_name, branch, cgpa, user_id))
    else:
        cur.execute("""
            UPDATE student_profile SET name = ?, branch = ?, cgpa = ?, year = ?
            WHERE user_id = ?;
        """, (full_name, branch, cgpa, year, user_id))
    conn.commit()
    updated = cur.rowcount
    conn.close()
    return updated > 0


def set_student_resume(user_id, resume_path):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE student_profile SET resume_path = ? WHERE user_id = ?;",
        (resume_path, user_id),
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    return updated > 0


def get_admin_stats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM student_profile;")
    students = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM company_profile;")
    companies = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM placement_drive;")
    drives = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM application;")
    applications = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM application WHERE status = 'selected';")
    selected = cur.fetchone()[0]
    conn.close()
    return {
        "students": students,
        "companies": companies,
        "drives": drives,
        "applications": applications,
        "selected": selected,
    }


def get_monthly_stats(year=None, month=None):
    """Activity stats for one calendar month (defaults to previous month on the 1st, else current)."""
    from calendar import monthrange
    from datetime import date

    today = date.today()
    if year is None or month is None:
        if today.day == 1:
            # Scheduled run on the 1st → report previous month
            if today.month == 1:
                year, month = today.year - 1, 12
            else:
                year, month = today.year, today.month - 1
        else:
            year, month = today.year, today.month

    start = date(year, month, 1).isoformat()
    last_day = monthrange(year, month)[1]
    # exclusive upper bound (first day of next month)
    if month == 12:
        end = date(year + 1, 1, 1).isoformat()
    else:
        end = date(year, month + 1, 1).isoformat()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) FROM placement_drive
        WHERE status IN ('approved', 'closed')
          AND application_deadline IS NOT NULL
          AND application_deadline >= ? AND application_deadline < ?;
        """,
        (start, end),
    )
    drives = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM application
        WHERE application_date IS NOT NULL
          AND application_date >= ? AND application_date < ?;
        """,
        (start, end),
    )
    applications = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM application
        WHERE status = 'selected'
          AND application_date IS NOT NULL
          AND application_date >= ? AND application_date < ?;
        """,
        (start, end),
    )
    selected = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(DISTINCT student_id) FROM application
        WHERE application_date IS NOT NULL
          AND application_date >= ? AND application_date < ?;
        """,
        (start, end),
    )
    students_applied = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM company_profile WHERE approval_status = 'approved';"
    )
    companies = cur.fetchone()[0]

    conn.close()
    return {
        "year": year,
        "month": month,
        "period_label": f"{year}-{month:02d}",
        "period_start": start,
        "period_end": date(year, month, last_day).isoformat(),
        "drives": drives,
        "applications": applications,
        "selected": selected,
        "students_applied": students_applied,
        "companies": companies,
    }


def get_applications_for_company_drive(company_user_id, drive_id=None):
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        SELECT a.id, s.name, s.branch, s.cgpa, d.job_title, a.status,
               a.application_date, a.interview_date, a.interview_notes, d.id, s.resume_path
        FROM application a
        JOIN student_profile s ON a.student_id = s.id
        JOIN placement_drive d ON a.drive_id = d.id
        JOIN company_profile c ON d.company_id = c.id
        WHERE c.user_id = ?
    """
    params = [company_user_id]
    if drive_id:
        sql += " AND d.id = ?"
        params.append(drive_id)
    sql += " ORDER BY a.id DESC;"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_application_status(application_id, status, interview_date=None, interview_notes=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE application
        SET status = ?,
            interview_date = COALESCE(?, interview_date),
            interview_notes = COALESCE(?, interview_notes)
        WHERE id = ?;
    """, (status, interview_date, interview_notes, application_id))
    conn.commit()
    updated = cur.rowcount
    conn.close()
    return updated > 0


def company_owns_application(company_user_id, application_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id FROM application a
        JOIN placement_drive d ON a.drive_id = d.id
        JOIN company_profile c ON d.company_id = c.id
        WHERE a.id = ? AND c.user_id = ?;
    """, (application_id, company_user_id))
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_upcoming_deadline_reminders(within_days=3):
    """Eligible active students for approved drives closing within `within_days`."""
    from datetime import date, timedelta

    today = date.today()
    end = today + timedelta(days=within_days)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.job_title, c.company_name, d.application_deadline,
               d.eligibility_branch, d.eligibility_cgpa, d.eligibility_year
        FROM placement_drive d
        JOIN company_profile c ON d.company_id = c.id
        WHERE d.status = 'approved'
          AND c.approval_status = 'approved'
          AND d.application_deadline IS NOT NULL;
    """)
    drives = cur.fetchall()
    cur.execute("""
        SELECT u.email, s.name, s.branch, s.cgpa, s.year
        FROM student_profile s
        JOIN users u ON s.user_id = u.id
        WHERE u.is_active = 1;
    """)
    students = cur.fetchall()
    conn.close()

    result = []
    for (
        _drive_id,
        job_title,
        company_name,
        deadline,
        elig_branch,
        elig_cgpa,
        elig_year,
    ) in drives:
        try:
            d = date.fromisoformat(str(deadline)[:10])
        except ValueError:
            continue
        if not (today <= d <= end):
            continue

        for email, name, branch, cgpa, year in students:
            student_branch = (branch or "").strip().upper()
            student_cgpa = float(cgpa or 0)
            student_year = int(year or 0)
            if elig_branch:
                allowed = [
                    b.strip().upper()
                    for b in elig_branch.replace("/", ",").split(",")
                    if b.strip()
                ]
                if student_branch not in allowed:
                    continue
            if elig_cgpa is not None and student_cgpa < float(elig_cgpa):
                continue
            if elig_year is not None and int(elig_year) != 0 and student_year != int(elig_year):
                continue
            result.append((email, name, job_title, company_name, deadline))
    return result
