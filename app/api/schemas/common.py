"""Shared API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class APIErrorBody(BaseModel):
    error: APIErrorDetail


class APIErrorResponse(APIErrorBody):
    """Alias used in OpenAPI documentation."""


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
