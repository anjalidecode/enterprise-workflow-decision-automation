"""Authentication service — login, registration, and token issuance against PostgreSQL."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.auth.models import Role, User
from app.auth.schemas import RegisterResponse, TokenResponse, UserPublic
from app.auth.security import create_access_token, hash_password, verify_password
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.user import UserRepository, to_auth_user
from app.database.session import session_scope

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORG_SLUG_RE = re.compile(r"[^a-z0-9]+")


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


def _organization_slug(name: str) -> str:
    slug = _ORG_SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:80] or "org"


def _validate_registration(
    *,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    organization_name: str,
) -> tuple[str, str]:
    if len(full_name.strip()) < 2:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Full name is required.",
        )
    email_key = email.strip().lower()
    if not _EMAIL_RE.match(email_key):
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Enter a valid work email address.",
        )
    org_name = organization_name.strip()
    if len(org_name) < 2:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Organization name is required.",
        )
    if password != confirm_password:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Password and confirmation do not match.",
        )
    if len(password) < 10:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Password must be at least 10 characters.",
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Password must include at least one letter and one number.",
        )
    return email_key, org_name


def register(
    *,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    organization_name: str,
    session: Session | None = None,
) -> RegisterResponse:
    """Create a PostgreSQL user. Never trusts client-supplied role or org IDs."""

    email_key, org_name = _validate_registration(
        full_name=full_name,
        email=email,
        password=password,
        confirm_password=confirm_password,
        organization_name=organization_name,
    )

    def _register(db: Session) -> User:
        users = UserRepository(db)
        orgs = OrganizationRepository(db)
        if users.get_by_username(email_key) is not None:
            raise APIError(
                status_code=409,
                code="ACCOUNT_EXISTS",
                message="An account with this email already exists.",
            )

        slug = _organization_slug(org_name)
        existing = orgs.get_by_name(org_name) or orgs.get_by_organization_id(slug)
        created_org = False
        if existing is None:
            organization_id = slug
            if orgs.get_by_organization_id(organization_id) is not None:
                organization_id = f"{slug}-{uuid.uuid4().hex[:6]}"
            existing = orgs.create(
                organization_id=organization_id,
                name=org_name,
                is_active=True,
            )
            created_org = True

        role = Role.ADMIN if created_org else Role.EMPLOYEE
        try:
            record = users.create(
                user_id=f"user-{uuid.uuid4().hex[:12]}",
                organization_id=existing.organization_id,
                username=email_key,
                password_hash=hash_password(password),
                role=role.value,
                employee_id=None,
                is_active=True,
            )
        except IntegrityError as exc:
            raise APIError(
                status_code=409,
                code="ACCOUNT_EXISTS",
                message="An account with this email already exists.",
            ) from exc
        return to_auth_user(record)

    try:
        if session is not None:
            user = _register(session)
        else:
            with session_scope() as db:
                user = _register(db)
    except APIError:
        raise
    except IntegrityError as exc:
        raise APIError(
            status_code=409,
            code="ACCOUNT_EXISTS",
            message="An account with this email already exists.",
        ) from exc
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

    return RegisterResponse(
        message="Account created successfully.",
        user=to_public_user(user),
    )
