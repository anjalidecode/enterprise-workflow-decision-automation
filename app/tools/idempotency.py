"""Reusable idempotency helpers for write tools."""

from __future__ import annotations

from typing import Any


def build_idempotency_key(
    *,
    capability: str,
    workflow_id: str,
    organization_id: str = "",
    **parts: Any,
) -> str:
    """Build a stable key so retries cannot double-apply the same write action.

    Organization is included so multi-tenant writes never collide across companies.
    Empty organization_id remains valid for the current single-tenant simulation.
    """

    fragments = [
        organization_id or "_",
        workflow_id or "_",
        capability,
    ]
    for key in sorted(parts):
        value = parts[key]
        fragments.append(f"{key}={'' if value is None else value}")
    return ":".join(str(item) for item in fragments)
