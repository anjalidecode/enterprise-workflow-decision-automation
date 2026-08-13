"""Structured API error responses (no stack traces or secrets)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas.common import APIErrorBody, APIErrorDetail
from app.workflows.errors import WorkflowResumeError


class APIError(Exception):
    """Raised by API routes to produce a structured error response."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


def error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = APIErrorBody(
        error=APIErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            details=details or {},
        )
    )
    return body.model_dump()


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=exc.code,
            message=exc.message,
            request_id=_request_id(request),
            details=exc.details,
        ),
        headers={"X-Request-ID": _request_id(request)},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 400:
        code = "INVALID_REQUEST"
    elif exc.status_code == 401:
        code = "AUTHENTICATION_REQUIRED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 409:
        code = "CONFLICT"
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        code = str(detail["code"])
        message = str(detail["message"])
    else:
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=code,
            message=message,
            request_id=_request_id(request),
        ),
        headers={"X-Request-ID": _request_id(request)},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    safe_errors: list[dict[str, Any]] = []
    for item in exc.errors():
        entry = {
            "type": item.get("type"),
            "loc": list(item.get("loc") or []),
            "msg": item.get("msg"),
        }
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            entry["ctx"] = {
                key: (str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value)
                for key, value in ctx.items()
            }
        safe_errors.append(entry)
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=_request_id(request),
            details={"errors": safe_errors},
        ),
        headers={"X-Request-ID": _request_id(request)},
    )


async def resume_error_handler(request: Request, exc: WorkflowResumeError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error_payload(
            code="WORKFLOW_NOT_RESUMABLE",
            message=str(exc),
            request_id=_request_id(request),
        ),
        headers={"X-Request-ID": _request_id(request)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Do not expose stack traces, paths, or internal exception dumps.
    return JSONResponse(
        status_code=500,
        content=error_payload(
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred.",
            request_id=_request_id(request),
        ),
        headers={"X-Request-ID": _request_id(request)},
    )
