"""Business notification service — events → templates → email provider.

Agents never call SMTP. Auth/workflow layers emit events here. Delivery failures
never roll back account creation or workflow decisions.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.repositories.notification import NotificationEventRepository
from app.database.session import session_scope
from app.notifications.errors import EmailConfigurationError, EmailProviderError, NotificationError
from app.notifications.factory import get_email_provider
from app.notifications.metrics import record_notification
from app.notifications.models import (
    NotificationDispatchResult,
    NotificationEventPayload,
    NotificationEventType,
    NotificationStatus,
)
from app.notifications.provider import EmailProviderPort
from app.notifications.templates import render_email
from app.services.notifications import get_notification_service

logger = logging.getLogger("worksphere.notifications")

_SUCCESS_STATUSES = {
    NotificationStatus.SENT.value,
    NotificationStatus.GENERATED.value,
}


def _public_message(event_type: NotificationEventType, status: NotificationStatus) -> str:
    if event_type == NotificationEventType.USER_REGISTERED:
        if status == NotificationStatus.SENT:
            return "Welcome email sent."
        if status == NotificationStatus.GENERATED:
            return "Welcome notification generated."
        if status == NotificationStatus.FAILED:
            return "Welcome email could not be delivered."
        return "Account created successfully."
    if event_type == NotificationEventType.USER_INVITED:
        if status == NotificationStatus.SENT:
            return "Invitation email sent."
        if status == NotificationStatus.GENERATED:
            return "Invitation notification generated."
        if status == NotificationStatus.FAILED:
            return "Account created, but the invitation email could not be sent."
        return "Invitation created successfully."
    if status == NotificationStatus.FAILED:
        return "Notification could not be delivered."
    if status == NotificationStatus.GENERATED:
        return "Notification generated."
    if status == NotificationStatus.SENT:
        return "Notification email sent."
    return "Notification skipped."


class BusinessNotificationService:
    """Dispatch typed business notification events via the configured email provider."""

    def __init__(self, provider: EmailProviderPort | None = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> EmailProviderPort:
        return self._provider or get_email_provider()

    def dispatch(
        self,
        payload: NotificationEventPayload,
        *,
        session: Session | None = None,
    ) -> NotificationDispatchResult:
        """Send one notification. Never raises for delivery failures."""

        started = time.perf_counter()
        try:
            if session is not None:
                return self._dispatch_with_session(session, payload, started)
            with session_scope() as db:
                return self._dispatch_with_session(db, payload, started)
        except (DatabaseNotConfiguredError, DatabaseUnavailableError) as exc:
            logger.warning(
                "notification_db_unavailable event=%s error=%s",
                payload.event_type.value,
                type(exc).__name__,
            )
            return self._dispatch_without_persistence(payload, started)
        except Exception as exc:  # noqa: BLE001 — side effect must not break callers
            logger.warning(
                "notification_dispatch_error event=%s error=%s",
                payload.event_type.value,
                type(exc).__name__,
            )
            record_notification(
                provider="none",
                event_type=payload.event_type.value,
                status="failed",
                duration_seconds=time.perf_counter() - started,
            )
            return NotificationDispatchResult(
                event_type=payload.event_type,
                status=NotificationStatus.FAILED,
                public_message=_public_message(payload.event_type, NotificationStatus.FAILED),
                error_code="NOTIFICATION_DISPATCH_ERROR",
            )

    def _dispatch_without_persistence(
        self,
        payload: NotificationEventPayload,
        started: float,
    ) -> NotificationDispatchResult:
        """Fallback path when DB is unavailable — still attempt delivery (no idempotency)."""

        return self._deliver(payload, record=None, session=None, started=started)

    def _dispatch_with_session(
        self,
        session: Session,
        payload: NotificationEventPayload,
        started: float,
    ) -> NotificationDispatchResult:
        repo = NotificationEventRepository(session)
        existing = repo.get_by_idempotency(
            organization_id=payload.organization_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None and existing.status in _SUCCESS_STATUSES:
            return NotificationDispatchResult(
                event_type=payload.event_type,
                status=NotificationStatus(existing.status),
                provider=existing.provider or "",
                recipient_user_id=existing.recipient_user_id or "",
                public_message=_public_message(
                    payload.event_type, NotificationStatus(existing.status)
                ),
                idempotent_replay=True,
                event_id=existing.event_id,
            )

        if existing is None:
            event_id = f"notif-{uuid.uuid4().hex[:16]}"
            record = repo.create(
                event_id=event_id,
                organization_id=payload.organization_id,
                event_type=payload.event_type.value,
                idempotency_key=payload.idempotency_key,
                recipient_user_id=payload.recipient_user_id,
                recipient_email=payload.recipient_email,
                workflow_run_id=payload.workflow_run_id,
                provider="",
                status=NotificationStatus.PENDING.value,
                audit_meta={
                    "event_type": payload.event_type.value,
                    "recipient_user_id": payload.recipient_user_id,
                    "workflow_run_id": payload.workflow_run_id,
                },
            )
        else:
            record = existing

        return self._deliver(payload, record=record, session=session, started=started)

    def _deliver(
        self,
        payload: NotificationEventPayload,
        *,
        record: Any,
        session: Session | None,
        started: float,
    ) -> NotificationDispatchResult:
        if not payload.recipient_email or "@" not in payload.recipient_email:
            record_notification(
                provider="none",
                event_type=payload.event_type.value,
                status="skipped",
                duration_seconds=time.perf_counter() - started,
            )
            if record is not None and session is not None:
                NotificationEventRepository(session).mark_failure(
                    record,
                    provider="none",
                    error_code="NO_RECIPIENT_EMAIL",
                    error_message="Recipient has no email address.",
                )
            return NotificationDispatchResult(
                event_type=payload.event_type,
                status=NotificationStatus.SKIPPED,
                recipient_user_id=payload.recipient_user_id,
                public_message=_public_message(payload.event_type, NotificationStatus.SKIPPED),
                error_code="NO_RECIPIENT_EMAIL",
                event_id=getattr(record, "event_id", None),
            )

        email = render_email(
            event_type=payload.event_type,
            to_email=payload.recipient_email,
            to_name=payload.recipient_name,
            organization_id=payload.organization_id,
            recipient_user_id=payload.recipient_user_id,
            workflow_run_id=payload.workflow_run_id,
            context=payload.context,
        )

        provider = self.provider
        try:
            delivery = provider.send(email)
        except (EmailConfigurationError, EmailProviderError, NotificationError) as exc:
            latency = time.perf_counter() - started
            record_notification(
                provider=getattr(provider, "name", "none"),
                event_type=payload.event_type.value,
                status="failed",
                duration_seconds=latency,
            )
            if record is not None and session is not None:
                NotificationEventRepository(session).mark_failure(
                    record,
                    provider=getattr(provider, "name", "none"),
                    error_code=exc.error_code,
                    error_message=str(exc),
                )
            logger.warning(
                "notification_failed event=%s provider=%s code=%s org=%s",
                payload.event_type.value,
                getattr(provider, "name", "none"),
                exc.error_code,
                payload.organization_id,
            )
            return NotificationDispatchResult(
                event_type=payload.event_type,
                status=NotificationStatus.FAILED,
                provider=getattr(provider, "name", ""),
                recipient_user_id=payload.recipient_user_id,
                public_message=_public_message(payload.event_type, NotificationStatus.FAILED),
                error_code=exc.error_code,
                event_id=getattr(record, "event_id", None),
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.perf_counter() - started
            record_notification(
                provider=getattr(provider, "name", "none"),
                event_type=payload.event_type.value,
                status="failed",
                duration_seconds=latency,
            )
            if record is not None and session is not None:
                NotificationEventRepository(session).mark_failure(
                    record,
                    provider=getattr(provider, "name", "none"),
                    error_code="EMAIL_SEND_FAILED",
                    error_message=type(exc).__name__,
                )
            return NotificationDispatchResult(
                event_type=payload.event_type,
                status=NotificationStatus.FAILED,
                provider=getattr(provider, "name", ""),
                recipient_user_id=payload.recipient_user_id,
                public_message=_public_message(payload.event_type, NotificationStatus.FAILED),
                error_code="EMAIL_SEND_FAILED",
                event_id=getattr(record, "event_id", None),
            )

        # Mirror into existing NotificationServicePort sink for tests/tools visibility.
        try:
            get_notification_service().send(
                employee_id=payload.recipient_user_id or payload.recipient_email,
                message=f"{payload.event_type.value}: {email.subject}",
                workflow_id=payload.workflow_run_id or payload.idempotency_key,
                organization_id=payload.organization_id,
                channel="email",
                idempotency_key=payload.idempotency_key,
            )
        except Exception:  # noqa: BLE001
            pass

        if record is not None and session is not None:
            NotificationEventRepository(session).mark_success(
                record,
                provider=delivery.provider,
                status=delivery.status.value,
                audit_meta={
                    "provider": delivery.provider,
                    "status": delivery.status.value,
                    "message_id": delivery.message_id,
                },
            )

        latency = time.perf_counter() - started
        record_notification(
            provider=delivery.provider,
            event_type=payload.event_type.value,
            status=delivery.status.value,
            duration_seconds=delivery.latency_seconds or latency,
        )
        logger.info(
            "notification_ok event=%s provider=%s status=%s org=%s recipient_user=%s",
            payload.event_type.value,
            delivery.provider,
            delivery.status.value,
            payload.organization_id,
            payload.recipient_user_id or "-",
        )
        return NotificationDispatchResult(
            event_type=payload.event_type,
            status=delivery.status,
            provider=delivery.provider,
            recipient_user_id=payload.recipient_user_id,
            public_message=_public_message(payload.event_type, delivery.status),
            event_id=getattr(record, "event_id", None),
        )


_SERVICE: BusinessNotificationService | None = None


def get_business_notification_service() -> BusinessNotificationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = BusinessNotificationService()
    return _SERVICE


def reset_business_notification_service(
    service: BusinessNotificationService | None = None,
) -> BusinessNotificationService:
    global _SERVICE
    from app.notifications.factory import reset_email_provider
    from app.notifications.metrics import reset_notification_metrics

    reset_email_provider()
    reset_notification_metrics()
    _SERVICE = service if service is not None else BusinessNotificationService()
    return _SERVICE


def frontend_url(path: str) -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def role_label(role: str) -> str:
    mapping = {
        "admin": "Administrator",
        "employee": "Employee",
        "manager": "Manager",
        "hr": "HR",
    }
    return mapping.get((role or "").lower(), role or "")


def workflow_type_label(workflow_type: str) -> str:
    mapping = {
        "leave_attendance": "leave request",
        "recruitment": "recruitment request",
        "onboarding": "onboarding request",
        "attendance": "attendance request",
        "performance": "performance request",
        "training": "training request",
        "offboarding": "offboarding request",
        "hr_services": "HR services request",
    }
    return mapping.get(workflow_type or "", workflow_type or "workflow")
