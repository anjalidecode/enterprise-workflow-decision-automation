"""Notification / email provider errors. Never crash callers; wrap and record."""

from __future__ import annotations


class NotificationError(Exception):
    """Base notification failure."""

    def __init__(self, message: str, *, error_code: str = "NOTIFICATION_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


class EmailProviderError(NotificationError):
    """Provider-level delivery failure (SMTP/console)."""

    def __init__(self, message: str, *, error_code: str = "EMAIL_PROVIDER_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class EmailConfigurationError(NotificationError):
    """Invalid or incomplete email configuration."""

    def __init__(self, message: str, *, error_code: str = "EMAIL_CONFIG_INVALID") -> None:
        super().__init__(message, error_code=error_code)
