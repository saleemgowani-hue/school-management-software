"""
services/academic_service.py — Classes, Students, Attendance, Exams & Marks.

TENANT SAFETY RULE (applies to every function in every services/*.py file):
`school_id` is always the FIRST parameter, always comes from
`st.session_state.user["school_id"]` in app.py, and is included in the
WHERE clause of every single query below. There is no function here that
can return or modify another school's rows, because school_id is baked
into the SQL text itself, not appended conditionally.
"""

from database.connection import fetch_one, fetch_all, execute, df

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

def list_classes_df(school_id):
    return df("""
        SELECT c.id, c.class_name AS "Class", c.section AS "Section",
               c.academic_session AS "Session",
               COALESCE(t.full_name,'-') AS "Class Teacher",
               (SELECT COUNT(*) FROM students s WHERE s.class_id=c.id AND s.status='Active' AND s.school_id=%(sid)s) AS "Students"
        FROM classes c LEFT JOIN teachers t ON t.id = c.class_teacher_id AND t.school_id = %(sid)s
        WHERE c.school_id = %(sid)s
        ORDER BY c.class_name, c.section
    """, {"sid": school_id})


def class_options(school_id):
    rows = fetch_all(
        "SELECT id, class_name, section FROM classes WHERE school_id=%s ORDER BY class_name, section",
        (school_id,),
    )
    return {f"{r['class_name']} - {r['section']}": r["id"] for r in rows}


def add_class(school_id, class_name, section, session, class_teacher_id):
    try:
        execute(
            "INSERT INTO classes (school_id, class_name, section, academic_session, class_teacher_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (school_id, class_name.strip(), section.strip(), session.strip(), class_teacher_id),
        )
        return True, "Class created successfully."
    except Exception as e:
        if "unique" in str(e).lower():
            return False, "This Class-Section-Session already exists."
        raise


def delete_class(school_id, class_id):
    in_use = fetch_one(
        "SELECT COUNT(*) c FROM students WHERE class_id=%s AND school_id=%s", (class_id, school_id)
    )["c"]
    if in_use > 0:
        return False, "Cannot delete: students are assigned to this class."
    execute("DELETE FROM classes WHERE id=%s AND school_id=%s", (class_id, school_id))
    return True, "Class deleted."


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

def next_admission_no(school_id):
    from datetime import date
    year = date.today().year
    row = fetch_one(
        "SELECT COUNT(*) c FROM students WHERE school_id=%s AND admission_no LIKE %s",
        (school_id, f"ADM{year}%"),
    )
    return f"ADM{year}{row['c'] + 1:04d}"


def next_student_id(school_id):
    row = fetch_one("SELECT COUNT(*) c FROM students WHERE school_id=%s", (school_id,))
    return f"STU{row['c'] + 1:05d}"


def add_student(school_id, **fields):
    fields["school_id"] = school_id
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(f"%({k})s" for k in fields.keys())
    execute(f"INSERT INTO students ({cols}) VALUES ({placeholders})", fields)
    return True


def search_students_df(school_id, query=""):
    sql = """
        SELECT s.*, c.class_name, c.section FROM students s
        LEFT JOIN classes c ON c.id = s.class_id AND c.school_id = s.school_id
        WHERE s.school_id = %(sid)s
    """
    params = {"sid": school_id}
    if query:
        sql += " AND (s.full_name ILIKE %(q)s OR s.admission_no ILIKE %(q)s OR s.student_id ILIKE %(q)s OR s.guardian_phone ILIKE %(q)s)"
        params["q"] = f"%{query}%"
    sql += " ORDER BY s.id DESC"
    return df(sql, params)


def get_student(school_id, student_pk):
    return fetch_one("SELECT * FROM students WHERE id=%s AND school_id=%s", (student_pk, school_id))


def list_active_students(school_id, class_id=None):
    if class_id:
        return fetch_all(
            "SELECT id, full_name, admission_no, roll_no FROM students "
            "WHERE school_id=%s AND class_id=%s AND status='Active' ORDER BY roll_no, full_name",
            (school_id, class_id),
        )
    return fetch_all(
        "SELECT id, full_name, admission_no FROM students WHERE school_id=%s AND status='Active' ORDER BY full_name",
        (school_id,),
    )


def update_student(school_id, student_pk, **fields):
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    execute(
        f"UPDATE students SET {set_clause} WHERE id=%s AND school_id=%s",
        (*fields.values(), student_pk, school_id),
    )
    return True


def promote_students(school_id, student_ids, to_class_id):
    if not student_ids:
        return 0
    execute(
        "UPDATE students SET class_id=%s WHERE school_id=%s AND id = ANY(%s)",
        (to_class_id, school_id, student_ids),
    )
    return len(student_ids)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

def mark_student_attendance(school_id, student_id, att_date, status):
    execute("""
        INSERT INTO student_attendance (school_id, student_id, att_date, status)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (school_id, student_id, att_date) DO UPDATE SET status = EXCLUDED.status
    """, (school_id, student_id, att_date, status))


def get_attendance_for_class_date(school_id, student_ids, att_date):
    if not student_ids:
        return {}
    rows = fetch_all(
        "SELECT student_id, status FROM student_attendance WHERE school_id=%s AND att_date=%s AND student_id = ANY(%s)",
        (school_id, att_date, student_ids),
    )
    return {r["student_id"]: r["status"] for r in rows}


def attendance_report_df(school_id, month, class_id=None):
    sql = """
        SELECT s.full_name AS "Student", sa.att_date AS "Date", sa.status AS "Status"
        FROM student_attendance sa JOIN students s ON s.id = sa.student_id AND s.school_id = sa.school_id
        WHERE sa.school_id = %(sid)s AND to_char(sa.att_date, 'YYYY-MM') = %(month)s
    """
    params = {"sid": school_id, "month": month}
    if class_id:
        sql += " AND s.class_id = %(cid)s"
        params["cid"] = class_id
    sql += " ORDER BY sa.att_date, s.full_name"
    return df(sql, params)


def mark_staff_attendance(school_id, person_type, person_id, att_date, status):
    execute("""
        INSERT INTO staff_attendance (school_id, person_type, person_id, att_date, status)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (school_id, person_type, person_id, att_date) DO UPDATE SET status = EXCLUDED.status
    """, (school_id, person_type, person_id, att_date, status))


# ---------------------------------------------------------------------------
# Exams & Marks
# ---------------------------------------------------------------------------

def add_exam_type(school_id, exam_name, session):
    try:
        execute("INSERT INTO exam_types (school_id, exam_name, academic_session) VALUES (%s,%s,%s)",
                (school_id, exam_name, session))
        return True, "Exam type added."
    except Exception as e:
        if "unique" in str(e).lower():
            return False, "This exam name already exists."
        raise


def list_exam_types(school_id):
    return fetch_all("SELECT id, exam_name FROM exam_types WHERE school_id=%s", (school_id,))


def add_exam_subject(school_id, class_id, subject_name, max_marks):
    try:
        execute("INSERT INTO exam_subjects (school_id, class_id, subject_name, max_marks) VALUES (%s,%s,%s,%s)",
                (school_id, class_id, subject_name, max_marks))
        return True, "Subject added."
    except Exception as e:
        if "unique" in str(e).lower():
            return False, "This subject already exists for the class."
        raise


def list_exam_subjects(school_id, class_id):
    return fetch_all(
        "SELECT id, subject_name, max_marks FROM exam_subjects WHERE school_id=%s AND class_id=%s",
        (school_id, class_id),
    )


def save_marks(school_id, exam_id, subject_id, marks_by_student: dict):
    for student_id, marks in marks_by_student.items():
        execute("""
            INSERT INTO marks (school_id, exam_id, student_id, subject_id, marks_obtained)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (school_id, exam_id, student_id, subject_id) DO UPDATE SET marks_obtained = EXCLUDED.marks_obtained
        """, (school_id, exam_id, student_id, subject_id, marks))


def get_result_df(school_id, exam_id, student_pk):
    return df("""
        SELECT es.subject_name AS "Subject", m.marks_obtained AS "Obtained", es.max_marks AS "Max"
        FROM marks m JOIN exam_subjects es ON es.id = m.subject_id AND es.school_id = m.school_id
        WHERE m.school_id = %(sid)s AND m.exam_id = %(eid)s AND m.student_id = %(stid)s
    """, {"sid": school_id, "eid": exam_id, "stid": student_pk})


def get_class_rank(school_id, exam_id, class_id, student_pk):
    rank_df = df("""
        SELECT m.student_id, SUM(m.marks_obtained) AS total
        FROM marks m JOIN students s ON s.id = m.student_id AND s.school_id = m.school_id
        WHERE m.school_id = %(sid)s AND m.exam_id = %(eid)s AND s.class_id = %(cid)s
        GROUP BY m.student_id ORDER BY total DESC
    """, {"sid": school_id, "eid": exam_id, "cid": class_id})
    if rank_df.empty:
        return "-"
    match = rank_df.reset_index(drop=True).index[rank_df["student_id"] == student_pk]
    return int(match[0]) + 1 if len(match) else "-"
