# Code Audit Report — EduManage Pro (School Management Software)

**Audited files:** `app.py` (1,860 lines), `database.py` (643 lines)
**Audit method:** full read of both files; grep-verified inventory of every table, page function, and raw-SQL call site (counts below are exact, not estimated).

---

## 1. Existing Architecture

A single-tenant desktop application:

- **Frontend/UI:** Streamlit, one file (`app.py`), 16 page-render functions (`page_dashboard`, `page_students`, `page_classes`, `page_attendance`, `page_fees`, `page_exams`, `page_teachers`, `page_staff`, `page_library`, `page_transport`, `page_hostel`, `page_notices`, `page_certificates`, `page_reports`, `page_global_search`, `page_settings`), routed by a hand-rolled sidebar button menu (not Streamlit's native multipage folder).
- **Data layer:** `database.py` — thin SQLite wrapper (`get_conn`, `run`, `fetch_one`, `fetch_all`, `df`) that every page in `app.py` calls directly with **inline raw SQL strings**. There is no service/repository layer — **128 separate call sites** in `app.py` build and execute their own SQL.
- **Database:** SQLite file `school.db`, created and migrated in-place by `init_db()` (uses `ALTER TABLE ... ADD COLUMN` guarded by `PRAGMA table_info` checks for backward compatibility).
- **License/subscription:** Implemented **per user account**, not per installation and not per school — each row in `users` carries its own `license_activated`, `license_activation_date`, `license_expiry_date`, `license_plan`. This was a deliberate earlier design choice for a single-machine desktop tool where "one account = one school owner"; see Section 7 for why this must change for SaaS.
- **File/blob storage:** student photos and the school logo are stored as base64 text directly inside SQLite columns (`photo_blob`, `logo_blob`) — no filesystem or object-storage dependency.
- **Packaging:** ships as `app.py` + `database.py` + a generated `license_keys.txt`, run locally via `streamlit run app.py`, with `.bat`/`.sh` launchers. No `requirements.txt`, no `.gitignore`, no environment-variable/secrets handling — none of this existed because it was never meant to run on shared infrastructure.

## 2. Existing Modules (all confirmed present in `app.py`)

Dashboard · Student Management (admission/search/update/promotion/transfer certificate) · Class Management · Attendance (student/teacher/staff, monthly report) · Fees (structure/collection/dues/reports) · Exams (types/subjects/marks/report card) · Teacher Management · Staff Management · Library (books/issue/return) · Transport (vehicles/routes) · Hostel (rooms/allocation) · Notice Board · Certificates · Reports (7 report types, Excel export) · Global Search · Settings (school profile, appearance, backup/restore, user accounts, own-password change) · Auth (Sign In / Sign Up) · License/Subscription (monthly & yearly keys, no trial).

## 3. Existing Database Structure — 23 Tables

```
users, sessions_meta (legacy/unused), license_keys, settings, classes, students, teachers, staff,
staff_attendance, student_attendance, fee_structure, fee_payments, exam_types, exam_subjects,
marks, library_books, book_issues, transport_vehicles, transport_routes, hostel_rooms,
hostel_allocations, notices, certificates_log
```

None of these tables currently have a `school_id`/`tenant_id` column — **every one of them is a Phase-11 migration target.**

**Relationships (SQLite, enforced only loosely — `PRAGMA foreign_keys=ON` is set but SQLite FKs are advisory unless the column is declared correctly):** `classes.class_teacher_id → teachers.id`, `students.class_id → classes.id`, `students.route_id → transport_routes.id`, `fee_structure.class_id → classes.id`, `fee_payments.student_id → students.id`, `marks.{exam_id,student_id,subject_id}`, `book_issues.{book_id,student_id}`, `hostel_allocations.{room_id,student_id}`.

**Uniqueness constraints that are currently GLOBAL and must become PER-SCHOOL:** `users.username`, `students.admission_no`, `students.student_id`, `teachers.employee_code`, `staff.employee_code`, `library_books.book_code`, `transport_vehicles.vehicle_no`, `hostel_rooms.room_no`, `classes(class_name, section, academic_session)`, `exam_types.exam_name`, `fee_payments.receipt_no`.

## 4. Existing Authentication Flow

- `hash_pw()` uses **unsalted SHA-256** (`hashlib.sha256(...).hexdigest()`). This is adequate for a local single-user desktop tool but is a **security risk for an internet-facing SaaS app** — SHA-256 is fast to brute-force at scale and has no per-user salt. **Must be replaced with bcrypt** before deployment (Section 8).
- `authenticate(username, password)` — single global lookup, no tenant scoping (there is only one tenant today).
- `signup_user()` — public self-service signup, blocks the "Super Admin" role from being selected (prevents an anonymous visitor from granting themselves top-level access) but otherwise creates an active account immediately.
- `change_password()` — self-service, verifies current password, enforces 6-char minimum.
- Session state: `st.session_state.user` holds the full user row, re-fetched from the DB on every `main()` run to keep license/active-status current (already a good pattern — reused in the SaaS version).

## 5. Existing Roles & Permissions (`ROLE_PERMISSIONS`, `database.py`)

```
Super Admin → ALL modules
Principal   → Students, Classes, Attendance, Fees, Exams, Teachers, Staff, Library, Transport,
              Hostel, Notice Board, Certificates, Reports, Global Search, Settings
Accountant  → Dashboard, Fees, Reports, Global Search
Teacher     → Dashboard, Students, Attendance, Exams, Notice Board, Global Search
Reception   → Dashboard, Students, Attendance, Notice Board, Certificates, Global Search
Librarian   → Dashboard, Library, Global Search
```

This RBAC table is preserved **unchanged** in the SaaS version (Phase 6) — it correctly separates duties already. Only a new role, `Platform Admin`, is **added on top** (not replacing anything) to manage schools/subscriptions across the whole SaaS, since no such cross-school role existed or could have existed in a single-tenant app.

## 6. Existing License/Subscription Logic

- 50 monthly + 50 yearly keys, format `EDU-M-####-####-####-####` / `EDU-Y-...`, generated once and kept in sync with `license_keys.txt` on every `init_db()` call (`INSERT OR IGNORE`, so re-running never invalidates already-used keys).
- No free trial (already removed per a prior request) — every account must activate before use.
- **Conflict with SaaS requirements:** subscription is keyed to `users.id`. In a real multi-tenant SaaS, a school has 5–50 staff members; it would be wrong (and commercially nonsensical) for *each staff member* to need their own subscription key. **Resolution (Section 7): subscription moves to the `schools` table** — one active plan per school, shared by every user in that school. This is the single largest behavioural change in this conversion and is called out explicitly per your Phase 25 instruction to surface conflicts before implementing.

## 7. Existing School-Related Data

None — the desktop app has no concept of "a school" as a row; the single `settings` table (id fixed at 1) *is* the one school's profile. In the SaaS schema this becomes one row per tenant in a new `schools` table (Section on schema below), and every other table gains a `school_id` foreign key.

## 8. Security Risks Identified (feeds Phase 13)

| Risk | Where | Severity | Fix |
|---|---|---|---|
| Unsalted SHA-256 passwords | `hash_pw()` | High (once internet-facing) | Migrate to bcrypt with per-password salt |
| No tenant scoping on any table/query | all 128 SQL call sites | Critical for SaaS | `school_id` column + enforced filtering in a service layer, never trusted from the browser |
| Global uniqueness assumptions | usernames, admission numbers, etc. | Medium | Move uniqueness constraints to `(school_id, field)` composite |
| No secrets management | none existed | High for cloud deploy | `st.secrets` / environment variables, `.gitignore` |
| SQLite `?` placeholders throughout | `database.py` | Low (already parameterized, no string concatenation found — good) | Convert placeholder style to psycopg2 `%s`, keep parameterization discipline |
| No audit trail | none existed | Medium | New `audit_log` table (Phase 20) |

**Positive finding:** every existing query already uses parameterized placeholders (`?`) — there is **no SQL-injection-by-concatenation** anywhere in the current code. This significantly de-risks the migration; the Postgres layer only needs to keep using parameters (`%s`), not retrofit safety that was missing.

## 9. Files That Need Modification

- `database.py` → fully replaced by a PostgreSQL, tenant-aware data layer (`database/`, `services/`).
- `app.py` → **UI/forms/layout preserved**; every raw-SQL call site is rewired to call the new tenant-scoped service functions instead. Net effect: same screens, same buttons, same workflow — different data layer underneath.
- License/key logic → moves from `users` to `schools`.

## 10. Files That Remain Conceptually Unchanged

- All CSS (`inject_css()`), the multicolour sidebar button styling, KPI cards, forms, and page layouts — copied forward as-is into the new `app.py`, since Phase 10/24 require preserving the UI.
- The 6 original roles and their permission sets.
- The monthly/yearly (no-trial) subscription *concept* — only its owner (school vs. user) changes.
- The Excel/receipt/certificate HTML export helpers.

## 11. Recommended New Files (delivered)

`database/connection.py`, `database/schema.sql`, `database/migrate_from_sqlite.py`, `auth/authentication.py`, `auth/authorization.py`, `services/*.py` (grouped by domain — see `docs/SAAS_ARCHITECTURE.md` for why they're grouped rather than one-file-per-table), `utils/security.py`, `utils/validators.py`, `utils/helpers.py`, `tests/test_tenant_isolation.py`, `requirements.txt`, `.gitignore`, `README.md`, plus this `docs/` folder.

## 12. Dependency Changes

| Removed | Added | Why |
|---|---|---|
| (implicit) `sqlite3` | `psycopg2-binary` | PostgreSQL driver |
| `hashlib` (for passwords) | `bcrypt` | Adaptive, salted password hashing |
| — | `python-dotenv` (local dev only) | Load `DATABASE_URL` from `.env` outside Streamlit Cloud |

`pandas`, `plotly`, `openpyxl`, `streamlit` are unchanged — the reporting/UI stack did not need to change.

---

**Conclusion:** the application is well-structured for a single-tenant tool (consistent parameterized queries, a real RBAC table, a working subscription concept) but has **zero tenant isolation** by construction — there was never a second tenant to isolate from. The conversion work is concentrated in two places: (1) adding `school_id` everywhere and enforcing it server-side, and (2) moving subscription ownership from the user to the school. Everything else — UI, roles, modules, workflows — carries forward with minimal change, per your instruction to avoid unnecessary rewrites.
