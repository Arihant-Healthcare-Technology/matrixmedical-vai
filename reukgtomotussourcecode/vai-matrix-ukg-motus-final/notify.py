"""
Notification module for batch operation alerts.
Supports SMTP and AWS SES.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = False
    provider: str = "smtp"  # smtp or ses
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = ""
    to_emails: str = ""  # Comma-separated

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.getenv("NOTIFY_ENABLED", "0") == "1",
            provider=os.getenv("NOTIFY_PROVIDER", "smtp"),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_email=os.getenv("NOTIFY_FROM", ""),
            to_emails=os.getenv("NOTIFY_TO", ""),
        )


class NotificationService:
    """Service for sending notifications."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig.from_env()

    def send_batch_summary(self,
                          correlation_id: str,
                          total: int,
                          saved: int,
                          skipped: int,
                          errors: int,
                          duration_seconds: float) -> bool:
        """Send batch completion summary."""
        if not self.config.enabled:
            return False

        success_rate = (saved / total * 100) if total > 0 else 0
        status = "SUCCESS" if errors == 0 else "COMPLETED WITH ERRORS"

        subject = f"[Motus Sync] {status} - {saved}/{total} records"
        body = f"""
Motus Driver Sync Batch Summary
===============================

Correlation ID: {correlation_id}
Status: {status}

Results:
- Total: {total}
- Saved: {saved}
- Skipped: {skipped}
- Errors: {errors}
- Success Rate: {success_rate:.1f}%
- Duration: {duration_seconds:.1f}s

"""
        return self._send_email(subject, body)

    def send_error_alert(self,
                        correlation_id: str,
                        error_message: str,
                        context: Optional[Dict[str, Any]] = None) -> bool:
        """Send error alert."""
        if not self.config.enabled:
            return False

        subject = f"[Motus Sync] ERROR - {error_message[:50]}"
        body = f"""
Motus Driver Sync Error Alert
=============================

Correlation ID: {correlation_id}
Error: {error_message}

Context:
{context or 'N/A'}
"""
        return self._send_email(subject, body)

    def send_warning(self,
                    correlation_id: str,
                    warning_message: str,
                    details: Optional[str] = None) -> bool:
        """Send warning notification."""
        if not self.config.enabled:
            return False

        subject = f"[Motus Sync] WARNING - {warning_message[:50]}"
        body = f"""
Motus Driver Sync Warning
=========================

Correlation ID: {correlation_id}
Warning: {warning_message}

Details:
{details or 'N/A'}
"""
        return self._send_email(subject, body)

    def _send_email(self, subject: str, body: str) -> bool:
        """Send email via configured provider."""
        if self.config.provider == "smtp":
            return self._send_smtp(subject, body)
        elif self.config.provider == "ses":
            return self._send_ses(subject, body)
        return False

    def _send_smtp(self, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.from_email
            msg["To"] = self.config.to_emails
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send SMTP notification: {e}")
            return False

    def _send_ses(self, subject: str, body: str) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
            client = boto3.client("ses")
            client.send_email(
                Source=self.config.from_email,
                Destination={"ToAddresses": self.config.to_emails.split(",")},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}}
                }
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send SES notification: {e}")
            return False


def get_notification_service() -> NotificationService:
    """Get a notification service instance with environment configuration."""
    return NotificationService()
