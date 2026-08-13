"""FastAPI application layer (Module 5A). Thin HTTP facade over WorkflowEngine."""

from app.api.main import app, create_app

__all__ = ["app", "create_app"]
