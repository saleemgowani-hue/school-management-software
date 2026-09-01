"""
utils/security.py — password hashing and license-key generation.

Passwords use bcrypt (adaptive, automatically salted per-password) instead
of the original desktop app's unsalted SHA-256 — see docs/CODE_AUDIT_REPORT.md
Section 8 for why this changed for an internet-facing SaaS deployment.
"""

import secrets
import string

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Handles a stored hash that isn't a valid bcrypt hash (e.g. a row
        # migrated from the old SHA-256 scheme that hasn't been reset yet).
        return False


def generate_license_keys(n: int, prefix: str = "EDU") -> list:
    alphabet = string.ascii_uppercase + string.digits
    keys = set()
    while len(keys) < n:
        parts = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
        keys.add(f"{prefix}-" + "-".join(parts))
    return sorted(keys)


def generate_school_code(school_name: str) -> str:
    """Best-effort short code suggestion for a new school, e.g. 'Green Valley
    Public School' -> 'GVPS'. Uniqueness is enforced by the DB constraint and
    a numeric suffix is added by the caller on collision, not here."""
    words = [w for w in school_name.upper().split() if w.isalpha()]
    code = "".join(w[0] for w in words) or "SCH"
    return code[:8]
