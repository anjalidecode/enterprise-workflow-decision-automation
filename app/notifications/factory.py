"""Factory for email providers from application settings."""

from __future__ import annotations

from app.config.settings import Settings, get_settings
from app.notifications.console import ConsoleEmailProvider
from app.notifications.errors import EmailConfigurationError
from app.notifications.provider import EmailProviderPort
from app.notifications.smtp import SmtpEmailProvider

_PROVIDER: EmailProviderPort | None = None


def build_email_provider(settings: Settings | None = None) -> EmailProviderPort:
    cfg = settings or get_settings()
    provider_key = (cfg.email_provider or "console").strip().lower()
    if provider_key in {"", "console", "development", "dev"}:
        return ConsoleEmailProvider()
    if provider_key == "smtp":
        return SmtpEmailProvider(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            username=cfg.smtp_username,
            password=cfg.smtp_password,
            from_email=cfg.smtp_from_email,
            from_name=cfg.smtp_from_name,
            use_tls=cfg.smtp_use_tls,
            timeout_seconds=cfg.smtp_timeout_seconds,
        )
    raise EmailConfigurationError(
        f"Unknown EMAIL_PROVIDER '{cfg.email_provider}'. Use 'console' or 'smtp'.",
        error_code="EMAIL_CONFIG_INVALID",
    )


def get_email_provider() -> EmailProviderPort:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = build_email_provider()
    return _PROVIDER


def reset_email_provider(provider: EmailProviderPort | None = None) -> EmailProviderPort:
    """Reset process-wide provider (tests). Optional explicit provider for fakes."""

    global _PROVIDER
    _PROVIDER = provider if provider is not None else build_email_provider()
    return _PROVIDER
