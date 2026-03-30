"""
SendGrid email notifier.

Provides SendGrid-based email notification delivery.
"""

import logging
from typing import List, Optional

from .base import Notifier

logger = logging.getLogger(__name__)


class SendGridNotifier(Notifier):
    """SendGrid-based email notifier."""

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
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Content, Email, Mail, To

            message = Mail(
                from_email=Email(self.config.sender_email, self.config.sender_name),
                to_emails=[To(r) for r in recipients],
                subject=subject
            )
            message.add_content(Content("text/plain", body_text))
            message.add_content(Content("text/html", body_html))

            sg = SendGridAPIClient(self.config.sendgrid_api_key)
            response = sg.send(message)

            logger.info(f"Email sent via SendGrid: {response.status_code}")
            return response.status_code in (200, 202)

        except ImportError:
            raise ImportError("sendgrid required. Install with: pip install sendgrid")
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {e}")
            return False
