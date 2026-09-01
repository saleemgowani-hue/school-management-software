# Database Documentation

Full DDL: `database/schema.sql`. This document explains the *why* behind it.

## Tenant Identifier

Every school-owned table has `school_id INTEGER REFERENCES schools(id)`.
`schools` and `license_keys` are the only tables without one — `schools` IS
the tenant registry, and `license_keys` is a platform-wide shared pool
(each key, once used, records `used_by_school_id`).

## Tables & Relationships

| Table | Key relationships | Composite uniqueness |
|---|---|---|
| `schools` | — | `school_code` |
| `license_keys` | `used_by_school_id → schools.id` | `license_key` |
| `users` | `school_id → schools.id` (NULL = Platform Admin) | `username` (global — see SAAS_ARCHITECTURE.md Conflict 2) |
| `audit_log` | `school_id → schools.id`, `user_id → users.id` | — |
| `classes` | `school_id → schools.id` | `(school_id, class_name, section, academic_session)` |
| `students` | `school_id`, `class_id → classes.id` | `(school_id, admission_no)`, `(school_id, student_id)` |
| `student_attendance` | `school_id`, `student_id → students.id` | `(school_id, student_id, att_date)` |
| `teachers` | `school_id → schools.id` | `(school_id, employee_code)` |
| `staff` | `school_id → schools.id` | `(school_id, employee_code)` |
| `staff_attendance` | `school_id` | `(school_id, person_type, person_id, att_date)` |
| `fee_structure` | `school_id`, `class_id → classes.id` | — |
| `fee_payments` | `school_id`, `student_id → students.id` | `(school_id, receipt_no)` |
| `exam_types` | `school_id → schools.id` | `(school_id, exam_name)` |
| `exam_subjects` | `school_id`, `class_id → classes.id` | `(school_id, class_id, subject_name)` |
| `marks` | `school_id`, `exam_id`, `student_id`, `subject_id` | `(school_id, exam_id, student_id, subject_id)` |
| `library_books` | `school_id → schools.id` | `(school_id, book_code)` |
| `book_issues` | `school_id`, `book_id`, `student_id` | — |
| `transport_vehicles` | `school_id → schools.id` | `(school_id, vehicle_no)` |
| `transport_routes` | `school_id`, `vehicle_id → transport_vehicles.id` | — |
| `hostel_rooms` | `school_id → schools.id` | `(school_id, room_no)` |
| `hostel_allocations` | `school_id`, `room_id`, `student_id` | — |
| `notices` | `school_id → schools.id` | — |
| `certificates_log` | `school_id`, `student_id → students.id` | — |

## Indexes

Every table has an index on `school_id` (or a composite index leading with
`school_id`), since every query filters on it — this is the single most
important index for query performance at scale, since it's present in
literally every WHERE clause in `services/*.py`. Additional indexes exist on
the columns the audit identified as commonly filtered/sorted:
`students(school_id, class_id)`, `students(school_id, admission_no)`,
`fee_payments(school_id, payment_date)`, `fee_payments(school_id,
student_id)`, `student_attendance(school_id, att_date)`,
`staff_attendance(school_id, att_date)`, `notices(school_id, notice_date)`,
`audit_log(school_id, created_at)`.

## Subscription Fields (on `schools`, not `users`)

```
subscription_plan       'monthly' | 'yearly' | NULL
subscription_status     'pending' | 'active' | 'expired' | 'suspended'
subscription_start      DATE
subscription_expiry     DATE
license_key_used        TEXT
```

See `docs/SAAS_ARCHITECTURE.md` "Conflict 1" for why this lives on the
school rather than the user.

## Nullable vs. Required Fields

Required (`NOT NULL`) fields follow the original app's form validation
exactly — e.g. `students.full_name`, `students.admission_no`,
`teachers.employee_code`. Everything optional in the original Streamlit
forms (guardian email, blood group, qualification, etc.) remains nullable.

## Timestamps

`schools.created_at` / `updated_at`, `users.created_at`, and
`audit_log.created_at` use `TIMESTAMP NOT NULL DEFAULT now()`. Date-only
business fields (`admission_date`, `payment_date`, `att_date`, etc.) use
`DATE DEFAULT CURRENT_DATE`, matching the original SQLite schema's
`date('now')` defaults.
