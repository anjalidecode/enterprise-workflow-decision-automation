"""Password hashing and JWT helpers. Never log passwords or return hashes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config.settings import Settings, get_settings

# Production-strength default. Development demo users may use fewer rounds.
_DEFAULT_ROUNDS = 12


def hash_password(password: str, *, rounds: int = _DEFAULT_ROUNDS) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=rounds),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    role: str,
    employee_id: str | None = None,
    expires_minutes: int | None = None,
    settings: Settings | None = None,
) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""

    cfg = settings or get_settings()
    minutes = expires_minutes if expires_minutes is not None else cfg.jwt_access_token_expire_minutes
    expires_in = max(int(minutes), 1) * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "organization_id": organization_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if employee_id:
        payload["employee_id"] = employee_id
    token = jwt.encode(
        payload,
        cfg.resolved_jwt_secret,
        algorithm=cfg.jwt_algorithm,
    )
    return token, expires_in


def generate_invite_token() -> str:
    """High-entropy one-time invitation token. Never log or store the raw value."""

    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_tokens_match(raw_token: str, stored_hash: str) -> bool:
    expected = hash_invite_token(raw_token)
    return hmac.compare_digest(expected, stored_hash)


_UNUSABLE_PASSWORD_HASH: str | None = None


def unusable_password_hash(*, rounds: int = 4) -> str:
    """Bcrypt hash of a random secret so invited accounts cannot authenticate."""

    global _UNUSABLE_PASSWORD_HASH
    if _UNUSABLE_PASSWORD_HASH is None:
        _UNUSABLE_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32), rounds=rounds)
    return _UNUSABLE_PASSWORD_HASH


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    return jwt.decode(
        token,
        cfg.resolved_jwt_secret,
        algorithms=[cfg.jwt_algorithm],
        options={"require": ["sub", "exp", "organization_id", "role"]},
    )
