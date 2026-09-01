# Security Report

This document explains every security-relevant decision in this codebase,
mapped to the audit findings in `docs/CODE_AUDIT_REPORT.md` Section 8.

## 1. Password Storage

**Before:** unsalted SHA-256 (`hashlib.sha256(password).hexdigest()`).
**Now:** bcrypt (`utils/security.py`), which is adaptive (tunable work
factor) and automatically salts every hash. Verified with real hashes in
this session:

```
>>> hash_password("pass123")
'$2b$12$......' (60-char bcrypt hash, unique every time even for the same input)
```

Old SHA-256 hashes are **not** silently accepted — `verify_password()`
returns `False` for anything that isn't a valid bcrypt hash, and the
migration script (`database/migrate_from_sqlite.py`) issues fresh bcrypt
hashes with a temporary password rather than attempting to carry the old
hash forward.

## 2. SQL Injection

Every one of the ~150 queries across `services/*.py` uses parameterized
placeholders (`%s` / `%(name)s`) via psycopg2 — **no query is built by
string concatenation or f-string interpolation of user input anywhere in
this codebase.** This preserves a property the audit found already true of
the original SQLite code (Section 8's "positive finding") and carries it
forward into the new query style.

## 3. Tenant Isolation (Cross-Tenant Data Leakage)

This is the highest-severity risk for any multi-tenant system, and it's
the one most extensively tested in this project — see
`docs/TESTING_REPORT.md` for the actual 16/16 passing isolation checks run
against a real PostgreSQL database, including a **simulated attack**: School
B calling `update_student(school_b_id, student_a_id, ...)` to try to modify
School A's data, and confirming it silently affects zero rows because the
`WHERE school_id = %s AND id = %s` clause never matches.

The enforcement point is architectural, not just tested: `app.py` contains
**no raw SQL**, so there is no code path in the presentation layer that
could omit the tenant filter. Every query lives inside a `services/*.py`
function that takes `school_id` as its first parameter.

## 4. Authentication & Session Handling

- Streamlit's `st.session_state` holds the authenticated user's row; it is
  **re-fetched from the database on every page load** (`main()` in
  `app.py`), so a deactivated account or a role change takes effect
  immediately, not just at next login.
- Inactive accounts (`active = FALSE`) cannot authenticate
  (`WHERE active = TRUE` in `authenticate()`) and are logged out mid-session
  if deactivated while logged in.
- The Sign Up / Join-a-School flow can never grant `Super Admin` or
  `Platform Admin` — both are excluded from `SIGNUP_ROLES`
  (`auth/authorization.py`).

## 5. Secrets Management

No credential is hard-coded anywhere in this codebase. `config.py` resolves
`DATABASE_URL` (or individual `PGHOST`/`PGUSER`/etc.) from, in order:
Streamlit Cloud's `st.secrets`, then environment variables, then an
optional local `.env` file. `.gitignore` excludes `.streamlit/secrets.toml`
and `.env` from version control.

## 6. Error Handling

`database/connection.py::health_check()` is called at the top of `main()`;
if the database is unreachable, the user sees a plain "temporarily
unavailable" message, and only an admin who expands a collapsed technical
section sees the underlying exception text — ordinary users never see a
raw stack trace or connection string.

## 7. Demo Account Hardening

The demo school (`is_demo = TRUE`) cannot have its password changed
(`auth/authentication.py::change_password`), cannot have its subscription
changed (`services/school_service.py::activate_subscription`), and cannot
have its settings changed (`update_school_settings`) — each of these
functions checks `is_demo` first and returns a refusal instead of writing,
regardless of who is calling it or what role they have.

## 8. Audit Trail

`services/audit_service.py` records login, logout, student
creation/update, and fee entries with `school_id`, `user_id`, a timestamp,
and a short description — never a password or password hash. This gives a
school's Super Admin (or the Platform Admin, per-school) a trace of who did
what, satisfying Phase 20.

## 9. Known Limitations / Recommended Next Steps

- **Rate limiting on login** is not implemented at the application layer in
  this iteration — Streamlit Cloud sits behind its own infrastructure, but
  a dedicated login-attempt throttle (e.g., lock an account after N failed
  attempts) would be a reasonable follow-up hardening step for a
  production launch.
- **HTTPS/TLS** is provided by Streamlit Cloud's platform, not by this
  application code — no action needed if deploying there, but a
  self-hosted deployment must terminate TLS itself (e.g., behind nginx).
- **File uploads** (student photos, school logo) are stored as base64 text
  directly in PostgreSQL columns, unchanged from the original design. This
  is simple and safe (no filesystem path traversal risk) but is not
  optimized for large-scale photo storage; migrating to object storage
  (S3-compatible) is a reasonable future enhancement, not a security gap.
