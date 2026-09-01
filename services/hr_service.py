"""services/hr_service.py — Teachers & Staff. All queries school_id-scoped."""

from database.connection import fetch_one, fetch_all, execute, df


def next_employee_code(school_id, table, prefix):
    row = fetch_one(f"SELECT COUNT(*) c FROM {table} WHERE school_id=%s", (school_id,))
    return f"{prefix}{row['c'] + 1:04d}"


def add_teacher(school_id, **fields):
    code = next_employee_code(school_id, "teachers", "TCH")
    fields.update(school_id=school_id, employee_code=code)
    cols = ", ".join(fields.keys())
    ph = ", ".join(f"%({k})s" for k in fields.keys())
    execute(f"INSERT INTO teachers ({cols}) VALUES ({ph})", fields)
    return code


def teachers_df(school_id):
    return df("""
        SELECT employee_code AS "Code", full_name AS "Name", qualification AS "Qualification",
               subject_specialization AS "Subject", phone AS "Phone", experience_years AS "Experience",
               salary AS "Salary", status AS "Status"
        FROM teachers WHERE school_id=%(sid)s ORDER BY full_name
    """, {"sid": school_id})


def active_teachers(school_id):
    return fetch_all("SELECT id, full_name FROM teachers WHERE school_id=%s AND status='Active' ORDER BY full_name", (school_id,))


def add_staff(school_id, **fields):
    code = next_employee_code(school_id, "staff", "STF")
    fields.update(school_id=school_id, employee_code=code)
    cols = ", ".join(fields.keys())
    ph = ", ".join(f"%({k})s" for k in fields.keys())
    execute(f"INSERT INTO staff ({cols}) VALUES ({ph})", fields)
    return code


def staff_df(school_id):
    return df("""
        SELECT employee_code AS "Code", full_name AS "Name", designation AS "Designation",
               phone AS "Phone", salary AS "Salary", status AS "Status"
        FROM staff WHERE school_id=%(sid)s ORDER BY full_name
    """, {"sid": school_id})


def active_staff(school_id):
    return fetch_all("SELECT id, full_name FROM staff WHERE school_id=%s AND status='Active' ORDER BY full_name", (school_id,))
