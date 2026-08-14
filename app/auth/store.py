"""Development user definitions used by database seed (Module 5C).

Runtime authentication reads users from PostgreSQL via UserRepository.
This module still builds the canonical demo user list for seeding and tests.
Passwords are stored only as bcrypt hashes — never plaintext.
"""

from __future__ import annotations

from app.auth.models import Role, User, UserStatus
from app.auth.security import hash_password

# Documented development password for all demo users (not a production secret).
DEV_PASSWORD = "dev-password-123"

# Hash once for the demo store (low rounds = faster tests/startup; still not plaintext).
_DEV_PASSWORD_HASH: str | None = None


def _demo_password_hash() -> str:
    global _DEV_PASSWORD_HASH
    if _DEV_PASSWORD_HASH is None:
        _DEV_PASSWORD_HASH = hash_password(DEV_PASSWORD, rounds=4)
    return _DEV_PASSWORD_HASH


def _user(
    *,
    user_id: str,
    organization_id: str,
    username: str,
    role: Role,
    employee_id: str | None = None,
    is_active: bool = True,
    password_hash: str | None = None,
    full_name: str | None = None,
) -> User:
    return User(
        user_id=user_id,
        organization_id=organization_id,
        username=username,
        password_hash=password_hash or _demo_password_hash(),
        role=role,
        employee_id=employee_id,
        is_active=is_active,
        full_name=full_name,
        status=UserStatus.ACTIVE if is_active else UserStatus.INACTIVE,
    )


class UserStore:
    """Process-local username → User map."""

    def __init__(self, users: list[User] | None = None) -> None:
        self._by_username: dict[str, User] = {}
        self._by_id: dict[str, User] = {}
        for user in users or []:
            self.add(user)

    def add(self, user: User) -> None:
        self._by_username[user.username.lower()] = user
        self._by_id[user.user_id] = user

    def get_by_username(self, username: str) -> User | None:
        return self._by_username.get(username.strip().lower())

    def get_by_id(self, user_id: str) -> User | None:
        return self._by_id.get(user_id)


def build_demo_users() -> list[User]:
    """Fictional demo accounts for local development and tests."""

    hashed = _demo_password_hash()
    return [
        _user(
            user_id="user-employee-001",
            organization_id="demo-org",
            username="employee001",
            role=Role.EMPLOYEE,
            employee_id="E001",
            password_hash=hashed,
            full_name="Demo Employee",
        ),
        _user(
            user_id="user-manager-001",
            organization_id="demo-org",
            username="manager001",
            role=Role.MANAGER,
            employee_id="E100",
            password_hash=hashed,
            full_name="Demo Manager",
        ),
        _user(
            user_id="user-hr-001",
            organization_id="demo-org",
            username="hr001",
            role=Role.HR,
            employee_id=None,
            password_hash=hashed,
            full_name="Demo HR",
        ),
        _user(
            user_id="user-admin-001",
            organization_id="demo-org",
            username="admin001",
            role=Role.ADMIN,
            employee_id=None,
            password_hash=hashed,
            full_name="Demo Admin",
        ),
        _user(
            user_id="user-inactive-001",
            organization_id="demo-org",
            username="inactive001",
            role=Role.EMPLOYEE,
            employee_id="E099",
            is_active=False,
            password_hash=hashed,
            full_name="Inactive Employee",
        ),
        _user(
            user_id="user-employee-other",
            organization_id="other-org",
            username="employee_other",
            role=Role.EMPLOYEE,
            employee_id="E050",
            password_hash=hashed,
            full_name="Other Org Employee",
        ),
        _user(
            user_id="user-hr-other",
            organization_id="other-org",
            username="hr_other",
            role=Role.HR,
            employee_id=None,
            password_hash=hashed,
            full_name="Other Org HR",
        ),
    ]


_STORE: UserStore | None = None


def get_user_store() -> UserStore:
    global _STORE
    if _STORE is None:
        _STORE = UserStore(build_demo_users())
    return _STORE


def reset_user_store() -> UserStore:
    global _STORE
    _STORE = UserStore(build_demo_users())
    return _STORE
