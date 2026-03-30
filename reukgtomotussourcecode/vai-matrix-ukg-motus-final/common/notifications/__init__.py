"""
Notifications Module - SOW Requirement 4.6

Provides email notification capabilities for run summaries and critical alerts.
Supports SMTP, AWS SES, and SendGrid backends.

This package is split into focused modules:
- config: NotificationConfig dataclass
- base: Abstract Notifier base class
- smtp: SMTPNotifier implementation
- aws_ses: AWSESNotifier implementation
- sendgrid: SendGridNotifier implementation
- noop: NoOpNotifier for testing
- factory: get_notifier factory function

Usage:
    from common.notifications import get_notifier, NotificationConfig

    # Configure notifier
    config = NotificationConfig.from_env()
    notifier = get_notifier(config)

    # Send run summary
    notifier.send_run_summary(run_context)

    # Send critical alert
    notifier.send_critical_alert("Token refresh failed", exception, context)
"""

from .aws_ses import AWSESNotifier
from .base import Notifier
from .config import NotificationConfig
from .factory import get_notifier
from .noop import NoOpNotifier
from .sendgrid import SendGridNotifier
from .smtp import SMTPNotifier

__all__ = [
    "NotificationConfig",
    "Notifier",
    "SMTPNotifier",
    "AWSESNotifier",
    "SendGridNotifier",
    "NoOpNotifier",
    "get_notifier",
]
