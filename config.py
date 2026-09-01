"""
config.py — central place that resolves configuration for every environment
this app runs in, in priority order:

    1. Streamlit Cloud "Secrets" (st.secrets)   — production
    2. Environment variables                     — Docker / servers / CI
    3. A local .env file (python-dotenv)          — local development only

No credential is ever hard-coded here or anywhere else in the codebase.
"""

import os

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

try:
    from dotenv import load_dotenv
    load_dotenv()  # no-op if no .env file exists — safe to always call
except ImportError:
    pass


def _get(key: str, default=None):
    """Resolve a config key from st.secrets first, then the environment."""
    if _HAS_STREAMLIT:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass  # st.secrets raises if no secrets.toml exists at all — fine locally
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Preferred: a single DATABASE_URL, e.g.
#   postgresql://user:password@host:5432/dbname
# Falls back to individual PG* parts if DATABASE_URL isn't set.
DATABASE_URL = _get("DATABASE_URL")

PGHOST = _get("PGHOST", "localhost")
PGPORT = _get("PGPORT", "5432")
PGDATABASE = _get("PGDATABASE", "school_saas")
PGUSER = _get("PGUSER", "postgres")
PGPASSWORD = _get("PGPASSWORD", "")

# ---------------------------------------------------------------------------
# App-level settings
# ---------------------------------------------------------------------------
APP_NAME = "EduManage Pro"
SECRET_KEY = _get("SECRET_KEY", "change-me-in-production")  # reserved for future signed tokens

TRIAL_DAYS = 0  # no free trial, per requirement
MONTHLY_VALIDITY_DAYS = 30
YEARLY_VALIDITY_DAYS = 365
TOTAL_MONTHLY_KEYS = 50
TOTAL_YEARLY_KEYS = 50
PLAN_VALIDITY_DAYS = {"monthly": MONTHLY_VALIDITY_DAYS, "yearly": YEARLY_VALIDITY_DAYS}

DEMO_SCHOOL_CODE = "DEMO"
