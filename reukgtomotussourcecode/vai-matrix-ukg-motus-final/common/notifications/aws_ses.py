"""
AWS SES email notifier.

Provides AWS Simple Email Service-based notification delivery.
"""

import logging
from typing import List, Optional

from .base import Notifier
from .config import NotificationConfig

logger = logging.getLogger(__name__)


class AWSESNotifier(Notifier):
    """AWS SES-based email notifier."""

    def __init__(self, config: NotificationConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('ses', region_name=self.config.aws_region)
            except ImportError:
                raise ImportError("boto3 required for AWS SES. Install with: pip install boto3")
        return self._client

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        recipients = recipients or self.config.recipients
        if not recipients:
            logger.warning("No recipients configured for notification")
            return False

        try:
            client = self._get_client()
            response = client.send_email(
                Source=f"{self.config.sender_name} <{self.config.sender_email}>",
                Destination={'ToAddresses': recipients},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Text': {'Data': body_text},
                        'Html': {'Data': body_html}
                    }
                }
            )
            logger.info(f"Email sent via SES: {response['MessageId']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False
