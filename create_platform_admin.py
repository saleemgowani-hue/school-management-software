"""
database/create_platform_admin.py

Bootstraps the very first Platform Admin account. Deliberately a command-
line script, not a UI screen or public form — the Platform Admin role can
see every school's subscription status and suspend/reactivate accounts, so
it must never be reachable through Sign Up or Register School (see
auth/authorization.py: PLATFORM_ROLE is not in SIGNUP_ROLES).

Run ONCE, right after deploying, from a trusted machine / Streamlit Cloud
shell with the same DATABASE_URL / secrets configured:

    python -m database.create_platform_admin
"""

import getpass
import sys

sys.path.insert(0, ".")

from database.connection import fetch_one, execute
from utils.security import hash_password


def main():
    print("=== EduManage Pro — Create Platform Admin ===")
    existing = fetch_one("SELECT COUNT(*) c FROM users WHERE role = 'Platform Admin'")
    if existing and existing["c"] > 0:
        print(f"There are already {existing['c']} Platform Admin account(s). "
              "Continuing will add ANOTHER one.")
        if input("Continue anyway? [y/N]: ").strip().lower() != "y":
            print("Cancelled.")
            return

    username = input("Choose a username: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Choose a password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")

    if not username or not full_name:
        print("Username and full name are required. Aborted.")
        return
    if password != confirm:
        print("Passwords do not match. Aborted.")
        return
    if len(password) < 8:
        print("Password must be at least 8 characters for a Platform Admin account. Aborted.")
        return
    if fetch_one("SELECT id FROM users WHERE username = %s", (username,)):
        print("That username is already taken. Aborted.")
        return

    execute(
        "INSERT INTO users (school_id, username, password_hash, full_name, role) "
        "VALUES (NULL, %s, %s, %s, 'Platform Admin')",
        (username, hash_password(password), full_name),
    )
    print(f"\nPlatform Admin '{username}' created successfully. You can now sign in at the app's login screen.")


if __name__ == "__main__":
    main()
