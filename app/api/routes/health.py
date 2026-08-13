"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import SettingsDep
from app.api.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description=(
        "Lightweight liveness check. Does not run workflows. "
        "No API key required (authentication arrives in Module 5B)."
    ),
)
def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
