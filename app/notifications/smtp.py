"""Real SMTP email provider. Credentials come from settings only."""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage as StdEmailMessage

from app.notifications.errors import EmailConfigurationError, EmailProviderError
from app.notifications.models import (
    EmailDeliveryResult,
    EmailMessage,
    NotificationStatus,
)

logger = logging.getLogger("worksphere.notifications.smtp")


class SmtpEmailProvider:
    """Deliver mail via SMTP using configured host/credentials."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str = "WorkSphere AI",
        use_tls: bool = True,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._host = (host or "").strip()
        self._port = int(port)
        self._username = (username or "").strip()
        self._password = password or ""
        self._from_email = (from_email or "").strip()
        self._from_name = (from_name or "WorkSphere AI").strip()
        self._use_tls = bool(use_tls)
        self._timeout = float(timeout_seconds)
        self._validate_config()

    def _validate_config(self) -> None:
        missing: list[str] = []
        if not self._host:
            missing.append("SMTP_HOST")
        if not self._port:
            missing.append("SMTP_PORT")
        if not self._from_email:
            missing.append("SMTP_FROM_EMAIL")
        if missing:
            raise EmailConfigurationError(
                "SMTP configuration incomplete: " + ", ".join(missing) + ".",
                error_code="EMAIL_CONFIG_INVALID",
            )

    @property
    def name(self) -> str:
        return "smtp"

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        started = time.perf_counter()
        message_id = f"smtp-{uuid.uuid4().hex[:12]}"
        envelope = StdEmailMessage()
        envelope["Subject"] = message.subject
        envelope["From"] = f"{self._from_name} <{self._from_email}>"
        envelope["To"] = (
            f"{message.to_name} <{message.to_email}>"
            if message.to_name
            else message.to_email
        )
        envelope["Message-ID"] = f"<{message_id}@worksphere>"
        envelope.set_content(message.text_body)
        if message.html_body:
            envelope.add_alternative(message.html_body, subtype="html")

        try:
            if self._use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(
                    self._host, self._port, timeout=self._timeout
                ) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    if self._username:
                        server.login(self._username, self._password)
                    server.send_message(envelope)
            else:
                with smtplib.SMTP(
                    self._host, self._port, timeout=self._timeout
                ) as server:
                    if self._username:
                        server.login(self._username, self._password)
                    server.send_message(envelope)
        except smtplib.SMTPAuthenticationError as exc:
            logger.warning(
                "SMTP auth failed event=%s recipient=%s code=EMAIL_AUTH_FAILED",
                message.event_type.value,
                message.to_email,
            )
            raise EmailProviderError(
                "SMTP authentication failed.",
                error_code="EMAIL_AUTH_FAILED",
            ) from exc
        except (smtplib.SMTPConnectError, ConnectionError, TimeoutError, OSError) as exc:
            logger.warning(
                "SMTP connection failed event=%s recipient=%s code=EMAIL_CONNECTION_FAILED",
                message.event_type.value,
                message.to_email,
            )
            raise EmailProviderError(
                "Could not connect to the SMTP server.",
                error_code="EMAIL_CONNECTION_FAILED",
            ) from exc
        except smtplib.SMTPException as exc:
            logger.warning(
                "SMTP delivery failed event=%s recipient=%s code=EMAIL_SEND_FAILED",
                message.event_type.value,
                message.to_email,
            )
            raise EmailProviderError(
                "SMTP delivery failed.",
                error_code="EMAIL_SEND_FAILED",
            ) from exc

        latency = time.perf_counter() - started
        logger.info(
            "EMAIL_SMTP event=%s recipient=%s subject=%s status=sent latency=%.3fs",
            message.event_type.value,
            message.to_email,
            message.subject,
            latency,
        )
        return EmailDeliveryResult(
            status=NotificationStatus.SENT,
            provider=self.name,
            message_id=message_id,
            latency_seconds=latency,
        )
