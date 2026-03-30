"""
Abstract base notifier class.

Provides the base interface and template generation for notification providers.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import NotificationConfig

logger = logging.getLogger(__name__)


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
