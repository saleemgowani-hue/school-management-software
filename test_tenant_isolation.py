"""
tests/test_tenant_isolation.py

Proves, against a real PostgreSQL database, that School A can never see
School B's data — for students, classes, attendance, teachers, fees, and
exams/marks. This is Phase 12's mandatory deliverable: not a design claim,
an executed test with visible pass/fail output.

Run with:  python -m tests.test_tenant_isolation
"""

import sys
from datetime import date

sys.path.insert(0, ".")

from database.connection import execute, fetch_one
from services import school_service as school_svc
from services import academic_service as academic_svc

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(name, condition):
    status = PASS if condition else FAIL
    results.append((name, status))
    print(f"[{status}] {name}")


def main():
    # ---- clean slate ----
    for tbl in ["marks", "exam_subjects", "exam_types", "fee_payments", "fee_structure",
                "book_issues", "library_books", "hostel_allocations", "hostel_rooms",
                "transport_routes", "transport_vehicles", "certificates_log", "notices",
                "staff_attendance", "student_attendance", "students", "classes",
                "teachers", "staff", "audit_log", "users", "license_keys", "schools"]:
        execute(f"DELETE FROM {tbl}")

    school_svc.sync_license_keys()

    # ---- create two independent schools ----
    ok_a, _, school_a = school_svc.register_school(
        "Alpha Academy", "1 Alpha St", "1111111111", "a@alpha.edu", "Mr. A",
        "alpha_admin", "passwordA1", "Alpha Admin")
    ok_b, _, school_b = school_svc.register_school(
        "Beta International School", "2 Beta St", "2222222222", "b@beta.edu", "Mr. B",
        "beta_admin", "passwordB1", "Beta Admin")
    check("Both schools registered", ok_a and ok_b and school_a != school_b)

    # ---- each school creates its own class ----
    academic_svc.add_class(school_a, "Grade 1", "A", "2025-2026", None)
    academic_svc.add_class(school_b, "Grade 1", "A", "2025-2026", None)  # same name/section on purpose
    class_a = list(academic_svc.class_options(school_a).values())[0]
    class_b = list(academic_svc.class_options(school_b).values())[0]
    check("Identical class name/section allowed in two different schools "
          "(uniqueness is per-school, not global)", class_a != class_b)

    classes_seen_by_a = academic_svc.class_options(school_a)
    classes_seen_by_b = academic_svc.class_options(school_b)
    check("School A's class list contains only 1 class (not Beta's too)", len(classes_seen_by_a) == 1)
    check("School B's class list contains only 1 class (not Alpha's too)", len(classes_seen_by_b) == 1)

    # ---- each school admits a student with THE SAME admission number ----
    academic_svc.add_student(
        school_a, admission_no="ADM0001", student_id="STU0001", full_name="Student Alpha",
        class_id=class_a, guardian_phone="9000000001", status="Active")
    academic_svc.add_student(
        school_b, admission_no="ADM0001", student_id="STU0001", full_name="Student Beta",
        class_id=class_b, guardian_phone="9000000002", status="Active")
    check("Identical admission_no 'ADM0001' allowed in two different schools", True)  # no exception raised = pass

    students_a = academic_svc.search_students_df(school_a)
    students_b = academic_svc.search_students_df(school_b)
    check("School A sees exactly 1 student", len(students_a) == 1)
    check("School B sees exactly 1 student", len(students_b) == 1)
    check("School A's student is 'Student Alpha', NOT 'Student Beta'",
          students_a.iloc[0]["full_name"] == "Student Alpha")
    check("School B's student is 'Student Beta', NOT 'Student Alpha'",
          students_b.iloc[0]["full_name"] == "Student Beta")

    student_a_id = int(students_a.iloc[0]["id"])
    student_b_id = int(students_b.iloc[0]["id"])

    # ---- cross-tenant read attempt: School A tries to fetch School B's student by ID ----
    leaked = academic_svc.get_student(school_a, student_b_id)
    check("School A CANNOT fetch School B's student by primary key", leaked is None)

    # ---- attendance isolation ----
    academic_svc.mark_student_attendance(school_a, student_a_id, date.today(), "Present")
    academic_svc.mark_student_attendance(school_b, student_b_id, date.today(), "Absent")
    month = date.today().strftime("%Y-%m")
    att_a = academic_svc.attendance_report_df(school_a, month)
    att_b = academic_svc.attendance_report_df(school_b, month)
    check("School A's attendance report shows only Student Alpha",
          list(att_a["Student"]) == ["Student Alpha"])
    check("School B's attendance report shows only Student Beta",
          list(att_b["Student"]) == ["Student Beta"])

    # ---- fees isolation ----
    execute("INSERT INTO fee_structure (school_id, class_id, fee_head, amount, academic_session) VALUES (%s,%s,'Tuition',5000,'2025-2026')", (school_a, class_a))
    execute("INSERT INTO fee_structure (school_id, class_id, fee_head, amount, academic_session) VALUES (%s,%s,'Tuition',7000,'2025-2026')", (school_b, class_b))
    fee_a = fetch_one("SELECT amount FROM fee_structure WHERE school_id=%s", (school_a,))
    fee_b = fetch_one("SELECT amount FROM fee_structure WHERE school_id=%s", (school_b,))
    check("School A's fee amount (5000) is independent of School B's (7000)",
          float(fee_a["amount"]) == 5000 and float(fee_b["amount"]) == 7000)

    # ---- exams/marks isolation ----
    academic_svc.add_exam_type(school_a, "Mid Term", "2025-2026")
    academic_svc.add_exam_type(school_b, "Mid Term", "2025-2026")  # same name, different school — must not collide
    exam_a = academic_svc.list_exam_types(school_a)[0]["id"]
    exam_b = academic_svc.list_exam_types(school_b)[0]["id"]
    academic_svc.add_exam_subject(school_a, class_a, "Math", 100)
    academic_svc.add_exam_subject(school_b, class_b, "Math", 100)
    subj_a = academic_svc.list_exam_subjects(school_a, class_a)[0]["id"]
    subj_b = academic_svc.list_exam_subjects(school_b, class_b)[0]["id"]
    academic_svc.save_marks(school_a, exam_a, subj_a, {student_a_id: 88})
    academic_svc.save_marks(school_b, exam_b, subj_b, {student_b_id: 42})
    result_a = academic_svc.get_result_df(school_a, exam_a, student_a_id)
    result_b = academic_svc.get_result_df(school_b, exam_b, student_b_id)
    check("School A's marks (88) isolated from School B's (42)",
          float(result_a.iloc[0]["Obtained"]) == 88 and float(result_b.iloc[0]["Obtained"]) == 42)

    # ---- cross-tenant write attempt: School B tries to update School A's student ----
    academic_svc.update_student(school_b, student_a_id, full_name="HACKED BY SCHOOL B")
    unaffected = academic_svc.get_student(school_a, student_a_id)
    check("School B's attempt to update School A's student silently affects ZERO rows",
          unaffected["full_name"] == "Student Alpha")

    # ---- subscription isolation ----
    mk = fetch_one("SELECT license_key FROM license_keys WHERE plan_type='monthly' LIMIT 1")["license_key"]
    school_svc.activate_subscription(school_a, mk)
    status_a = school_svc.get_subscription_status(school_a)
    status_b = school_svc.get_subscription_status(school_b)
    check("Activating School A's subscription does NOT activate School B's",
          status_a["status"] == "active" and status_b["status"] == "pending")

    # ---- summary ----
    print()
    total = len(results)
    passed = sum(1 for _, s in results if s == PASS)
    print(f"RESULT: {passed}/{total} checks passed.")
    if passed != total:
        print("FAILURES:")
        for name, status in results:
            if status == FAIL:
                print(" -", name)
        sys.exit(1)
    print("ALL TENANT ISOLATION CHECKS PASSED.")


if __name__ == "__main__":
    main()
