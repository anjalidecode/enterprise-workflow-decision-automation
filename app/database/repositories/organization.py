"""Organization repository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.organization import Organization


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_organization_id(self, organization_id: str) -> Organization | None:
        stmt = select(Organization).where(Organization.organization_id == organization_id)
        return self._session.scalars(stmt).first()

    def get_by_name(self, name: str) -> Organization | None:
        key = name.strip().lower()
        if not key:
            return None
        stmt = select(Organization).where(func.lower(Organization.name) == key)
        return self._session.scalars(stmt).first()

    def create(
        self,
        *,
        organization_id: str,
        name: str,
        is_active: bool = True,
    ) -> Organization:
        existing = self.get_by_organization_id(organization_id)
        if existing is not None:
            return existing
        org = Organization(
            organization_id=organization_id,
            name=name,
            is_active=is_active,
        )
        self._session.add(org)
        self._session.flush()
        return org
