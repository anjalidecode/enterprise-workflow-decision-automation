"""FastAPI dependencies: shared engine, DB session, and request correlation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.session import get_db_session
from app.workflows.engine import (
    WorkflowEngine,
    _default_load_checkpoint,
    _default_persist_result,
    get_workflow_engine,
)


def get_engine() -> WorkflowEngine:
    """Application-scoped WorkflowEngine with persistence when DATABASE_URL is set."""

    engine = get_workflow_engine()
    settings = get_settings()
    if settings.has_database_url and engine._persist_result is None:
        engine._persist_result = _default_persist_result
        engine._load_checkpoint = _default_load_checkpoint
    return engine


def get_app_settings() -> Settings:
    return get_settings()


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


EngineDep = Annotated[WorkflowEngine, Depends(get_engine)]
DbSessionDep = Annotated[Session, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
