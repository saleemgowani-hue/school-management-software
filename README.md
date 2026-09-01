# EduManage Pro — Multi-School SaaS Edition

A multi-tenant School Management SaaS, converted from an existing single-school
Streamlit/SQLite desktop application into a PostgreSQL-backed platform where
many schools share one deployment with **completely isolated data**.

See `docs/CODE_AUDIT_REPORT.md` for what the original app looked like and
`docs/SAAS_ARCHITECTURE.md` for every design decision and conflict this
conversion required.

## Architecture

```
app.py                     Streamlit UI — every page, no raw SQL
config.py                  Reads DATABASE_URL / secrets, app-wide constants

database/
  connection.py             The ONLY module that talks to psycopg2/SQLAlchemy
  schema.sql                Full PostgreSQL DDL (23 tables, all tenant-scoped)
  migrate_from_sqlite.py    One-time importer for an existing desktop school.db
  create_platform_admin.py  CLI bootstrap for the first Platform Admin

auth/
  authentication.py         Login, self-signup, password change (bcrypt)
  authorization.py          RBAC — the original 6 roles + Platform Admin

services/                   One school_id-scoped function per operation,
  school_service.py         grouped by domain (see SAAS_ARCHITECTURE.md for why)
  academic_service.py
  finance_service.py
  hr_service.py
  facilities_service.py
  communication_service.py
  report_service.py
  audit_service.py

utils/
  security.py                bcrypt hashing, license-key generation
  helpers.py                 Excel export, certificate/receipt HTML builders

tests/
  test_tenant_isolation.py   Automated proof that School A never sees School B
```

## Tenant Isolation Model

Every school-owned table has a `school_id` column. Every service function
takes `school_id` as its first argument and bakes it into the SQL text of
every query — never appended conditionally, never trusted from the browser.
`school_id` is set exactly once, in `app.py`, from the authenticated user's
own row (`st.session_state.user["school_id"]`), immediately after login.

This is proven, not just claimed — see `docs/TESTING_REPORT.md` for the
actual output of a 16-check automated test run against a real PostgreSQL
instance, covering students, classes, attendance, fees, exams/marks, and
subscriptions across two independently-created schools.

## Local Setup

1. Install PostgreSQL and create a database:
   ```bash
   createdb school_saas
   ```
2. Apply the schema:
   ```bash
   psql -d school_saas -f database/schema.sql
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure credentials — create `.streamlit/secrets.toml` (never commit this
   file; it's in `.gitignore`):
   ```toml
   PGHOST = "localhost"
   PGPORT = "5432"
   PGDATABASE = "school_saas"
   PGUSER = "postgres"
   PGPASSWORD = "your-local-password"
   ```
5. Run:
   ```bash
   streamlit run app.py
   ```
   On first run, the app auto-syncs 50 monthly + 50 yearly license keys into
   `license_keys.txt` and seeds a working **Demo school** (username `demo`,
   password `demo1234`) so there's something to explore immediately.
6. Create the first Platform Admin (only needed once per deployment):
   ```bash
   python -m database.create_platform_admin
   ```

## Migrating an Existing Desktop Installation

If you have an existing single-school `school.db` from the desktop version:

```bash
python -m database.migrate_from_sqlite /path/to/school.db "Your School Name"
```

The original file is opened **read-only** and is never modified — see the
script's docstring and `docs/TESTING_REPORT.md` for a worked example. Every
migrated user gets a temporary password (`ChangeMe123!`) since the old
SHA-256 hashes can't be converted to bcrypt — they must reset it via
Settings > My Account on first login. The migrated school starts in
`pending` subscription status (no trial) and needs a key activated before
staff can use it.

## Deployment (GitHub → Streamlit Cloud → PostgreSQL)

See `docs/DEPLOYMENT_GUIDE.md` for the complete step-by-step walkthrough,
including exactly what to put in Streamlit Cloud's Secrets panel and what
must never be committed to GitHub.

## Demo Account

Username `demo` / password `demo1234` — a fully seeded sample school anyone
can explore. Password changes, settings changes, subscription changes, and
account deletion are all blocked for this account (see `is_demo` checks
throughout `services/school_service.py` and `auth/authentication.py`).

## Subscriptions

No free trial. Every school must activate a Monthly (30-day) or Yearly
(365-day) key before use — belongs to the **school**, not an individual
user, so every staff member shares their school's subscription. See
"Conflict 1" in `docs/SAAS_ARCHITECTURE.md` for why this differs from the
original desktop app.

## Further Reading

- `docs/CODE_AUDIT_REPORT.md` — what was inspected and found in the original app
- `docs/SAAS_ARCHITECTURE.md` — every conflict and its resolution
- `docs/SECURITY_REPORT.md` — what protections are implemented and why
- `docs/DEPLOYMENT_GUIDE.md` — GitHub + Streamlit Cloud + Postgres, step by step
- `docs/DATABASE_DOCUMENTATION.md` — every table, relationship, and index
- `docs/TESTING_REPORT.md` — actual test runs and their real output
