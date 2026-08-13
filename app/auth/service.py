"""Authentication service — login and token issuance against PostgreSQL."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.auth.models import User
from app.auth.schemas import TokenResponse, UserPublic
from app.auth.security import create_access_token, verify_password
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.repositories.user import UserRepository
from app.database.session import session_scope


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
    session: Session | None = None,
) -> User:
    """Validate credentials against PostgreSQL. Never reveal which field failed."""

    def _authenticate(db: Session) -> User:
        repo = UserRepository(db)
        user = repo.get_auth_user_by_username(username)
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

    try:
        if session is not None:
            return _authenticate(session)
        with session_scope() as db:
            return _authenticate(db)
    except APIError:
        raise
    except DatabaseNotConfiguredError as exc:
        raise APIError(
            status_code=503,
            code="DATABASE_NOT_CONFIGURED",
            message=str(exc),
        ) from exc
    except DatabaseUnavailableError as exc:
        raise APIError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message=str(exc),
        ) from exc


def login(
    username: str,
    password: str,
    *,
    session: Session | None = None,
) -> TokenResponse:
    user = authenticate_user(username, password, session=session)
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
