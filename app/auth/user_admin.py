"""Organization-scoped user administration. Authorization uses JWT current_user only."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.auth.employee_binding import (
    assert_employee_bindable,
    binding_required_for_role,
    list_organization_directory,
)
from app.auth.models import ASSIGNABLE_ROLES, Role, User, UserStatus
from app.auth.schemas import (
    DirectoryEmployee,
    EmployeeDirectoryResponse,
    InvitationInfo,
    InviteUserResponse,
    ManagedUserPublic,
    NotificationInfo,
    UserListResponse,
)
from app.auth.security import (
    generate_invite_token,
    hash_invite_token,
    hash_password,
    unusable_password_hash,
)
from app.auth.service import _EMAIL_RE, validate_password
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.models.user import UserRecord
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.user import UserRepository, to_auth_user
from app.database.session import session_scope
from app.notifications.models import NotificationEventPayload, NotificationEventType
from app.notifications.service import (
    frontend_url,
    get_business_notification_service,
    role_label,
)

INVITE_TTL_DAYS = 7


def _db_error(exc: Exception) -> APIError:
    if isinstance(exc, DatabaseNotConfiguredError):
        return APIError(
            status_code=503,
            code="DATABASE_NOT_CONFIGURED",
            message=str(exc),
        )
    if isinstance(exc, DatabaseUnavailableError):
        return APIError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message=str(exc),
        )
    raise exc


def _created_at_iso(record: UserRecord) -> str | None:
    created = record.created_at
    if created is None:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created.isoformat()


def to_managed_user(record: UserRecord) -> ManagedUserPublic:
    auth = to_auth_user(record)
    return ManagedUserPublic(
        user_id=auth.user_id,
        username=auth.username,
        full_name=auth.full_name,
        organization_id=auth.organization_id,
        role=auth.role,
        employee_id=auth.employee_id,
        status=auth.status,
        is_active=auth.is_active,
        created_at=_created_at_iso(record),
    )


def _require_assignable_role(role: Role) -> None:
    if role not in ASSIGNABLE_ROLES:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Role must be employee, manager, or hr.",
        )


def _org_user_or_404(repo: UserRepository, *, user_id: str, organization_id: str) -> UserRecord:
    record = repo.get_in_organization(user_id, organization_id)
    if record is None:
        raise APIError(
            status_code=404,
            code="NOT_FOUND",
            message="User not found.",
        )
    return record


def _prevent_last_admin_loss(
    repo: UserRepository,
    *,
    organization_id: str,
    target: UserRecord,
    new_role: str | None = None,
    new_status: str | None = None,
) -> None:
    is_admin = target.role == Role.ADMIN.value
    if not is_admin:
        return
    remaining = repo.count_active_admins(organization_id)
    would_lose_admin = False
    if new_role is not None and new_role != Role.ADMIN.value:
        would_lose_admin = True
    if new_status is not None and new_status != UserStatus.ACTIVE.value:
        would_lose_admin = True
    if would_lose_admin and remaining <= 1:
        raise APIError(
            status_code=400,
            code="LAST_ADMIN",
            message="This organization must keep at least one active administrator.",
        )


def list_users(
    actor: User,
    *,
    search: str | None = None,
    role: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session | None = None,
) -> UserListResponse:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    role_key = role.strip().lower() if role else None
    status_key = status.strip().lower() if status else None
    if role_key:
        try:
            Role(role_key)
        except ValueError as exc:
            raise APIError(
                status_code=400,
                code="INVALID_REQUEST",
                message="Unknown role filter.",
            ) from exc
    if status_key:
        try:
            UserStatus(status_key)
        except ValueError as exc:
            raise APIError(
                status_code=400,
                code="INVALID_REQUEST",
                message="Unknown status filter.",
            ) from exc

    def _run(db: Session) -> UserListResponse:
        repo = UserRepository(db)
        records, total = repo.list_for_organization(
            actor.organization_id,
            search=search,
            role=role_key,
            status=status_key,
            limit=limit,
            offset=offset,
        )
        return UserListResponse(
            users=[to_managed_user(item) for item in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def list_employees(actor: User, *, session: Session | None = None) -> EmployeeDirectoryResponse:
    def _run(db: Session) -> EmployeeDirectoryResponse:
        items = list_organization_directory(db, actor.organization_id)
        return EmployeeDirectoryResponse(
            employees=[DirectoryEmployee.model_validate(item) for item in items]
        )

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def get_user(actor: User, user_id: str, *, session: Session | None = None) -> ManagedUserPublic:
    def _run(db: Session) -> ManagedUserPublic:
        repo = UserRepository(db)
        record = _org_user_or_404(
            repo,
            user_id=user_id,
            organization_id=actor.organization_id,
        )
        return to_managed_user(record)

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def invite_user(
    actor: User,
    *,
    full_name: str,
    email: str,
    role: Role,
    employee_id: str | None = None,
    session: Session | None = None,
) -> InviteUserResponse:
    _require_assignable_role(role)
    name = full_name.strip()
    if len(name) < 2:
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

    token = generate_invite_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    def _run(db: Session) -> UserRecord:
        repo = UserRepository(db)
        if repo.get_by_username(email_key) is not None:
            raise APIError(
                status_code=409,
                code="ACCOUNT_EXISTS",
                message="An account with this email already exists.",
            )
        bound_employee_id = assert_employee_bindable(
            db,
            organization_id=actor.organization_id,
            employee_id=employee_id,
            required=binding_required_for_role(role),
        )
        try:
            return repo.create(
                user_id=f"user-{uuid.uuid4().hex[:12]}",
                organization_id=actor.organization_id,
                username=email_key,
                password_hash=unusable_password_hash(),
                role=role.value,
                employee_id=bound_employee_id,
                is_active=False,
                full_name=name,
                status=UserStatus.INVITED.value,
                invite_token_hash=hash_invite_token(token),
                invite_expires_at=expires_at,
            )
        except IntegrityError as exc:
            raise APIError(
                status_code=409,
                code="ACCOUNT_EXISTS",
                message="An account with this email already exists.",
            ) from exc

    try:
        if session is not None:
            record = _run(session)
            notification = _send_invitation_email(
                session,
                record=record,
                token=token,
                expires_at=expires_at,
                organization_id=actor.organization_id,
            )
        else:
            with session_scope() as db:
                record = _run(db)
                notification = _send_invitation_email(
                    db,
                    record=record,
                    token=token,
                    expires_at=expires_at,
                    organization_id=actor.organization_id,
                )
    except APIError:
        raise
    except IntegrityError as exc:
        raise APIError(
            status_code=409,
            code="ACCOUNT_EXISTS",
            message="An account with this email already exists.",
        ) from exc
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc

    activation_path = f"/activate?token={token}"
    base_message = "Invitation created successfully."
    message = (
        f"{base_message} {notification.message}".strip()
        if notification is not None
        else base_message
    )
    return InviteUserResponse(
        message=message,
        user=to_managed_user(record),
        invitation=InvitationInfo(
            expires_at=expires_at.isoformat(),
            activation_path=activation_path,
            activation_token=token,
        ),
        notification=notification,
    )


def _send_invitation_email(
    session: Session,
    *,
    record: UserRecord,
    token: str,
    expires_at: datetime,
    organization_id: str,
) -> NotificationInfo:
    org = OrganizationRepository(session).get_by_organization_id(organization_id)
    org_name = org.name if org is not None else organization_id
    # Activation link uses the existing one-time token mechanism. Do not log the raw token.
    activation_url = frontend_url(f"/activate?token={token}")
    result = get_business_notification_service().dispatch(
        NotificationEventPayload(
            event_type=NotificationEventType.USER_INVITED,
            organization_id=organization_id,
            idempotency_key=f"USER_INVITED:{record.user_id}",
            recipient_user_id=record.user_id,
            recipient_email=record.username,
            recipient_name=record.full_name or record.username,
            context={
                "organization_name": org_name,
                "role": record.role,
                "role_label": role_label(record.role),
                "activation_url": activation_url,
                "expires_at": expires_at.isoformat(),
            },
        ),
        session=session,
    )
    return NotificationInfo(
        event_type=result.event_type.value if result.event_type else None,
        status=result.status.value,
        message=result.public_message,
        provider=result.provider,
    )


def patch_user(
    actor: User,
    user_id: str,
    *,
    role: Role | None,
    employee_id: str | None = None,
    session: Session | None = None,
) -> ManagedUserPublic:
    if role is None and employee_id is None:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Provide a role or employee binding to update.",
        )
    if role is not None:
        _require_assignable_role(role)

    def _run(db: Session) -> ManagedUserPublic:
        repo = UserRepository(db)
        record = _org_user_or_404(
            repo,
            user_id=user_id,
            organization_id=actor.organization_id,
        )
        next_role = Role(role.value) if role is not None else Role(record.role)
        if role is not None:
            _prevent_last_admin_loss(
                repo,
                organization_id=actor.organization_id,
                target=record,
                new_role=role.value,
            )
        if actor.user_id == user_id:
            raise APIError(
                status_code=400,
                code="SELF_ACTION_FORBIDDEN",
                message="You cannot change your own role or employee binding.",
            )
        if role is not None:
            record.role = role.value
        requested_employee_id = employee_id if employee_id is not None else record.employee_id
        record.employee_id = assert_employee_bindable(
            db,
            organization_id=actor.organization_id,
            employee_id=requested_employee_id,
            required=binding_required_for_role(next_role),
            exclude_user_id=record.user_id,
        )
        db.flush()
        return to_managed_user(record)

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def deactivate_user(
    actor: User,
    user_id: str,
    *,
    session: Session | None = None,
) -> ManagedUserPublic:
    if actor.user_id == user_id:
        raise APIError(
            status_code=400,
            code="SELF_ACTION_FORBIDDEN",
            message="You cannot deactivate your own account.",
        )

    def _run(db: Session) -> ManagedUserPublic:
        repo = UserRepository(db)
        record = _org_user_or_404(
            repo,
            user_id=user_id,
            organization_id=actor.organization_id,
        )
        _prevent_last_admin_loss(
            repo,
            organization_id=actor.organization_id,
            target=record,
            new_status=UserStatus.INACTIVE.value,
        )
        record.status = UserStatus.INACTIVE.value
        record.is_active = False
        record.invite_token_hash = None
        record.invite_expires_at = None
        db.flush()
        return to_managed_user(record)

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def activate_user(
    actor: User,
    user_id: str,
    *,
    session: Session | None = None,
) -> ManagedUserPublic:
    if actor.user_id == user_id:
        raise APIError(
            status_code=400,
            code="SELF_ACTION_FORBIDDEN",
            message="Your account is already active.",
        )

    def _run(db: Session) -> ManagedUserPublic:
        repo = UserRepository(db)
        record = _org_user_or_404(
            repo,
            user_id=user_id,
            organization_id=actor.organization_id,
        )
        if record.status == UserStatus.INVITED.value:
            raise APIError(
                status_code=400,
                code="INVALID_REQUEST",
                message="Invited users must set a password with the activation link before they can sign in.",
            )
        record.status = UserStatus.ACTIVE.value
        record.is_active = True
        db.flush()
        return to_managed_user(record)

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc


def complete_invitation(
    *,
    token: str,
    password: str,
    confirm_password: str,
    session: Session | None = None,
) -> ManagedUserPublic:
    validate_password(password, confirm_password)
    token_key = token.strip()
    if not token_key:
        raise APIError(
            status_code=400,
            code="INVALID_REQUEST",
            message="Invitation token is required.",
        )
    token_hash = hash_invite_token(token_key)

    def _run(db: Session) -> ManagedUserPublic:
        repo = UserRepository(db)
        record = repo.get_by_invite_token_hash(token_hash)
        if record is None or record.status != UserStatus.INVITED.value:
            raise APIError(
                status_code=400,
                code="INVALID_REQUEST",
                message="Invitation is invalid or has already been used.",
            )
        expires = record.invite_expires_at
        now = datetime.now(timezone.utc)
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is None or expires < now:
            raise APIError(
                status_code=400,
                code="INVALID_REQUEST",
                message="Invitation has expired. Ask an administrator to send a new invitation.",
            )
        record.password_hash = hash_password(password)
        record.status = UserStatus.ACTIVE.value
        record.is_active = True
        record.invite_token_hash = None
        record.invite_expires_at = None
        db.flush()
        return to_managed_user(record)

    try:
        if session is not None:
            return _run(session)
        with session_scope() as db:
            return _run(db)
    except APIError:
        raise
    except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
        raise _db_error(exc) from exc
