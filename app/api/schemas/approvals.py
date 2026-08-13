"""Approval API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRequest(BaseModel):
    """Approval action body. Approver identity/role come from the JWT only."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(default="")
