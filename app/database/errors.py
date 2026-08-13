"""Database-layer errors mapped to structured API responses where appropriate."""

from __future__ import annotations


class DatabaseError(Exception):
    """Base class for persistence failures (no connection strings in messages)."""


class DatabaseNotConfiguredError(DatabaseError):
    """DATABASE_URL missing when a persistent operation is required."""


class DatabaseUnavailableError(DatabaseError):
    """PostgreSQL unreachable or query failed; safe for clients."""


class PersistenceConflictError(DatabaseError):
    """Duplicate or conflicting persistent record."""
