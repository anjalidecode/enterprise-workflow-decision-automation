"""Email provider port — application depends on this, not on SMTP directly."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.notifications.models import EmailDeliveryResult, EmailMessage


@runtime_checkable
class EmailProviderPort(Protocol):
    """Deliver a rendered email. Implementations: console (dev) or SMTP (prod)."""

    @property
    def name(self) -> str: ...

    def send(self, message: EmailMessage) -> EmailDeliveryResult: ...
