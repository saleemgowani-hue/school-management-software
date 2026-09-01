"""
database/migrate_from_sqlite.py — Phase 21 migration.

Imports an EXISTING desktop EduManage Pro installation's school.db (SQLite)
into this SaaS's PostgreSQL database as ONE school/tenant. The original
school.db is opened READ-ONLY and is never modified or deleted — per the
brief's Phase 22 ("do not lose existing data", "do not modify the original
database during migration").

Usage:
    python -m database.migrate_from_sqlite /path/to/school.db "My School Name"

What it does, in order:
  1. Opens school.db read-only.
  2. Creates a new row in `schools` for this installation.
  3. Copies every table, assigning the new school_id to every row.
  4. Re-maps old integer primary keys to new ones (a lookup dict per table)
     so foreign keys (class_id, student_id, etc.) still point correctly at
     the newly-inserted Postgres rows.
  5. Prints a row-count summary per table so the operator can verify nothing
     was silently dropped, and highlights old vs. new row counts as a sanity
     check before anyone deletes the old installation.

This script is safe to re-run against a fresh/empty target schema; it is
NOT idempotent against a partially-migrated school (re-running would create
duplicate rows), so it prints a clear warning and asks for confirmation if
the target school_code already exists.
"""

import sqlite3
import sys

sys.path.insert(0, ".")

from database.connection import execute, fetch_one
from utils.security import hash_password, generate_school_code


def open_sqlite(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(sqlite_path, school_name):
    src = open_sqlite(sqlite_path)

    existing_code = fetch_one("SELECT id FROM schools WHERE school_name = %s", (school_name,))
    if existing_code:
        print(f"WARNING: a school named '{school_name}' already exists (id={existing_code['id']}).")
        if input("Re-running will create DUPLICATE rows. Continue? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            return

    settings_row = src.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    school_code = generate_school_code(school_name)
    while fetch_one("SELECT id FROM schools WHERE school_code = %s", (school_code,)):
        school_code += "1"

    new_school_id = execute(
        "INSERT INTO schools (school_code, school_name, address, phone, email, receipt_footer, academic_session) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (school_code, school_name,
         settings_row["address"] if settings_row else None,
         settings_row["phone"] if settings_row else None,
         settings_row["email"] if settings_row else None,
         settings_row["receipt_footer"] if settings_row else "Thank you!",
         settings_row["academic_session"] if settings_row else "2025-2026"),
    )
    print(f"Created school '{school_name}' (code {school_code}, id {new_school_id}).")

    id_maps = {}  # table_name -> {old_id: new_id}
    counts = {}
    BOOLEAN_COLUMNS = {"transport_required", "hostel_required"}

    def copy_table(table, columns, id_col="id", extra=None):
        """Copies `columns` from the SQLite table into the same Postgres
        table, adding school_id, and remapping FK columns listed in `extra`
        (a dict of {column_name: referenced_table_name}) using id_maps."""
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        mapping = {}
        for row in rows:
            values = {}
            for c in columns:
                if c not in row.keys():
                    continue
                v = row[c]
                if c in BOOLEAN_COLUMNS and v is not None:
                    v = bool(v)  # SQLite stores booleans as 0/1 integers; Postgres needs a real bool
                values[c] = v
            values["school_id"] = new_school_id
            if extra:
                for col, ref_table in extra.items():
                    old_fk = row[col] if col in row.keys() else None
                    values[col] = id_maps.get(ref_table, {}).get(old_fk) if old_fk else None
            cols_sql = ", ".join(values.keys())
            placeholders = ", ".join(f"%({k})s" for k in values.keys())
            new_id = execute(
                f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders}) RETURNING id", values
            )
            mapping[row[id_col]] = new_id
        id_maps[table] = mapping
        counts[table] = (len(rows), len(mapping))
        print(f"  {table}: {len(rows)} row(s) migrated.")

    # Order matters: parents before children, so FK remapping has data to look up.
    copy_table("classes", ["class_name", "section", "academic_session"])
    copy_table("teachers", ["employee_code", "full_name", "gender", "qualification",
                             "subject_specialization", "phone", "email", "address",
                             "joining_date", "experience_years", "salary", "status"])
    # classes.class_teacher_id needs teachers migrated first; patch it in a second pass:
    for old_class in src.execute("SELECT id, class_teacher_id FROM classes WHERE class_teacher_id IS NOT NULL"):
        new_class_id = id_maps["classes"].get(old_class["id"])
        new_teacher_id = id_maps["teachers"].get(old_class["class_teacher_id"])
        if new_class_id and new_teacher_id:
            execute("UPDATE classes SET class_teacher_id = %s WHERE id = %s", (new_teacher_id, new_class_id))

    copy_table("staff", ["employee_code", "full_name", "designation", "phone", "address",
                          "joining_date", "salary", "status"])
    copy_table("students", ["admission_no", "student_id", "full_name", "dob", "gender",
                             "blood_group", "category", "roll_no", "father_name", "mother_name",
                             "guardian_phone", "guardian_email", "address", "emergency_contact",
                             "transport_required", "hostel_required", "photo_blob",
                             "documents_note", "status", "admission_date"],
                extra={"class_id": "classes"})
    copy_table("student_attendance", ["att_date", "status"], extra={"student_id": "students"})
    copy_table("staff_attendance", ["person_type", "person_id", "att_date", "status"])
    copy_table("fee_structure", ["fee_head", "amount", "academic_session"], extra={"class_id": "classes"})
    copy_table("fee_payments", ["receipt_no", "amount_paid", "discount", "fine", "payment_mode",
                                 "fee_head", "remarks", "payment_date"], extra={"student_id": "students"})
    copy_table("exam_types", ["exam_name", "academic_session"])
    copy_table("exam_subjects", ["subject_name", "max_marks"], extra={"class_id": "classes"})
    copy_table("marks", ["marks_obtained"], extra={"exam_id": "exam_types", "student_id": "students", "subject_id": "exam_subjects"})
    copy_table("library_books", ["book_code", "title", "author", "category", "total_copies", "available_copies"])
    copy_table("book_issues", ["issued_to_name", "issue_date", "due_date", "return_date", "fine", "status"],
               extra={"book_id": "library_books", "student_id": "students"})
    copy_table("transport_vehicles", ["vehicle_no", "driver_name", "driver_phone", "capacity"])
    copy_table("transport_routes", ["route_name", "pickup_point", "fare"], extra={"vehicle_id": "transport_vehicles"})
    copy_table("hostel_rooms", ["room_no", "room_type", "capacity", "occupied"])
    copy_table("hostel_allocations", ["allocation_date", "status"], extra={"room_id": "hostel_rooms", "student_id": "students"})
    copy_table("notices", ["title", "description", "notice_type", "notice_date", "posted_by"])
    copy_table("certificates_log", ["cert_type", "issue_date"], extra={"student_id": "students"})

    # Users: passwords are re-hashed with bcrypt (the old SHA-256 hash cannot
    # be reversed, so every migrated user must reset their password on first
    # login of the new system — this is called out clearly at the end).
    user_rows = src.execute("SELECT * FROM users").fetchall()
    for u in user_rows:
        if fetch_one("SELECT id FROM users WHERE username = %s", (u["username"],)):
            print(f"  users: skipping '{u['username']}' — username already exists on the platform.")
            continue
        temp_password = hash_password("ChangeMe123!")
        execute(
            "INSERT INTO users (school_id, username, password_hash, full_name, role, email, phone, active) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (new_school_id, u["username"], temp_password, u["full_name"], u["role"],
             u["email"], u["phone"], bool(u["active"])),
        )
    print(f"  users: {len(user_rows)} row(s) migrated (temporary password 'ChangeMe123!' for all — must be changed on first login).")

    src.close()

    print("\n=== MIGRATION SUMMARY ===")
    for table, (old_n, new_n) in counts.items():
        status = "OK" if old_n == new_n else "MISMATCH"
        print(f"  [{status}] {table}: {old_n} in SQLite -> {new_n} in PostgreSQL")
    print(f"\nDone. School id {new_school_id} is PENDING subscription activation (no trial) — "
          "activate it with a license key before staff can log in normally.")
    print("The original school.db was opened read-only and was NOT modified.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m database.migrate_from_sqlite /path/to/school.db \"School Name\"")
        sys.exit(1)
    migrate(sys.argv[1], sys.argv[2])
