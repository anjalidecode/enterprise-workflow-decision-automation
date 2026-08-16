"""Recipient resolution from authoritative backend data only."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.auth.models import Role, UserStatus
from app.auth.permissions import APPROVER_ROLES
from app.database.models.user import UserRecord
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.user import UserRepository


@dataclass(frozen=True)
class ResolvedRecipient:
    user_id: str
    email: str
    full_name: str
    role: str
    organization_id: str
    organization_name: str


def organization_name(session: Session, organization_id: str) -> str:
    org = OrganizationRepository(session).get_by_organization_id(organization_id)
    if org is None:
        return organization_id
    return org.name or organization_id


def resolve_user(
    session: Session,
    *,
    user_id: str,
    organization_id: str,
) -> ResolvedRecipient | None:
    repo = UserRepository(session)
    record = repo.get_in_organization(user_id, organization_id)
    if record is None:
        return None
    return _from_record(session, record)


def resolve_user_by_email(
    session: Session,
    *,
    email: str,
    organization_id: str,
) -> ResolvedRecipient | None:
    record = UserRepository(session).get_by_username(email)
    if record is None or record.organization_id != organization_id:
        return None
    return _from_record(session, record)


def resolve_approvers(
    session: Session,
    *,
    organization_id: str,
    required_role: str = "manager",
) -> list[ResolvedRecipient]:
    """Return authorized approvers for the org. Never trust client-supplied emails."""

    role_key = (required_role or "manager").strip().lower()
    preferred: list[str]
    if role_key == "admin":
        preferred = [Role.ADMIN.value]
    elif role_key == "hr":
        preferred = [Role.HR.value, Role.ADMIN.value]
    else:
        # manager (default): managers first, then HR, then admin
        preferred = [Role.MANAGER.value, Role.HR.value, Role.ADMIN.value]

    repo = UserRepository(session)
    found: list[ResolvedRecipient] = []
    seen: set[str] = set()
    for role in preferred:
        records, _ = repo.list_for_organization(
            organization_id,
            role=role,
            status=UserStatus.ACTIVE.value,
            limit=50,
            offset=0,
        )
        for record in records:
            if not record.is_active:
                continue
            try:
                user_role = Role(record.role)
            except ValueError:
                continue
            if user_role not in APPROVER_ROLES:
                continue
            if record.user_id in seen:
                continue
            seen.add(record.user_id)
            recipient = _from_record(session, record)
            if recipient is not None:
                found.append(recipient)
        # Prefer the primary role cohort; only fall through if empty.
        if found and role == preferred[0]:
            break
    return found


def _from_record(session: Session, record: UserRecord) -> ResolvedRecipient | None:
    email = (record.username or "").strip().lower()
    if not email or "@" not in email:
        # Demo seed usernames like admin001 are not emails — skip email delivery.
        return None
    org_name = organization_name(session, record.organization_id)
    return ResolvedRecipient(
        user_id=record.user_id,
        email=email,
        full_name=(record.full_name or "").strip() or email,
        role=record.role,
        organization_id=record.organization_id,
        organization_name=org_name,
    )


from app.notifications.recipients import (
    ResolvedRecipient,
    organization_name,
    resolve_approvers,
    resolve_user,
    resolve_user_by_email,
)

__all__ = [
    "ResolvedRecipient",
    "organization_name",
    "resolve_approvers",
    "resolve_user",
    "resolve_user_by_email",
]
