"""
Notifications Module - SOW Requirement 4.6

Provides email notification capabilities for run summaries and critical alerts.
Supports SMTP, AWS SES, and SendGrid backends.

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

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


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


class Notifier(ABC):
    """Abstract base class for notification providers."""

    def __init__(self, config: NotificationConfig):
        self.config = config

    @abstractmethod
    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """Send an email notification."""
        pass

    def send_run_summary(self, run_context: Dict[str, Any]) -> bool:
        """
        Send a run summary notification.

        Args:
            run_context: Dictionary from RunContext.to_dict()

        Returns:
            True if sent successfully
        """
        if not self.config.enabled:
            logger.debug("Notifications disabled, skipping run summary")
            return False

        project = run_context.get('project', 'Unknown')
        stats = run_context.get('stats', {})
        success_rate = self._calculate_success_rate(stats)

        subject = self._generate_summary_subject(project, stats, success_rate)
        body_html = self._generate_summary_html(run_context, success_rate)
        body_text = self._generate_summary_text(run_context, success_rate)

        return self.send_email(subject, body_html, body_text)

    def send_critical_alert(
        self,
        title: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a critical alert notification.

        Args:
            title: Alert title
            error: The exception that occurred
            context: Additional context information

        Returns:
            True if sent successfully
        """
        if not self.config.enabled:
            logger.debug("Notifications disabled, skipping critical alert")
            return False

        subject = f"[CRITICAL] UKG Integration Alert: {title}"
        body_html = self._generate_alert_html(title, error, context)
        body_text = self._generate_alert_text(title, error, context)

        return self.send_email(subject, body_html, body_text)

    def _calculate_success_rate(self, stats: Dict[str, int]) -> float:
        total = stats.get('total_processed', 0)
        if total == 0:
            return 100.0
        errors = stats.get('errors', 0)
        return ((total - errors) / total) * 100

    def _generate_summary_subject(
        self,
        project: str,
        stats: Dict[str, int],
        success_rate: float
    ) -> str:
        errors = stats.get('errors', 0)
        total = stats.get('total_processed', 0)

        if errors == 0:
            status = "SUCCESS"
        elif success_rate >= 99:
            status = "COMPLETED"
        else:
            status = "COMPLETED WITH ERRORS"

        return f"[{status}] UKG {project.upper()} Sync - {total} processed, {errors} errors"

    def _generate_summary_html(
        self,
        run_context: Dict[str, Any],
        success_rate: float
    ) -> str:
        stats = run_context.get('stats', {})
        errors = run_context.get('errors', [])[:10]  # First 10 errors

        status_color = "#28a745" if success_rate >= 99 else "#ffc107" if success_rate >= 90 else "#dc3545"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: {status_color}; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .stats-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        .stats-table th, .stats-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        .stats-table th {{ background: #f5f5f5; }}
        .error-list {{ background: #fff3cd; padding: 15px; margin-top: 20px; }}
        .footer {{ color: #666; font-size: 12px; padding: 20px; border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>UKG Integration Run Summary</h1>
        <p>Project: {run_context.get('project', 'Unknown').upper()} | Success Rate: {success_rate:.1f}%</p>
    </div>
    <div class="content">
        <h2>Run Details</h2>
        <table class="stats-table">
            <tr><th>Run ID</th><td>{run_context.get('run_id', 'N/A')}</td></tr>
            <tr><th>Correlation ID</th><td>{run_context.get('correlation_id', 'N/A')}</td></tr>
            <tr><th>Company ID</th><td>{run_context.get('company_id', 'N/A')}</td></tr>
            <tr><th>Start Time</th><td>{run_context.get('start_time', 'N/A')}</td></tr>
            <tr><th>End Time</th><td>{run_context.get('end_time', 'N/A')}</td></tr>
            <tr><th>Duration</th><td>{run_context.get('duration_seconds', 0):.2f} seconds</td></tr>
        </table>

        <h2>Statistics</h2>
        <table class="stats-table">
            <tr><th>Total Processed</th><td>{stats.get('total_processed', 0)}</td></tr>
            <tr><th>Created</th><td>{stats.get('created', 0)}</td></tr>
            <tr><th>Updated</th><td>{stats.get('updated', 0)}</td></tr>
            <tr><th>Skipped</th><td>{stats.get('skipped', 0)}</td></tr>
            <tr><th>Errors</th><td style="color: {'#dc3545' if stats.get('errors', 0) > 0 else '#28a745'};">{stats.get('errors', 0)}</td></tr>
        </table>
"""

        if errors:
            html += """
        <div class="error-list">
            <h3>Error Details (First 10)</h3>
            <ul>
"""
            for err in errors:
                html += f"""
                <li>
                    <strong>{err.get('identifier', 'Unknown')}</strong>: {err.get('error', 'Unknown error')}
                    <br><small>{err.get('timestamp', '')}</small>
                </li>
"""
            html += """
            </ul>
        </div>
"""

        html += f"""
    </div>
    <div class="footer">
        <p>This is an automated message from the UKG Integration Suite.</p>
        <p>Generated at {datetime.now().isoformat()}</p>
    </div>
</body>
</html>
"""
        return html

    def _generate_summary_text(
        self,
        run_context: Dict[str, Any],
        success_rate: float
    ) -> str:
        stats = run_context.get('stats', {})
        errors = run_context.get('errors', [])[:10]

        text = f"""
UKG Integration Run Summary
===========================

Project: {run_context.get('project', 'Unknown').upper()}
Success Rate: {success_rate:.1f}%

Run Details:
- Run ID: {run_context.get('run_id', 'N/A')}
- Correlation ID: {run_context.get('correlation_id', 'N/A')}
- Company ID: {run_context.get('company_id', 'N/A')}
- Start Time: {run_context.get('start_time', 'N/A')}
- End Time: {run_context.get('end_time', 'N/A')}
- Duration: {run_context.get('duration_seconds', 0):.2f} seconds

Statistics:
- Total Processed: {stats.get('total_processed', 0)}
- Created: {stats.get('created', 0)}
- Updated: {stats.get('updated', 0)}
- Skipped: {stats.get('skipped', 0)}
- Errors: {stats.get('errors', 0)}
"""

        if errors:
            text += "\nError Details (First 10):\n"
            for err in errors:
                text += f"- {err.get('identifier', 'Unknown')}: {err.get('error', 'Unknown error')}\n"

        text += f"\n---\nGenerated at {datetime.now().isoformat()}\n"
        return text

    def _generate_alert_html(
        self,
        title: str,
        error: Exception,
        context: Optional[Dict[str, Any]]
    ) -> str:
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: #dc3545; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .error-box {{ background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; margin: 15px 0; }}
        .context-box {{ background: #fff3cd; border: 1px solid #ffeeba; padding: 15px; margin: 15px 0; }}
        .footer {{ color: #666; font-size: 12px; padding: 20px; border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CRITICAL ALERT: {title}</h1>
    </div>
    <div class="content">
        <div class="error-box">
            <h3>Error Details</h3>
            <p><strong>Type:</strong> {type(error).__name__}</p>
            <p><strong>Message:</strong> {str(error)}</p>
        </div>
"""

        if context:
            html += """
        <div class="context-box">
            <h3>Context</h3>
            <ul>
"""
            for key, value in context.items():
                html += f"<li><strong>{key}:</strong> {value}</li>\n"
            html += """
            </ul>
        </div>
"""

        html += f"""
        <p><strong>Immediate action may be required.</strong></p>
    </div>
    <div class="footer">
        <p>This is an automated alert from the UKG Integration Suite.</p>
        <p>Generated at {datetime.now().isoformat()}</p>
    </div>
</body>
</html>
"""
        return html

    def _generate_alert_text(
        self,
        title: str,
        error: Exception,
        context: Optional[Dict[str, Any]]
    ) -> str:
        text = f"""
CRITICAL ALERT: {title}
{'=' * (18 + len(title))}

Error Details:
- Type: {type(error).__name__}
- Message: {str(error)}
"""

        if context:
            text += "\nContext:\n"
            for key, value in context.items():
                text += f"- {key}: {value}\n"

        text += f"\nImmediate action may be required.\n\n---\nGenerated at {datetime.now().isoformat()}\n"
        return text


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
            from sendgrid.helpers.mail import Mail, Email, To, Content

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


class NoOpNotifier(Notifier):
    """No-op notifier for testing or when notifications are disabled."""

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        logger.debug(f"NoOpNotifier: Would send email '{subject}' to {recipients}")
        return True


def get_notifier(config: Optional[NotificationConfig] = None) -> Notifier:
    """
    Get the appropriate notifier based on configuration.

    Args:
        config: Optional configuration (defaults to from_env())

    Returns:
        Configured Notifier instance
    """
    config = config or NotificationConfig.from_env()

    if not config.enabled:
        return NoOpNotifier(config)

    provider = config.provider.lower()

    if provider == 'smtp':
        return SMTPNotifier(config)
    elif provider == 'ses':
        return AWSESNotifier(config)
    elif provider == 'sendgrid':
        return SendGridNotifier(config)
    else:
        logger.warning(f"Unknown provider '{provider}', using NoOp notifier")
        return NoOpNotifier(config)
