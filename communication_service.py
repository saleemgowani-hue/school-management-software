"""services/communication_service.py — Notice Board & Certificates. All
queries school_id-scoped."""

from database.connection import fetch_all, execute, df


def post_notice(school_id, title, description, notice_type, notice_date, posted_by):
    execute("""
        INSERT INTO notices (school_id, title, description, notice_type, notice_date, posted_by)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (school_id, title, description, notice_type, notice_date, posted_by))


def list_notices(school_id, notice_type=None, limit=None):
    sql = "SELECT * FROM notices WHERE school_id=%s"
    params = [school_id]
    if notice_type and notice_type != "All":
        sql += " AND notice_type=%s"
        params.append(notice_type)
    sql += " ORDER BY notice_date DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return fetch_all(sql, tuple(params))


def log_certificate(school_id, student_id, cert_type):
    execute("INSERT INTO certificates_log (school_id, student_id, cert_type) VALUES (%s,%s,%s)",
            (school_id, student_id, cert_type))


def certificate_log_df(school_id):
    return df("""
        SELECT s.full_name AS "Student", cl.cert_type AS "Certificate Type", cl.issue_date AS "Issued On"
        FROM certificates_log cl JOIN students s ON s.id = cl.student_id AND s.school_id = cl.school_id
        WHERE cl.school_id = %(sid)s ORDER BY cl.issue_date DESC
    """, {"sid": school_id})
