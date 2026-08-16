"""FastAPI auth dependencies: current user and role gates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import Role, User
from app.auth.permissions import auth_required_error, forbidden_error
from app.auth.security import decode_access_token
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.repositories.user import UserRepository
from app.database.session import session_scope

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise auth_required_error()
    token = (credentials.credentials or "").strip()
    if not token:
        raise auth_required_error()

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise auth_required_error("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise auth_required_error("Invalid or malformed access token.") from exc

    user_id = str(payload.get("sub") or "").strip()
    organization_id = str(payload.get("organization_id") or "").strip()
    role_value = str(payload.get("role") or "").strip().lower()
    if not user_id or not organization_id or not role_value:
        raise auth_required_error("Access token is missing required claims.")

    try:
        with session_scope() as session:
            user = UserRepository(session).get_auth_user_by_id(user_id)
    except DatabaseNotConfiguredError as exc:
        raise auth_required_error(str(exc)) from exc
    except DatabaseUnavailableError as exc:
        raise auth_required_error(str(exc)) from exc

    if user is None or not user.is_active or user.status.value != "active":
        raise auth_required_error("User account is inactive or unknown.")

    # Token claims must match the stored user (prevents stale/tampered role/org).
    if user.organization_id != organization_id or user.role.value != role_value:
        raise auth_required_error("Access token claims do not match the user record.")
    token_employee = str(payload.get("employee_id") or "").strip()
    stored_employee = (user.employee_id or "").strip()
    if token_employee != stored_employee:
        raise auth_required_error("Access token claims do not match the user record.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise forbidden_error(
                f"Requires one of roles: {', '.join(sorted(r.value for r in allowed))}."
            )
        return user

    return dependency


require_employee = require_roles(Role.EMPLOYEE)
require_manager = require_roles(Role.MANAGER)
require_hr = require_roles(Role.HR)
require_admin = require_roles(Role.ADMIN)

# Convenience composite for staff who may approve in development RBAC.
require_approver = require_roles(Role.MANAGER, Role.HR, Role.ADMIN)
