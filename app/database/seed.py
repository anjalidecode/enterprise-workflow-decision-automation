"""Deterministic development database seed.

Usage:
    python -m app.database.seed

Requires DATABASE_URL. Stores bcrypt password hashes only — never plaintext.
Demo password is documented in README for local development only.
"""

from __future__ import annotations

import sys

from app.auth.models import Role
from app.auth.security import hash_password
from app.auth.store import DEV_PASSWORD, build_demo_users
from app.config.settings import get_settings
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.user import UserRepository
from app.database.session import session_scope

_CACHED_SEED_HASH: str | None = None


def _seed_password_hash(*, password: str = DEV_PASSWORD, rounds: int = 4) -> str:
    global _CACHED_SEED_HASH
    if _CACHED_SEED_HASH is None:
        _CACHED_SEED_HASH = hash_password(password, rounds=rounds)
    return _CACHED_SEED_HASH


def seed_development_data(
    *,
    password: str = DEV_PASSWORD,
    rounds: int = 4,
    password_hash: str | None = None,
) -> None:
    """Upsert demo organizations and users into PostgreSQL."""

    settings = get_settings()
    if not settings.has_database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not configured. Set it before running the seed command."
        )

    hashed = password_hash or _seed_password_hash(password=password, rounds=rounds)
    demo_users = build_demo_users()
    orgs = {
        "demo-org": "Demo Organization",
        "other-org": "Other Organization",
    }

    with session_scope(settings) as session:
        org_repo = OrganizationRepository(session)
        user_repo = UserRepository(session)
        for organization_id, name in orgs.items():
            org_repo.create(organization_id=organization_id, name=name, is_active=True)

        for user in demo_users:
            user_repo.upsert(
                user_id=user.user_id,
                organization_id=user.organization_id,
                username=user.username,
                password_hash=hashed,
                role=user.role.value if isinstance(user.role, Role) else str(user.role),
                employee_id=user.employee_id,
                is_active=user.is_active,
                full_name=user.full_name,
                status=user.status.value,
            )


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        seed_development_data()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except DatabaseUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"ERROR: seed failed ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print("Seed complete: demo organizations and development users are ready.")
    print("Demo password is documented in README (local development only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
