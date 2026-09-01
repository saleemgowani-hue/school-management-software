"""services/finance_service.py — Fee Structure & Fee Collection. All queries
school_id-scoped; see services/academic_service.py docstring for the rule."""

from datetime import date

from database.connection import fetch_one, fetch_all, execute, df


def add_fee_structure(school_id, class_id, fee_head, amount, session):
    execute(
        "INSERT INTO fee_structure (school_id, class_id, fee_head, amount, academic_session) VALUES (%s,%s,%s,%s,%s)",
        (school_id, class_id, fee_head, amount, session),
    )


def fee_structure_df(school_id):
    return df("""
        SELECT c.class_name||'-'||c.section AS "Class", f.fee_head AS "Fee Head",
               f.amount AS "Amount", f.academic_session AS "Session"
        FROM fee_structure f JOIN classes c ON c.id=f.class_id AND c.school_id = f.school_id
        WHERE f.school_id = %(sid)s ORDER BY c.class_name
    """, {"sid": school_id})


def class_due_total(school_id, class_id):
    row = fetch_one(
        "SELECT COALESCE(SUM(amount),0) s FROM fee_structure WHERE school_id=%s AND class_id=%s",
        (school_id, class_id),
    )
    return float(row["s"])


def student_paid_total(school_id, student_id):
    row = fetch_one(
        "SELECT COALESCE(SUM(amount_paid),0) s FROM fee_payments WHERE school_id=%s AND student_id=%s",
        (school_id, student_id),
    )
    return float(row["s"])


def next_receipt_no(school_id):
    row = fetch_one("SELECT COUNT(*) c FROM fee_payments WHERE school_id=%s", (school_id,))
    return f"RCPT{date.today().year}{row['c'] + 1:05d}"


def collect_fee(school_id, student_id, amount_paid, discount, fine, payment_mode, fee_head, remarks):
    receipt_no = next_receipt_no(school_id)
    execute("""
        INSERT INTO fee_payments (school_id, receipt_no, student_id, amount_paid, discount, fine,
                                   payment_mode, fee_head, remarks)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (school_id, receipt_no, student_id, amount_paid, discount, fine, payment_mode, fee_head, remarks))
    return receipt_no


def due_list_df(school_id):
    result = df("""
        SELECT s.full_name AS "Student", s.admission_no AS "Admission No",
               c.class_name||'-'||c.section AS "Class",
               COALESCE(fs.total_due,0) AS "Total Due",
               COALESCE(fp.total_paid,0) AS "Total Paid",
               (COALESCE(fs.total_due,0) - COALESCE(fp.total_paid,0)) AS "Balance"
        FROM students s
        LEFT JOIN classes c ON c.id = s.class_id AND c.school_id = s.school_id
        LEFT JOIN (SELECT class_id, SUM(amount) total_due FROM fee_structure WHERE school_id=%(sid)s GROUP BY class_id) fs
               ON fs.class_id = s.class_id
        LEFT JOIN (SELECT student_id, SUM(amount_paid) total_paid FROM fee_payments WHERE school_id=%(sid)s GROUP BY student_id) fp
               ON fp.student_id = s.id
        WHERE s.school_id = %(sid)s AND s.status='Active'
        ORDER BY "Balance" DESC
    """, {"sid": school_id})
    return result[result["Balance"] > 0]


def collection_report_df(school_id, day=None, month=None):
    sql = """
        SELECT fp.receipt_no AS "Receipt", s.full_name AS "Student", fp.fee_head AS "Fee Head",
               fp.amount_paid AS "Amount", fp.payment_mode AS "Mode", fp.payment_date AS "Date"
        FROM fee_payments fp JOIN students s ON s.id = fp.student_id AND s.school_id = fp.school_id
        WHERE fp.school_id = %(sid)s
    """
    params = {"sid": school_id}
    if day:
        sql += " AND fp.payment_date = %(day)s"
        params["day"] = day
    if month:
        sql += " AND to_char(fp.payment_date,'YYYY-MM') = %(month)s"
        params["month"] = month
    return df(sql, params)
