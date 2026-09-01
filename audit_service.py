"""services/audit_service.py — records important actions per Phase 20.
Never stores passwords or password hashes."""

from database.connection import execute, df

TRACKED_ACTIONS = {
    "login", "logout", "student_create", "student_update", "student_delete",
    "fee_entry", "fee_modify", "user_create", "permission_change", "subscription_change",
}


def log(school_id, user_id, action, details=""):
    execute(
        "INSERT INTO audit_log (school_id, user_id, action, details) VALUES (%s,%s,%s,%s)",
        (school_id, user_id, action, details),
    )


def recent_activity_df(school_id, limit=100):
    return df("""
        SELECT al.created_at AS "When", u.full_name AS "User", al.action AS "Action", al.details AS "Details"
        FROM audit_log al LEFT JOIN users u ON u.id = al.user_id
        WHERE al.school_id = %(sid)s ORDER BY al.created_at DESC LIMIT %(lim)s
    """, {"sid": school_id, "lim": limit})
