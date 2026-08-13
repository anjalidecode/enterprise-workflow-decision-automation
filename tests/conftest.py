"""Shared pytest fixtures — isolated PostgreSQL test database for Module 5C."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import text

from app.memory.facade import reset_memory
from app.services.attendance_store import reset_attendance_store
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.onboarding_store import reset_onboarding_store
from app.services.performance_store import reset_performance_store
from app.services.recruitment_store import reset_recruitment_store
from app.services.training_store import reset_training_store
from app.services.offboarding_store import reset_offboarding_store
from app.services.hr_services_store import reset_hr_services_store
from app.api.execution_index import reset_execution_index
from app.auth.store import reset_user_store
from app.tools.catalog import reset_registry
from app.workflows.engine import reset_workflow_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://postgres@127.0.0.1:5433/enterprise_workflow_test"
)


def _configure_test_database() -> str:
    url = (
        os.environ.get("TEST_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
        or DEFAULT_TEST_DATABASE_URL
    )
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("APP_ENV", "test")
    return url


@pytest.fixture(scope="session", autouse=True)
def _session_database() -> None:
    """Point the process at an isolated test database and ensure schema exists."""

    url = _configure_test_database()
    from app.config.settings import get_settings
    from app.database.base import Base
    from app.database.session import get_engine, reset_engine
    import app.database.models  # noqa: F401

    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()
    get_settings.cache_clear()
    # Avoid leaking the test URL into unrelated interactive shells unexpectedly.
    if os.environ.get("DATABASE_URL") == url:
        # Keep for subsequent pytest invocations in the same process.
        pass


def _truncate_and_seed() -> None:
    from app.database.seed import _seed_password_hash, seed_development_data
    from app.database.session import get_engine

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "metrics, audits, decisions, approvals, workflow_runs, users, organizations "
                "RESTART IDENTITY CASCADE"
            )
        )
    seed_development_data(password_hash=_seed_password_hash())


@pytest.fixture(autouse=True)
def reset_simulated_runtime() -> None:
    _configure_test_database()
    from app.config.settings import get_settings

    get_settings.cache_clear()

    reset_hr_store()
    reset_recruitment_store()
    reset_onboarding_store()
    reset_attendance_store()
    reset_performance_store()
    reset_training_store()
    reset_offboarding_store()
    reset_hr_services_store()
    reset_notification_service()
    reset_registry()
    reset_memory()
    reset_execution_index()
    reset_user_store()
    _truncate_and_seed()
    # API/auth paths enable persistence via get_engine when DATABASE_URL is set.
    reset_workflow_engine(with_persistence=False)
    yield
    reset_hr_store()
    reset_recruitment_store()
    reset_onboarding_store()
    reset_attendance_store()
    reset_performance_store()
    reset_training_store()
    reset_offboarding_store()
    reset_hr_services_store()
    reset_notification_service()
    reset_memory()
    reset_workflow_engine(with_persistence=False)
    reset_execution_index()
    reset_user_store()
