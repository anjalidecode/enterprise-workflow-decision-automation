"""Development console email provider — no real SMTP, safe structured output."""

from __future__ import annotations

import logging
import time
import uuid

from app.notifications.models import (
    EmailDeliveryResult,
    EmailMessage,
    NotificationStatus,
)

logger = logging.getLogger("worksphere.notifications.console")


class ConsoleEmailProvider:
    """Renders notification delivery for local development without SMTP credentials."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    @property
    def name(self) -> str:
        return "console"

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        started = time.perf_counter()
        message_id = f"console-{uuid.uuid4().hex[:12]}"
        self.sent.append(message)
        # Safe fields only — never passwords, JWTs, SMTP secrets, or raw invite tokens.
        safe_meta = {
            k: v
            for k, v in (message.metadata or {}).items()
            if k
            not in {
                "password",
                "token",
                "activation_token",
                "invite_token",
                "jwt",
                "api_key",
            }
        }
        logger.info(
            "EMAIL_CONSOLE event=%s recipient=%s subject=%s provider=console "
            "status=generated workflow=%s org=%s user=%s meta=%s",
            message.event_type.value,
            message.to_email,
            message.subject,
            message.workflow_run_id or "-",
            message.organization_id or "-",
            message.recipient_user_id or "-",
            safe_meta,
        )
        print(
            "\n".join(
                [
                    "========== WorkSphere AI Email (console) ==========",
                    f"event:      {message.event_type.value}",
                    f"recipient:  {message.to_email}",
                    f"name:       {message.to_name or '-'}",
                    f"subject:    {message.subject}",
                    f"provider:   console",
                    f"status:     generated",
                    f"workflow:   {message.workflow_run_id or '-'}",
                    f"org:        {message.organization_id or '-'}",
                    f"user_id:    {message.recipient_user_id or '-'}",
                    "----- text body -----",
                    message.text_body,
                    "==================================================",
                ]
            ),
            flush=True,
        )
        latency = time.perf_counter() - started
        return EmailDeliveryResult(
            status=NotificationStatus.GENERATED,
            provider=self.name,
            message_id=message_id,
            latency_seconds=latency,
        )
