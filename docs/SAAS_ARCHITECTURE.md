# SaaS Architecture & Conflict Resolutions

This document exists because Phase 25 of the brief requires conflicts between the existing
software and the SaaS requirements to be **surfaced and resolved explicitly, before
implementation** — not silently designed around.

## Conflict 1 — Subscription belongs to a user, not a school

**Existing behaviour:** each row in `users` carries its own trial/license/expiry. This was
correct for a desktop tool where "one login = one installation."

**Why it breaks in SaaS:** a school has many staff logins (Principal, Accountant, several
Teachers, Reception, Librarian). If subscription stayed per-user, a school would need to buy
one key per staff member, and a Teacher's personal key expiring would have nothing to do with
whether the school's software access should continue. That is not how school software is sold
or reasoned about.

**Resolution:** subscription fields move to the new `schools` table — `subscription_plan`,
`subscription_status`, `subscription_start`, `subscription_expiry`, `license_key_used`. Every
user's access is gated by **their school's** subscription status, checked on every request via
`get_school_subscription_status(school_id)`. License keys remain a shared platform-wide pool
(50 monthly + 50 yearly, unchanged format) but `activate_subscription()` now takes a
`school_id`, and a used key is tied to `used_by_school_id`, not a user id.

## Conflict 2 — Username uniqueness (global vs. per-school)

**Existing behaviour:** `users.username` is globally unique.

**Option A** — scope usernames per school (`UNIQUE(school_id, username)`), which would let
"admin" exist once per school, but requires the login screen to ask **which school** before
username/password (a new UI element, breaking Phase 10's "preserve existing workflow").

**Resolution chosen:** keep `username` **globally unique across the whole platform**. The
existing single username/password login screen is preserved exactly as-is — no school
selector is added. The tradeoff (two different schools can't both have a user literally named
`admin`) is minor and is mitigated by suggesting `schoolcode_admin`-style usernames during
onboarding; it is not enforced, so it never blocks anyone.

## Conflict 3 — Per-school data uniqueness (admission numbers, employee codes, etc.)

**Existing behaviour:** `students.admission_no`, `teachers.employee_code`,
`library_books.book_code`, etc. are globally unique.

**Resolution:** these move to **composite uniqueness**: `UNIQUE(school_id, admission_no)`,
`UNIQUE(school_id, employee_code)`, and so on. Two different schools can both have admission
number `ADM20260001`; the same school cannot issue it twice. This is the standard multi-tenant
pattern and requires no UI change — auto-generated codes (`next_admission_no()` etc.) simply
count rows **within that school** instead of globally.

## Conflict 4 — SQLite `?` placeholders vs. PostgreSQL `%s`

Mechanical, not a design conflict: every one of the 128 existing call sites already used
parameterized placeholders (no string-built SQL was found in the audit), so the migration is a
straight placeholder-syntax swap behind a service layer — the safety property (no SQL
injection) is preserved, not newly introduced.

## Conflict 5 — Demo account vs. real accounts sharing one codebase

**Requirement:** a demo school must behave like a real school (so it's a genuine product
demo) but must reject password changes, data deletion, settings changes, and subscription
changes.

**Resolution:** the demo school is a completely normal row in `schools` with `is_demo = TRUE`.
Every service function that performs a **destructive or account-altering** write
(`change_password`, `set_user_active`, `update_school_settings`, `activate_subscription`,
student/teacher/staff/record deletion) checks `is_demo` first and returns a friendly refusal
instead of writing. Read and ordinary create/update operations for day-to-day modules
(admission, attendance, fees, exams, etc.) work normally so the demo is actually useful to
explore — it only blocks the handful of actions that would let a visitor damage the demo or
pretend to be a paying customer.

## Multi-Tenant Isolation Model

- **Tenant identifier:** `school_id INTEGER REFERENCES schools(id)` on every school-owned
  table.
- **Enforcement point:** the **service layer**, not the UI. Every service function's first
  parameter is `school_id`, sourced *only* from `st.session_state.user["school_id"]` (set once
  at login from the authenticated user's own database row) — it is never read from a URL
  parameter, form field, or any other browser-controlled input. `app.py` never issues raw SQL;
  it only calls service functions, so there is no code path in the UI layer that could omit
  the tenant filter.
- **Platform Admin exception:** the one role permitted to see cross-school data
  (`Platform Admin`, `school_id IS NULL`) uses a **separate, clearly-named set of functions**
  (`platform_list_schools()`, `platform_get_school_metrics()`) that are never reachable from
  any school-scoped page, so a bug in a school page cannot accidentally expose the platform
  view, and vice versa.

## Why services are grouped by domain, not one file per table

The brief's suggested structure lists one service file per module
(`student_service.py`, `fee_service.py`, ...). After inspecting the existing `app.py`, several
modules are small and tightly coupled in the UI (e.g. Transport/Hostel each have 2 tables and
~60 lines of page code; Notices/Certificates are single-table, <40 lines each). Splitting every
one into its own file would produce a dozen near-empty files. Per Phase 3 ("adapt the
architecture rather than blindly restructuring"), services are grouped by domain:

- `services/school_service.py` — schools, subscriptions, license keys, demo seeding, users/RBAC
- `services/academic_service.py` — classes, students, attendance, exams/marks
- `services/finance_service.py` — fee structure & collection
- `services/hr_service.py` — teachers, staff
- `services/facilities_service.py` — library, transport, hostel
- `services/communication_service.py` — notices, certificates
- `services/report_service.py` — cross-module reports/exports
- `services/audit_service.py` — audit log writes/reads

Each file still has one function per operation (`list_students`, `add_student`,
`update_attendance`, ...), so the granularity the brief wants is preserved — only the file
boundary is grouped sensibly.
