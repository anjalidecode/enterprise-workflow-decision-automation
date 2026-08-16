"""WorkSphere AI notification / email delivery package.

Business events flow through BusinessNotificationService → EmailProviderPort.
Agents continue to use NotificationServicePort / notify_* tools and never call SMTP.
"""

from app.notifications.factory import build_email_provider, get_email_provider, reset_email_provider
from app.notifications.models import (
    NotificationDispatchResult,
    NotificationEventType,
    NotificationStatus,
)
from app.notifications.service import (
    BusinessNotificationService,
    get_business_notification_service,
    reset_business_notification_service,
)

__all__ = [
    "BusinessNotificationService",
    "NotificationDispatchResult",
    "NotificationEventType",
    "NotificationStatus",
    "build_email_provider",
    "get_business_notification_service",
    "get_email_provider",
    "reset_business_notification_service",
    "reset_email_provider",
]
