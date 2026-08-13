"""Auth domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR = "hr"
    ADMIN = "admin"


@dataclass(frozen=True)
class User:
    """Internal user record. Never serialize password_hash to API clients."""

    user_id: str
    organization_id: str
    username: str
    password_hash: str
    role: Role
    employee_id: str | None = None
    is_active: bool = True
