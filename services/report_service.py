"""services/report_service.py — cross-module reports & KPI aggregates for
the dashboard. Every function takes school_id and every query filters on it,
so exports (Excel/CSV) built from these can never contain another school's
rows (Phase 19)."""

from datetime import date

from database.connection import fetch_one, df


def dashboard_kpis(school_id):
    today = date.today()
    total_students = fetch_one("SELECT COUNT(*) c FROM students WHERE school_id=%s AND status='Active'", (school_id,))["c"]
    total_teachers = fetch_one("SELECT COUNT(*) c FROM teachers WHERE school_id=%s AND status='Active'", (school_id,))["c"]
    total_staff = fetch_one("SELECT COUNT(*) c FROM staff WHERE school_id=%s AND status='Active'", (school_id,))["c"]
    today_attendance = fetch_one(
        "SELECT COUNT(*) c FROM student_attendance WHERE school_id=%s AND att_date=%s AND status='Present'",
        (school_id, today))["c"]
    fees_today = fetch_one(
        "SELECT COALESCE(SUM(amount_paid),0) s FROM fee_payments WHERE school_id=%s AND payment_date=%s",
        (school_id, today))["s"]
    total_due = fetch_one("SELECT COALESCE(SUM(amount),0) s FROM fee_structure WHERE school_id=%s", (school_id,))["s"]
    total_paid = fetch_one("SELECT COALESCE(SUM(amount_paid),0) s FROM fee_payments WHERE school_id=%s", (school_id,))["s"]
    library_books = fetch_one("SELECT COALESCE(SUM(total_copies),0) c FROM library_books WHERE school_id=%s", (school_id,))["c"]
    issued_books = fetch_one("SELECT COUNT(*) c FROM book_issues WHERE school_id=%s AND status='Issued'", (school_id,))["c"]
    new_admissions = fetch_one(
        "SELECT COUNT(*) c FROM students WHERE school_id=%s AND admission_date >= CURRENT_DATE - INTERVAL '30 day'",
        (school_id,))["c"]
    return {
        "total_students": total_students, "total_teachers": total_teachers, "total_staff": total_staff,
        "today_attendance": today_attendance, "fees_today": float(fees_today),
        "pending_fees": max(float(total_due) - float(total_paid), 0),
        "library_books": library_books, "issued_books": issued_books, "new_admissions": new_admissions,
    }


def attendance_trend_df(school_id):
    return df("""
        SELECT att_date, SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) AS absent
        FROM student_attendance
        WHERE school_id = %(sid)s AND att_date >= CURRENT_DATE - INTERVAL '14 day'
        GROUP BY att_date ORDER BY att_date
    """, {"sid": school_id})


def students_by_class_df(school_id):
    return df("""
        SELECT c.class_name || '-' || c.section AS class_label, COUNT(s.id) AS cnt
        FROM classes c LEFT JOIN students s ON s.class_id = c.id AND s.status='Active' AND s.school_id = c.school_id
        WHERE c.school_id = %(sid)s GROUP BY c.id, c.class_name, c.section
    """, {"sid": school_id})


def todays_birthdays(school_id):
    from database.connection import fetch_all
    return fetch_all("""
        SELECT full_name, dob FROM students
        WHERE school_id=%s AND status='Active' AND to_char(dob,'MM-DD') = to_char(CURRENT_DATE,'MM-DD')
    """, (school_id,))


REPORT_QUERIES = {
    "Admission Report": """
        SELECT admission_no AS "Admission No", full_name AS "Name", admission_date AS "Admission Date",
               c.class_name||'-'||c.section AS "Class"
        FROM students s LEFT JOIN classes c ON c.id=s.class_id AND c.school_id = s.school_id
        WHERE s.school_id = %(sid)s ORDER BY admission_date DESC
    """,
    "Attendance Report": """
        SELECT s.full_name AS "Student", sa.att_date AS "Date", sa.status AS "Status"
        FROM student_attendance sa JOIN students s ON s.id=sa.student_id AND s.school_id = sa.school_id
        WHERE sa.school_id = %(sid)s ORDER BY sa.att_date DESC
    """,
    "Fee Report": """
        SELECT fp.receipt_no AS "Receipt", s.full_name AS "Student", fp.fee_head AS "Fee Head",
               fp.amount_paid AS "Amount", fp.payment_mode AS "Mode", fp.payment_date AS "Date"
        FROM fee_payments fp JOIN students s ON s.id=fp.student_id AND s.school_id = fp.school_id
        WHERE fp.school_id = %(sid)s ORDER BY fp.payment_date DESC
    """,
    "Exam Report": """
        SELECT et.exam_name AS "Exam", s.full_name AS "Student", es.subject_name AS "Subject",
               m.marks_obtained AS "Marks", es.max_marks AS "Max Marks"
        FROM marks m
        JOIN exam_types et ON et.id=m.exam_id AND et.school_id = m.school_id
        JOIN students s ON s.id=m.student_id AND s.school_id = m.school_id
        JOIN exam_subjects es ON es.id=m.subject_id AND es.school_id = m.school_id
        WHERE m.school_id = %(sid)s
    """,
    "Library Report": """
        SELECT lb.title AS "Book", s.full_name AS "Issued To", bi.issue_date AS "Issue Date",
               bi.due_date AS "Due Date", bi.status AS "Status", bi.fine AS "Fine"
        FROM book_issues bi JOIN library_books lb ON lb.id=bi.book_id AND lb.school_id = bi.school_id
        LEFT JOIN students s ON s.id=bi.student_id AND s.school_id = bi.school_id
        WHERE bi.school_id = %(sid)s ORDER BY bi.issue_date DESC
    """,
    "Teacher Report": """
        SELECT employee_code AS "Code", full_name AS "Name", qualification AS "Qualification",
               subject_specialization AS "Subject", experience_years AS "Experience", status AS "Status"
        FROM teachers WHERE school_id = %(sid)s
    """,
}


def get_report_df(school_id, report_name):
    import pandas as pd
    if report_name == "Salary Report":
        t = df('SELECT employee_code AS "Code", full_name AS "Name", \'Teacher\' AS "Type", salary AS "Salary" '
               'FROM teachers WHERE school_id=%(sid)s', {"sid": school_id})
        s = df('SELECT employee_code AS "Code", full_name AS "Name", \'Staff\' AS "Type", salary AS "Salary" '
               'FROM staff WHERE school_id=%(sid)s', {"sid": school_id})
        return pd.concat([t, s], ignore_index=True)
    return df(REPORT_QUERIES[report_name], {"sid": school_id})
