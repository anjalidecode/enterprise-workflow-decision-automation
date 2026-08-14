"""User repository — authentication lookups always organization-aware where needed."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.database.models.user import UserRecord


def to_auth_user(record: UserRecord) -> User:
    return User(
        user_id=record.user_id,
        organization_id=record.organization_id,
        username=record.username,
        password_hash=record.password_hash,
        role=Role(record.role),
        employee_id=record.employee_id,
        is_active=record.is_active,
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
    ) -> UserRecord:
        record = UserRecord(
            user_id=user_id,
            organization_id=organization_id,
            username=username.strip().lower(),
            password_hash=password_hash,
            role=role,
            employee_id=employee_id,
            is_active=is_active,
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
    ) -> UserRecord:
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
            )
        existing.user_id = user_id
        existing.organization_id = organization_id
        existing.username = username.strip().lower()
        existing.password_hash = password_hash
        existing.role = role
        existing.employee_id = employee_id
        existing.is_active = is_active
        self._session.flush()
        return existing
