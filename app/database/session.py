"""SQLAlchemy engine and session lifecycle.

One engine per process. Session-per-operation (or per-request via FastAPI Depends).
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError

logger = logging.getLogger(__name__)

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def reset_engine() -> None:
    """Dispose the process engine (tests / reconfiguration)."""

    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None


def get_engine(settings: Settings | None = None) -> Engine:
    """Return the shared SQLAlchemy engine. Requires DATABASE_URL."""

    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        return _ENGINE

    cfg = settings or get_settings()
    try:
        url = cfg.require_database_url
    except RuntimeError as exc:
        raise DatabaseNotConfiguredError(str(exc)) from exc

    _ENGINE = create_engine(
        url,
        pool_size=cfg.database_pool_size,
        max_overflow=cfg.database_max_overflow,
        pool_pre_ping=True,
        future=True,
    )

    @event.listens_for(_ENGINE, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        # Keep connections honest; never log credentials.
        logger.debug("database connection established")

    _SESSION_FACTORY = sessionmaker(
        bind=_ENGINE,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    return _ENGINE


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    get_engine(settings)
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    try:
        factory = get_session_factory(settings)
    except DatabaseNotConfiguredError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("database engine/session factory failed")
        raise DatabaseUnavailableError(
            "Database operation failed. Check server logs for details."
        ) from exc

    session = factory()
    try:
        yield session
        session.commit()
    except DatabaseNotConfiguredError:
        session.rollback()
        raise
    except DatabaseUnavailableError:
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("database operation failed")
        raise DatabaseUnavailableError(
            "Database operation failed. Check server logs for details."
        ) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""

    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("request database session failed")
        raise DatabaseUnavailableError(
            "Database operation failed. Check server logs for details."
        ) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
