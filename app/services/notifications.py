"""Notification service port + in-memory implementation.

Later adapters (email, SMS, in-app, webhook) can implement NotificationServicePort
without changing ToolExecutor or agents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError
from app.tools.idempotency import build_idempotency_key


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryNotificationService:
    """Development notification sink with optional injected failures for tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fallback_log: list[dict[str, Any]] = []
        self._sent_keys: dict[str, dict[str, Any]] = {}
        self._fail_remaining = 0
        self.reset()

    def reset(self) -> None:
        self.sent = []
        self.fallback_log = []
        self._sent_keys = {}
        self._fail_remaining = 0

    def fail_next(self, times: int = 1) -> None:
        self._fail_remaining = times

    def send(
        self,
        *,
        employee_id: str,
        message: str,
        workflow_id: str,
        organization_id: str = "",
        channel: str = "simulated_inbox",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key or build_idempotency_key(
            capability="notification.send",
            workflow_id=workflow_id,
            organization_id=organization_id,
            employee_id=employee_id,
            channel=channel,
            message_hash=str(hash(message)),
        )
        if key in self._sent_keys:
            replay = dict(self._sent_keys[key])
            replay["idempotent_replay"] = True
            return replay

        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise SimulatedServiceError("Simulated notification sink is unavailable.")

        record = {
            "employee_id": employee_id,
            "message": message,
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "channel": channel,
            "status": "sent",
            "sent_at": _utc_now(),
            "source": "simulated_notification_service",
            "idempotent_replay": False,
        }
        self.sent.append(record)
        self._sent_keys[key] = dict(record)
        return dict(record)

    def log_fallback(
        self,
        *,
        employee_id: str,
        message: str,
        workflow_id: str,
        organization_id: str = "",
    ) -> dict[str, Any]:
        record = {
            "employee_id": employee_id,
            "message": message,
            "workflow_id": workflow_id,
            "organization_id": organization_id,
            "channel": "log",
            "status": "logged_fallback",
            "sent_at": _utc_now(),
            "source": "fallback_log",
        }
        self.fallback_log.append(record)
        return dict(record)


# Backward-compatible alias used by existing imports and tests.
NotificationService = InMemoryNotificationService

_SERVICE: InMemoryNotificationService | None = None


def get_notification_service() -> InMemoryNotificationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = InMemoryNotificationService()
    return _SERVICE


def reset_notification_service() -> InMemoryNotificationService:
    service = get_notification_service()
    service.reset()
    return service
