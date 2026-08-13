"""FastAPI application entrypoint for the enterprise workflow API (Module 5A).

Start with:
    uvicorn app.api.main:app --reload

CLI (`python run.py`) remains an independent interface over the same WorkflowEngine.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    resume_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes import approvals, health, workflows
from app.config.settings import get_settings
from app.workflows.errors import WorkflowResumeError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Enterprise Workflow Decision Automation API",
        description=(
            "Module 5A REST API over the existing WorkflowEngine. "
            "Thin application layer — no duplicated workflow logic. "
            "Development-mode organization/user context only; authentication "
            "and durable storage arrive in later Module 5 phases. "
            "In-memory execution index and approval checkpoints are process-local."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "").strip()
        request_id = incoming or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(WorkflowResumeError, resume_error_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)

    prefix = settings.api_v1_prefix
    application.include_router(health.router, prefix=prefix)
    application.include_router(workflows.router, prefix=prefix)
    application.include_router(approvals.router, prefix=prefix)

    return application


app = create_app()
