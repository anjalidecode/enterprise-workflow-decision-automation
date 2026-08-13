"""FastAPI dependencies: shared engine, index, and request correlation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.api.execution_index import ExecutionIndex, get_execution_index
from app.config.settings import Settings, get_settings
from app.workflows.engine import WorkflowEngine, get_workflow_engine


def get_engine() -> WorkflowEngine:
    """Application-scoped WorkflowEngine (process singleton; preserves checkpoints)."""

    return get_workflow_engine()


def get_index() -> ExecutionIndex:
    return get_execution_index()


def get_app_settings() -> Settings:
    return get_settings()


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


EngineDep = Annotated[WorkflowEngine, Depends(get_engine)]
IndexDep = Annotated[ExecutionIndex, Depends(get_index)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
