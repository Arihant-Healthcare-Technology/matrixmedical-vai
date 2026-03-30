"""
SMTP email notifier.

Provides SMTP-based email notification delivery.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from .base import Notifier

logger = logging.getLogger(__name__)


class SMTPNotifier(Notifier):
    """SMTP-based email notifier."""

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
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config.sender_name} <{self.config.sender_email}>"
            msg['To'] = ', '.join(recipients)

            msg.attach(MIMEText(body_text, 'plain'))
            msg.attach(MIMEText(body_html, 'html'))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.sender_email,
                    recipients,
                    msg.as_string()
                )

            logger.info(f"Email sent successfully to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
