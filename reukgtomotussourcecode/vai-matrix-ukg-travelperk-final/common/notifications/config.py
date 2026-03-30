"""
Notification configuration.

Provides NotificationConfig dataclass for configuring notification providers.
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class NotificationConfig:
    """Configuration for notification system."""

    # General settings
    enabled: bool = True
    sender_email: str = ""
    sender_name: str = "UKG Integration Suite"
    recipients: List[str] = field(default_factory=list)

    # SMTP settings
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # AWS SES settings
    aws_region: str = "us-east-1"

    # SendGrid settings
    sendgrid_api_key: str = ""

    # Provider selection
    provider: str = "smtp"  # 'smtp', 'ses', 'sendgrid'

    @classmethod
    def from_env(cls) -> 'NotificationConfig':
        """Create configuration from environment variables."""
        recipients_str = os.environ.get('ALERT_RECIPIENTS', '')
        recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]

        return cls(
            enabled=os.environ.get('NOTIFICATIONS_ENABLED', 'true').lower() == 'true',
            sender_email=os.environ.get('NOTIFICATION_SENDER', 'noreply@matrixmedical.com'),
            sender_name=os.environ.get('NOTIFICATION_SENDER_NAME', 'UKG Integration Suite'),
            recipients=recipients,
            smtp_host=os.environ.get('SMTP_HOST', ''),
            smtp_port=int(os.environ.get('SMTP_PORT', '587')),
            smtp_user=os.environ.get('SMTP_USER', ''),
            smtp_password=os.environ.get('SMTP_PASSWORD', ''),
            smtp_use_tls=os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
            aws_region=os.environ.get('AWS_REGION', 'us-east-1'),
            sendgrid_api_key=os.environ.get('SENDGRID_API_KEY', ''),
            provider=os.environ.get('NOTIFICATION_PROVIDER', 'smtp'),
        )
