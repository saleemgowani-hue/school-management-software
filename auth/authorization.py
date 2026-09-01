"""
auth/authorization.py — Role-Based Access Control.

The six original roles and their permitted modules are copied verbatim from
the audited desktop app (see docs/CODE_AUDIT_REPORT.md Section 5) — nothing
was removed or narrowed. One new role, "Platform Admin", is added on top for
the SaaS operator to manage schools/subscriptions; it is a strictly additive
change and cannot be selected during school self-registration or staff
Sign Up (see SIGNUP_ROLES below), matching the original app's rule that
Sign Up can never grant the top administrative role.
"""

ROLES = ["Super Admin", "Principal", "Accountant", "Teacher", "Reception", "Librarian"]
PLATFORM_ROLE = "Platform Admin"
ALL_ROLES = ROLES + [PLATFORM_ROLE]

# Roles selectable via the public "Sign Up" / school-registration flow.
# Super Admin is granted automatically to the school's first account at
# registration time — never chosen from a dropdown by an anonymous visitor.
SIGNUP_ROLES = [r for r in ROLES if r != "Super Admin"]

SCHOOL_MODULES = [
    "Dashboard", "Students", "Classes", "Attendance", "Fees", "Exams",
    "Teachers", "Staff", "Library", "Transport", "Hostel", "Notice Board",
    "Certificates", "Reports", "Global Search", "Settings",
]

PLATFORM_MODULES = ["Platform Dashboard", "Manage Schools", "Manage Subscriptions", "Manage License Keys"]

ROLE_PERMISSIONS = {
    "Super Admin": "ALL",
    "Principal": [
        "Dashboard", "Students", "Classes", "Attendance", "Fees", "Exams",
        "Teachers", "Staff", "Library", "Transport", "Hostel", "Notice Board",
        "Certificates", "Reports", "Global Search", "Settings",
    ],
    "Accountant": ["Dashboard", "Fees", "Reports", "Global Search"],
    "Teacher": ["Dashboard", "Students", "Attendance", "Exams", "Notice Board", "Global Search"],
    "Reception": ["Dashboard", "Students", "Attendance", "Notice Board", "Certificates", "Global Search"],
    "Librarian": ["Dashboard", "Library", "Global Search"],
    "Platform Admin": PLATFORM_MODULES,
}


def has_access(role: str, module: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, [])
    return perms == "ALL" or module in perms


def is_platform_role(role: str) -> bool:
    return role == PLATFORM_ROLE


def modules_for_role(role: str) -> list:
    if is_platform_role(role):
        return PLATFORM_MODULES
    perms = ROLE_PERMISSIONS.get(role, [])
    return SCHOOL_MODULES if perms == "ALL" else perms
