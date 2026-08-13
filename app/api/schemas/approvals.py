"""Approval API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ApprovalRequest(BaseModel):
    """Development-mode approval context until Module 5B authentication."""

    user_id: str = Field(..., min_length=1)
    user_role: str = Field(default="manager")
    reason: str = Field(default="")

    @field_validator("user_id")
    @classmethod
    def user_id_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_id must be a non-empty string")
        return cleaned
