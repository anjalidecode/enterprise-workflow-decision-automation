"""User repository — authentication lookups always organization-aware where needed."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.models import Role, User, UserStatus
from app.database.models.user import UserRecord


def to_auth_user(record: UserRecord) -> User:
    status_value = (record.status or UserStatus.ACTIVE.value).lower()
    try:
        status = UserStatus(status_value)
    except ValueError:
        status = UserStatus.ACTIVE if record.is_active else UserStatus.INACTIVE
    return User(
        user_id=record.user_id,
        organization_id=record.organization_id,
        username=record.username,
        password_hash=record.password_hash,
        role=Role(record.role),
        employee_id=record.employee_id,
        is_active=record.is_active,
        full_name=record.full_name,
        status=status,
    )


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> UserRecord | None:
        key = username.strip().lower()
        stmt = select(UserRecord).where(UserRecord.username == key)
        return self._session.scalars(stmt).first()

    def get_by_user_id(self, user_id: str) -> UserRecord | None:
        stmt = select(UserRecord).where(UserRecord.user_id == user_id)
        return self._session.scalars(stmt).first()

    def get_auth_user_by_username(self, username: str) -> User | None:
        record = self.get_by_username(username)
        return to_auth_user(record) if record else None

    def get_auth_user_by_id(self, user_id: str) -> User | None:
        record = self.get_by_user_id(user_id)
        return to_auth_user(record) if record else None

    def count_by_organization(self, organization_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(UserRecord)
            .where(UserRecord.organization_id == organization_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def count_active_admins(self, organization_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(UserRecord)
            .where(
                UserRecord.organization_id == organization_id,
                UserRecord.role == Role.ADMIN.value,
                UserRecord.status == UserStatus.ACTIVE.value,
                UserRecord.is_active.is_(True),
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def get_in_organization(
        self,
        user_id: str,
        organization_id: str,
    ) -> UserRecord | None:
        stmt = select(UserRecord).where(
            UserRecord.user_id == user_id,
            UserRecord.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def get_by_invite_token_hash(self, token_hash: str) -> UserRecord | None:
        stmt = select(UserRecord).where(UserRecord.invite_token_hash == token_hash)
        return self._session.scalars(stmt).first()

    def list_for_organization(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        role: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserRecord], int]:
        filters = [UserRecord.organization_id == organization_id]
        if role:
            filters.append(UserRecord.role == role)
        if status:
            filters.append(UserRecord.status == status)
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(UserRecord.username).like(pattern),
                    func.lower(func.coalesce(UserRecord.full_name, "")).like(pattern),
                )
            )

        count_stmt = (
            select(func.count()).select_from(UserRecord).where(*filters)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            select(UserRecord)
            .where(*filters)
            .order_by(UserRecord.created_at.desc(), UserRecord.username.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all()), total

    def create(
        self,
        *,
        user_id: str,
        organization_id: str,
        username: str,
        password_hash: str,
        role: str,
        employee_id: str | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        status: str = UserStatus.ACTIVE.value,
        invite_token_hash: str | None = None,
        invite_expires_at: datetime | None = None,
    ) -> UserRecord:
        record = UserRecord(
            user_id=user_id,
            organization_id=organization_id,
            username=username.strip().lower(),
            password_hash=password_hash,
            role=role,
            employee_id=employee_id,
            is_active=is_active,
            full_name=full_name,
            status=status,
            invite_token_hash=invite_token_hash,
            invite_expires_at=invite_expires_at,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def upsert(
        self,
        *,
        user_id: str,
        organization_id: str,
        username: str,
        password_hash: str,
        role: str,
        employee_id: str | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        status: str | None = None,
        invite_token_hash: str | None = None,
        invite_expires_at: datetime | None = None,
    ) -> UserRecord:
        resolved_status = status or (
            UserStatus.ACTIVE.value if is_active else UserStatus.INACTIVE.value
        )
        existing = self.get_by_user_id(user_id) or self.get_by_username(username)
        if existing is None:
            return self.create(
                user_id=user_id,
                organization_id=organization_id,
                username=username,
                password_hash=password_hash,
                role=role,
                employee_id=employee_id,
                is_active=is_active,
                full_name=full_name,
                status=resolved_status,
                invite_token_hash=invite_token_hash,
                invite_expires_at=invite_expires_at,
            )
        existing.user_id = user_id
        existing.organization_id = organization_id
        existing.username = username.strip().lower()
        existing.password_hash = password_hash
        existing.role = role
        existing.employee_id = employee_id
        existing.is_active = is_active
        existing.full_name = full_name
        existing.status = resolved_status
        existing.invite_token_hash = invite_token_hash
        existing.invite_expires_at = invite_expires_at
        self._session.flush()
        return existing
