"""Simulated notification sink. Replaceable later with a real email/API adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.errors import SimulatedServiceError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationService:
    """In-memory notification log with optional injected failures for tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fallback_log: list[dict[str, Any]] = []
        self._fail_remaining = 0
        self.reset()

    def reset(self) -> None:
        self.sent = []
        self.fallback_log = []
        self._fail_remaining = 0

    def fail_next(self, times: int = 1) -> None:
        self._fail_remaining = times

    def send(self, *, employee_id: str, message: str, workflow_id: str) -> dict[str, Any]:
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise SimulatedServiceError("Simulated notification sink is unavailable.")

        record = {
            "employee_id": employee_id,
            "message": message,
            "workflow_id": workflow_id,
            "channel": "simulated_inbox",
            "status": "sent",
            "sent_at": _utc_now(),
            "source": "simulated_notification_service",
        }
        self.sent.append(record)
        return dict(record)

    def log_fallback(self, *, employee_id: str, message: str, workflow_id: str) -> dict[str, Any]:
        record = {
            "employee_id": employee_id,
            "message": message,
            "workflow_id": workflow_id,
            "channel": "log",
            "status": "logged_fallback",
            "sent_at": _utc_now(),
            "source": "fallback_log",
        }
        self.fallback_log.append(record)
        return dict(record)


_SERVICE: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = NotificationService()
    return _SERVICE


def reset_notification_service() -> NotificationService:
    service = get_notification_service()
    service.reset()
    return service
