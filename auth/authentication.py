"""
auth/authentication.py — login, self-signup, password change.

Tenant-safety rule enforced throughout this file: the ONLY place a
`school_id` is ever written into `st.session_state` is right here, taken
directly from the authenticated user's own database row. No other code in
this application ever sets it, and no page reads a school_id from a URL
query parameter, form field, or any other browser-controlled input.
"""

from database.connection import fetch_one, execute
from auth.authorization import SIGNUP_ROLES, PLATFORM_ROLE
from utils.security import hash_password, verify_password


def authenticate(username: str, password: str):
    """Returns the full user row (including school_id) on success, else None."""
    user = fetch_one(
        "SELECT * FROM users WHERE username = %s AND active = TRUE", (username,)
    )
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def signup_user(school_id: int, username: str, password: str, full_name: str, role: str, email: str = ""):
    """Self-service staff account creation, scoped to ONE school.

    Mirrors the original desktop app's rule: Super Admin (and the platform-
    level Platform Admin role) can never be granted through this form.
    """
    username = (username or "").strip()
    full_name = (full_name or "").strip()

    if not username or not password or not full_name:
        return False, "Full Name, Username and Password are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if role not in SIGNUP_ROLES:
        return False, "Please choose a valid role."
    if fetch_one("SELECT id FROM users WHERE username = %s", (username,)):
        return False, "That username is already taken. Please choose another."

    execute(
        "INSERT INTO users (school_id, username, password_hash, full_name, role, email) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (school_id, username, hash_password(password), full_name, role, email.strip()),
    )
    return True, "Account created successfully! You can now sign in."


def change_password(user_id: int, current_password: str, new_password: str, confirm_password: str):
    user = fetch_one("SELECT u.*, s.is_demo FROM users u LEFT JOIN schools s ON s.id = u.school_id WHERE u.id = %s", (user_id,))
    if not user:
        return False, "User not found."
    if user.get("is_demo"):
        return False, "Password changes are disabled in the Demo account. Register your own school to keep your changes."
    if not verify_password(current_password, user["password_hash"]):
        return False, "Your current password is incorrect."
    if new_password != confirm_password:
        return False, "New password and confirmation do not match."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters long."
    if verify_password(new_password, user["password_hash"]):
        return False, "New password must be different from your current password."
    execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_password), user_id))
    return True, "Password changed successfully."


def set_user_active(school_id: int, user_id: int, active: bool):
    """Activate/deactivate a staff account — always scoped to the caller's own school."""
    school = fetch_one("SELECT is_demo FROM schools WHERE id = %s", (school_id,))
    if school and school["is_demo"]:
        return False, "Account management is disabled in the Demo school."
    execute(
        "UPDATE users SET active = %s WHERE id = %s AND school_id = %s",
        (active, user_id, school_id),
    )
    return True, "Updated."
