"""Authentication service — login and token issuance."""

from __future__ import annotations

from app.auth.models import User
from app.auth.schemas import TokenResponse, UserPublic
from app.auth.security import create_access_token, verify_password
from app.auth.store import UserStore, get_user_store
from app.api.errors import APIError


def to_public_user(user: User) -> UserPublic:
    return UserPublic(
        user_id=user.user_id,
        username=user.username,
        organization_id=user.organization_id,
        role=user.role,
        employee_id=user.employee_id,
    )


def authenticate_user(
    username: str,
    password: str,
    *,
    store: UserStore | None = None,
) -> User:
    """Validate credentials. Never reveal whether username or password failed."""

    user_store = store or get_user_store()
    user = user_store.get_by_username(username)
    if user is None or not verify_password(password, user.password_hash):
        raise APIError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid username or password.",
        )
    if not user.is_active:
        raise APIError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="User account is inactive.",
        )
    return user


def login(
    username: str,
    password: str,
    *,
    store: UserStore | None = None,
) -> TokenResponse:
    user = authenticate_user(username, password, store=store)
    token, expires_in = create_access_token(
        user_id=user.user_id,
        organization_id=user.organization_id,
        role=user.role.value,
        employee_id=user.employee_id,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=to_public_user(user),
    )
