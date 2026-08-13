"""PostgreSQL persistence layer for platform/application records (Module 5C).

WorkflowState remains the live per-run coordination state. This package stores
organizations, users, workflow runs, decisions, approvals, audit, and metrics.
"""

from app.database.session import get_engine, get_session_factory, session_scope

__all__ = [
    "get_engine",
    "get_session_factory",
    "session_scope",
]
