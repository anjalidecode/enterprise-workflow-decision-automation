"""Authentication and RBAC (Module 5B). Development user store + JWT."""

from app.auth.dependencies import (
    CurrentUser,
    get_current_user,
    require_admin,
    require_employee,
    require_hr,
    require_manager,
    require_roles,
)
from app.auth.models import Role, User

__all__ = [
    "CurrentUser",
    "Role",
    "User",
    "get_current_user",
    "require_admin",
    "require_employee",
    "require_hr",
    "require_manager",
    "require_roles",
]
