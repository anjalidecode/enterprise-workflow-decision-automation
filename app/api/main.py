"""FastAPI application entrypoint for the enterprise workflow API.

Start with:
    uvicorn app.api.main:app --reload

CLI (`python run.py`) remains an independent local development interface.
FastAPI is the authenticated application interface (Module 5B JWT/RBAC).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    resume_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes import approvals, auth, health, workflows
from app.config.settings import get_settings
from app.workflows.errors import WorkflowResumeError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Enterprise Workflow Decision Automation API",
        description=(
            "REST API over the existing WorkflowEngine with JWT authentication "
            "and development RBAC (Module 5B). Thin application layer — no duplicated "
            "workflow logic. Development user store is temporary; durable auth storage "
            "arrives later. In-memory execution index and approval checkpoints are "
            "process-local."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*", "X-Request-ID", "Authorization"],
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
    application.include_router(auth.router, prefix=prefix)
    application.include_router(workflows.router, prefix=prefix)
    application.include_router(approvals.router, prefix=prefix)

    def custom_openapi() -> dict:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste the access_token from POST /api/v1/auth/login",
        }
        # Apply Bearer security globally; public routes can override with [].
        schema["security"] = [{"BearerAuth": []}]
        # Keep health + login explicitly public in OpenAPI.
        paths = schema.get("paths", {})
        for path_key, methods in paths.items():
            if path_key.endswith("/health") or path_key.endswith("/auth/login"):
                for method_spec in methods.values():
                    if isinstance(method_spec, dict):
                        method_spec["security"] = []
        application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = custom_openapi  # type: ignore[method-assign]
    return application


app = create_app()
