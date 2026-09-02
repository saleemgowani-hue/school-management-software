"""
services/school_service.py — everything that operates above the level of a
single school's academic data: tenant registration, subscription state,
license keys, demo-school seeding, and per-school user administration.

This is the one file where functions legitimately take NO school_id (school
registration, by definition, doesn't have one yet) or operate on the
`schools` table itself. Every other service file's functions all take
school_id as their first parameter — see services/academic_service.py etc.
"""

import os
import random
from datetime import date, datetime, timedelta

from database.connection import fetch_one, fetch_all, execute
from utils.security import hash_password, generate_license_keys, generate_school_code
import config

LICENSE_KEY_FILE = "license_keys.txt"


# ---------------------------------------------------------------------------
# School registration (Phase 4)
# ---------------------------------------------------------------------------

def _unique_school_code(school_name: str) -> str:
    base = generate_school_code(school_name)
    code = base
    suffix = 1
    while fetch_one("SELECT id FROM schools WHERE school_code = %s", (code,)):
        suffix += 1
        code = f"{base}{suffix}"
    return code


def register_school(school_name, address, phone, email, principal_name,
                     admin_username, admin_password, admin_full_name):
    """Creates the school (tenant) row AND its first Super Admin account
    in one transaction-like sequence. Returns (ok, message, school_id)."""
    from auth.authentication import signup_user  # local import avoids a circular import

    school_name = (school_name or "").strip()
    admin_username = (admin_username or "").strip()

    if not school_name or not admin_username or not admin_password or not admin_full_name:
        return False, "School Name, Admin Username, Admin Name and Password are required.", None
    if len(admin_password) < 6:
        return False, "Password must be at least 6 characters long.", None
    if fetch_one("SELECT id FROM users WHERE username = %s", (admin_username,)):
        return False, "That admin username is already taken. Please choose another.", None

    school_code = _unique_school_code(school_name)
    school_id = execute(
        "INSERT INTO schools (school_code, school_name, address, phone, email, principal_name) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (school_code, school_name, address, phone, email, principal_name),
    )

    execute(
        "INSERT INTO users (school_id, username, password_hash, full_name, role, email) "
        "VALUES (%s,%s,%s,%s,'Super Admin',%s)",
        (school_id, admin_username, hash_password(admin_password), admin_full_name, email),
    )

    return True, f"School registered successfully! Your School Code is {school_code}.", school_id


# ---------------------------------------------------------------------------
# Subscription (Phase 7) — belongs to the SCHOOL, not the user.
# See docs/SAAS_ARCHITECTURE.md "Conflict 1" for why.
# ---------------------------------------------------------------------------

def get_subscription_status(school_id: int) -> dict:
    school = fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
    if not school:
        return {"status": "not_found", "days_left": 0, "plan": None}

    if school["is_demo"]:
        return {"status": "active", "days_left": 9999, "plan": "demo"}

    if school["subscription_status"] == "suspended":
        return {"status": "suspended", "days_left": 0, "plan": school["subscription_plan"]}

    if school["subscription_expiry"]:
        today = date.today()
        expiry = school["subscription_expiry"]
        if isinstance(expiry, str):
            expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
        if today > expiry:
            return {"status": "expired", "days_left": 0, "plan": school["subscription_plan"]}
        return {"status": "active", "days_left": (expiry - today).days, "plan": school["subscription_plan"]}

    return {"status": "pending", "days_left": 0, "plan": None}


def activate_subscription(school_id: int, key_input: str):
    """Activates a subscription for a whole school using a shared
    platform-wide monthly/yearly key — mirrors the original desktop app's
    key format and validity periods, just re-targeted at schools instead of
    individual users (Conflict 1 in docs/SAAS_ARCHITECTURE.md)."""
    school = fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
    if school and school["is_demo"]:
        return False, "Subscription changes are disabled for the Demo school."

    key_row = fetch_one("SELECT * FROM license_keys WHERE license_key = %s", (key_input.strip(),))
    if not key_row:
        return False, "Invalid license key. Please check and try again."
    if key_row["used"]:
        return False, "This license key has already been used by another school."

    plan_type = key_row["plan_type"] or "yearly"
    validity_days = config.PLAN_VALIDITY_DAYS.get(plan_type, config.YEARLY_VALIDITY_DAYS)
    start = date.today()
    expiry = start + timedelta(days=validity_days)

    execute(
        "UPDATE license_keys SET used = TRUE, used_by_school_id = %s, used_at = %s WHERE id = %s",
        (school_id, datetime.now(), key_row["id"]),
    )
    execute(
        "UPDATE schools SET subscription_plan=%s, subscription_status='active', "
        "subscription_start=%s, subscription_expiry=%s, license_key_used=%s, updated_at=now() "
        "WHERE id = %s",
        (plan_type, start, expiry, key_row["license_key"], school_id),
    )
    plan_label = "Monthly" if plan_type == "monthly" else "Yearly"
    return True, f"{plan_label} subscription activated! Valid until {expiry.strftime('%d %b %Y')}."


def load_or_create_license_key_file(n_monthly, n_yearly):
    if os.path.exists(LICENSE_KEY_FILE):
        with open(LICENSE_KEY_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip().upper().startswith("EDU-")]
        monthly = [l for l in lines if l.upper().startswith("EDU-M-")]
        yearly = [l for l in lines if l.upper().startswith("EDU-Y-")]
        if monthly and yearly:
            return monthly, yearly

    monthly = generate_license_keys(n_monthly, prefix="EDU-M")
    yearly = generate_license_keys(n_yearly, prefix="EDU-Y")
    with open(LICENSE_KEY_FILE, "w", encoding="utf-8") as f:
        f.write("# EDUMANAGE PRO -- SCHOOL SUBSCRIPTION KEYS\n# " + "=" * 58 + "\n\n")
        f.write(f"# ---- MONTHLY KEYS ({len(monthly)}) ----\n")
        f.writelines(k + "\n" for k in monthly)
        f.write(f"\n# ---- YEARLY KEYS ({len(yearly)}) ----\n")
        f.writelines(k + "\n" for k in yearly)
    return monthly, yearly


def sync_license_keys():
    """Idempotent — safe to call on every app startup. Never invalidates a
    key that has already been used."""
    monthly, yearly = load_or_create_license_key_file(config.TOTAL_MONTHLY_KEYS, config.TOTAL_YEARLY_KEYS)
    for k in monthly:
        execute("INSERT INTO license_keys (license_key, plan_type) VALUES (%s,'monthly') ON CONFLICT DO NOTHING", (k,))
    for k in yearly:
        execute("INSERT INTO license_keys (license_key, plan_type) VALUES (%s,'yearly') ON CONFLICT DO NOTHING", (k,))


# ---------------------------------------------------------------------------
# Demo account (Phase 8)
# ---------------------------------------------------------------------------

MIN_DEMO_STUDENTS = 20  # below this, treat the demo school as under-seeded and top it up

DEMO_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Anika", "Navya", "Priya", "Riya",
]
DEMO_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Reddy", "Nair", "Iyer", "Joshi",
    "Mehta", "Chopra", "Malhotra", "Rao", "Desai",
]


def ensure_demo_school():
    """Idempotent — creates the demo school + demo admin + sample data
    exactly once. Safe to call on every app startup. If a demo school
    already exists but was seeded by an older, thinner version of this
    function, top it up to the current sample-data set automatically."""
    existing = fetch_one("SELECT id FROM schools WHERE school_code = %s", (config.DEMO_SCHOOL_CODE,))
    if existing:
        school_id = existing["id"]
        count = fetch_one("SELECT COUNT(*) AS c FROM students WHERE school_id = %s", (school_id,))
        if not count or count["c"] < MIN_DEMO_STUDENTS:
            _clear_demo_sample_data(school_id)
            _seed_demo_sample_data(school_id)
        return school_id

    school_id = execute(
        "INSERT INTO schools (school_code, school_name, address, phone, email, is_demo, "
        "subscription_status, subscription_plan, subscription_start, subscription_expiry) "
        "VALUES (%s,%s,%s,%s,%s,TRUE,'active','yearly', CURRENT_DATE, CURRENT_DATE + INTERVAL '100 years') "
        "RETURNING id",
        (config.DEMO_SCHOOL_CODE, "Demo Public School", "123 Demo Street", "9999999999", "demo@example.com"),
    )
    execute(
        "INSERT INTO users (school_id, username, password_hash, full_name, role, email) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (school_id, "demo", hash_password("demo1234"), "Demo Administrator", "Super Admin", "demo@example.com"),
    )
    _seed_demo_sample_data(school_id)
    return school_id


def _clear_demo_sample_data(school_id: int):
    """Removes everything a previous _seed_demo_sample_data run could have
    created, in FK-safe order, so it can be reseeded without unique-
    constraint clashes. Scoped to the demo school_id only."""
    for stmt in [
        "DELETE FROM marks WHERE school_id = %s",
        "DELETE FROM certificates_log WHERE school_id = %s",
        "DELETE FROM book_issues WHERE school_id = %s",
        "DELETE FROM hostel_allocations WHERE school_id = %s",
        "DELETE FROM fee_payments WHERE school_id = %s",
        "DELETE FROM student_attendance WHERE school_id = %s",
        "DELETE FROM staff_attendance WHERE school_id = %s",
        "DELETE FROM exam_subjects WHERE school_id = %s",
        "DELETE FROM exam_types WHERE school_id = %s",
        "DELETE FROM fee_structure WHERE school_id = %s",
        "DELETE FROM students WHERE school_id = %s",
        "DELETE FROM teachers WHERE school_id = %s",
        "DELETE FROM notices WHERE school_id = %s",
        "DELETE FROM classes WHERE school_id = %s",
    ]:
        execute(stmt, (school_id,))


def _seed_demo_sample_data(school_id: int):
    """Seeds a realistic-looking demo school: 5 classes, 25 students spread
    across them, 5 teachers, per-class fee structure, a week of attendance,
    and a welcome notice."""
    rng = random.Random(42)  # deterministic — same demo data every reseed
    session = "2025-2026"

    class_ids = []
    for i, grade in enumerate(["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"], start=1):
        class_id = execute(
            "INSERT INTO classes (school_id, class_name, section, academic_session) "
            "VALUES (%s,%s,'A',%s) RETURNING id",
            (school_id, grade, session),
        )
        class_ids.append(class_id)
        execute(
            "INSERT INTO fee_structure (school_id, class_id, fee_head, amount, academic_session) "
            "VALUES (%s,%s,'Tuition Fee',%s,%s)",
            (school_id, class_id, 4000 + i * 500, session),
        )

    student_ids = []
    for i in range(1, 26):
        class_id = class_ids[(i - 1) % len(class_ids)]
        full_name = f"{rng.choice(DEMO_FIRST_NAMES)} {rng.choice(DEMO_LAST_NAMES)}"
        student_id = execute(
            "INSERT INTO students (school_id, admission_no, student_id, full_name, class_id, "
            "guardian_phone, status) VALUES (%s,%s,%s,%s,%s,%s,'Active') RETURNING id",
            (school_id, f"DEMO{i:04d}", f"DEMOSTU{i:03d}", full_name, class_id, f"9876500{i:03d}"),
        )
        student_ids.append(student_id)

    for i in range(1, 6):
        execute(
            "INSERT INTO teachers (school_id, employee_code, full_name, phone, status) "
            "VALUES (%s,%s,%s,%s,'Active')",
            (school_id, f"DEMOTCH{i:02d}", f"{rng.choice(DEMO_FIRST_NAMES)} {rng.choice(DEMO_LAST_NAMES)}", f"9876000{i:03d}"),
        )

    today = date.today()
    for day_offset in range(7):
        att_date = today - timedelta(days=day_offset)
        for student_id in student_ids:
            status = "Present" if rng.random() > 0.1 else "Absent"
            execute(
                "INSERT INTO student_attendance (school_id, student_id, att_date, status) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (school_id, student_id, att_date, status),
            )

    execute(
        "INSERT INTO notices (school_id, title, description, notice_type, posted_by) "
        "VALUES (%s,'Welcome to the Demo!','Explore every module — this is sample data only.','Notice','System')",
        (school_id,),
    )


def is_demo_school(school_id: int) -> bool:
    row = fetch_one("SELECT is_demo FROM schools WHERE id = %s", (school_id,))
    return bool(row and row["is_demo"])


# ---------------------------------------------------------------------------
# Per-school settings & user administration (Settings module)
# ---------------------------------------------------------------------------

def get_school(school_id: int):
    return fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))


def update_school_settings(school_id: int, **fields):
    school = get_school(school_id)
    if school and school["is_demo"]:
        return False, "School settings cannot be changed in the Demo account."
    if not fields:
        return True, "Nothing to update."
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    execute(f"UPDATE schools SET {set_clause}, updated_at = now() WHERE id = %s",
            (*fields.values(), school_id))
    return True, "Settings saved successfully."


def list_school_users(school_id: int):
    return fetch_all(
        "SELECT id, username, full_name, role, active FROM users WHERE school_id = %s ORDER BY full_name",
        (school_id,),
    )


# ---------------------------------------------------------------------------
# Platform Admin — cross-school functions.
# Deliberately separate and distinctly named so no school-scoped page can
# accidentally call them (see docs/SAAS_ARCHITECTURE.md).
# ---------------------------------------------------------------------------

def platform_list_schools():
    return fetch_all(
        "SELECT id, school_code, school_name, is_demo, subscription_plan, "
        "subscription_status, subscription_expiry, created_at "
        "FROM schools ORDER BY created_at DESC"
    )


def platform_get_summary():
    return fetch_one(
        "SELECT COUNT(*) AS total_schools, "
        "COUNT(*) FILTER (WHERE subscription_status='active') AS active_schools, "
        "COUNT(*) FILTER (WHERE subscription_status='expired') AS expired_schools, "
        "COUNT(*) FILTER (WHERE subscription_status='pending') AS pending_schools "
        "FROM schools WHERE is_demo = FALSE"
    )


def platform_suspend_school(school_id: int, suspend: bool = True):
    status = "suspended" if suspend else "active"
    execute("UPDATE schools SET subscription_status = %s, updated_at = now() WHERE id = %s AND is_demo = FALSE",
            (status, school_id))
    return True, f"School {'suspended' if suspend else 'reactivated'}."
