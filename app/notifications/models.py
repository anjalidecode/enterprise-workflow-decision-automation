"""Notification event models — no secrets, passwords, JWTs, or raw tokens."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NotificationEventType(str, Enum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_INVITED = "USER_INVITED"
    WORKFLOW_PENDING_APPROVAL = "WORKFLOW_PENDING_APPROVAL"
    WORKFLOW_APPROVED = "WORKFLOW_APPROVED"
    WORKFLOW_REJECTED = "WORKFLOW_REJECTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_BLOCKED = "WORKFLOW_BLOCKED"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    GENERATED = "generated"  # console provider rendered without SMTP


class EmailMessage(BaseModel):
    """Rendered email ready for a provider. Bodies must never include secrets."""

    to_email: str
    to_name: str = ""
    subject: str
    text_body: str
    html_body: str = ""
    event_type: NotificationEventType
    organization_id: str = ""
    recipient_user_id: str = ""
    workflow_run_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailDeliveryResult(BaseModel):
    status: NotificationStatus
    provider: str
    message_id: str = ""
    error_code: str | None = None
    error_message: str | None = None
    latency_seconds: float = 0.0


class NotificationDispatchResult(BaseModel):
    """Safe result returned to API / workflow callers."""

    event_type: NotificationEventType | None = None
    status: NotificationStatus
    provider: str = ""
    recipient_user_id: str = ""
    # Never include raw tokens or passwords in public_message.
    public_message: str = ""
    idempotent_replay: bool = False
    error_code: str | None = None
    event_id: str | None = None


class NotificationEventPayload(BaseModel):
    """Business event input for the notification service."""

    event_type: NotificationEventType
    organization_id: str
    idempotency_key: str
    recipient_user_id: str = ""
    recipient_email: str = ""
    recipient_name: str = ""
    workflow_run_id: str = ""
    # Structured template context — never put secrets here.
    context: dict[str, Any] = Field(default_factory=dict)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
