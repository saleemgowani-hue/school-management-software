# Deployment Guide — GitHub → Streamlit Cloud → PostgreSQL

## 1. Get a PostgreSQL Database

Any managed PostgreSQL works (Streamlit Cloud does not host a database
itself). Popular free/cheap options: Supabase, Neon, Railway, Render. You
need the connection string, which looks like:

```
postgresql://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME
```

Note it down — you'll paste it into Streamlit Cloud's Secrets in step 4,
**never** into any file that goes to GitHub.

## 2. Apply the Schema

From your own machine, with `psql` installed:

```bash
psql "postgresql://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME" -f database/schema.sql
```

This creates all 23 tables and their indexes. It's safe to re-run — every
statement is `CREATE ... IF NOT EXISTS`.

## 3. Push to GitHub

```bash
git init
git add .
git commit -m "Initial multi-tenant SaaS conversion"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/school-management-saas.git
git push -u origin main
```

Double-check `.gitignore` is doing its job before pushing:

```bash
git status --ignored
```

You should see `.streamlit/secrets.toml`, `.env`, `*.db`, and
`license_keys.txt` listed under "Ignored files" — if any of them show up
under "Changes to be committed" instead, **stop and fix `.gitignore` before
pushing.**

## 4. Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
2. Click "New app", pick your repository, branch `main`, main file `app.py`.
3. Before clicking Deploy, open **Advanced settings > Secrets** and paste:

   ```toml
   DATABASE_URL = "postgresql://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME"
   SECRET_KEY = "generate-a-random-string-here"
   ```

   (You can use either `DATABASE_URL` on its own, or the individual
   `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` keys shown in
   `README.md` — `config.py` checks `DATABASE_URL` first.)

4. Click Deploy. First boot will take a minute while dependencies install.

## 5. First-Run Checklist

Once the app is live:

1. It automatically syncs the 50 monthly + 50 yearly license keys and seeds
   the Demo school — confirm by logging in as `demo` / `demo1234`.
2. Register your first real school via the "Register School" tab.
3. From your own machine (with the same `DATABASE_URL` set as an
   environment variable), create the Platform Admin:
   ```bash
   DATABASE_URL="postgresql://..." python -m database.create_platform_admin
   ```
   This is deliberately a command-line step, not a button in the app — see
   `docs/SECURITY_REPORT.md` Section 4.
4. Activate your first real school's subscription using a key from
   `license_keys.txt` (generated locally the first time you ran the app —
   see step 6).

## 6. Where Do the License Keys Come From?

The first time the app starts against a fresh database, it generates 50
monthly + 50 yearly keys and writes them to `license_keys.txt` **on the
server it's running on**. On Streamlit Cloud, that file lives in the app's
ephemeral filesystem — download it via Streamlit Cloud's file browser
before the app restarts, or regenerate a copy locally by pointing your own
machine's `DATABASE_URL` at the same database and running:

```python
from services.school_service import sync_license_keys
sync_license_keys()
```

This reads/writes `license_keys.txt` in your current directory and is
always safe to re-run (existing used keys are never invalidated).

## 7. Updating the Live App

Push to `main` — Streamlit Cloud redeploys automatically. Database schema
changes should be applied manually first (`psql -f database/schema.sql`
picks up any new `CREATE TABLE IF NOT EXISTS` statements without touching
existing data).

## 8. Rolling Back

Streamlit Cloud keeps deploy history — use "Reboot app" pointed at a
previous commit if a deploy causes problems. Database changes are not
automatically rolled back by this; see `docs/SECURITY_REPORT.md` and the
audit's Phase 22 guidance: back up before any schema change you're unsure
about (`pg_dump` your database periodically).
