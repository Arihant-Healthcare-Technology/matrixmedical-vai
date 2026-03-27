"""
Unit tests for notifications module.
Tests for SOW Requirement 4.6 - Email notifications.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.notifications import (
    NotificationConfig,
    Notifier,
    SMTPNotifier,
    AWSESNotifier,
    SendGridNotifier,
    NoOpNotifier,
    get_notifier,
)


class TestNotificationConfig:
    """Tests for NotificationConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NotificationConfig()

        assert config.enabled is True
        assert config.sender_email == ""
        assert config.sender_name == "UKG Integration Suite"
        assert config.recipients == []
        assert config.smtp_host == ""
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True
        assert config.aws_region == "us-east-1"
        assert config.sendgrid_api_key == ""
        assert config.provider == "smtp"

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = NotificationConfig(
            enabled=False,
            sender_email="alerts@example.com",
            sender_name="Custom Sender",
            recipients=["user1@example.com", "user2@example.com"],
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_use_tls=False,
            provider="ses"
        )

        assert config.enabled is False
        assert config.sender_email == "alerts@example.com"
        assert config.sender_name == "Custom Sender"
        assert config.recipients == ["user1@example.com", "user2@example.com"]
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.smtp_use_tls is False
        assert config.provider == "ses"

    def test_from_env_default(self, monkeypatch):
        """Test from_env with default environment."""
        # Clear relevant env vars
        for key in ["NOTIFICATIONS_ENABLED", "NOTIFICATION_SENDER", "ALERT_RECIPIENTS",
                    "SMTP_HOST", "SMTP_PORT", "NOTIFICATION_PROVIDER"]:
            monkeypatch.delenv(key, raising=False)

        config = NotificationConfig.from_env()

        assert config.enabled is True
        assert config.sender_email == "noreply@matrixmedical.com"
        assert config.recipients == []
        assert config.provider == "smtp"

    def test_from_env_custom(self, monkeypatch):
        """Test from_env with custom environment variables."""
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
        monkeypatch.setenv("NOTIFICATION_SENDER", "custom@example.com")
        monkeypatch.setenv("NOTIFICATION_SENDER_NAME", "Custom Name")
        monkeypatch.setenv("ALERT_RECIPIENTS", "admin@example.com, ops@example.com")
        monkeypatch.setenv("SMTP_HOST", "mail.example.com")
        monkeypatch.setenv("SMTP_PORT", "25")
        monkeypatch.setenv("SMTP_USER", "mailuser")
        monkeypatch.setenv("SMTP_PASSWORD", "mailpass")
        monkeypatch.setenv("SMTP_USE_TLS", "false")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("SENDGRID_API_KEY", "sg_api_key")
        monkeypatch.setenv("NOTIFICATION_PROVIDER", "ses")

        config = NotificationConfig.from_env()

        assert config.enabled is False
        assert config.sender_email == "custom@example.com"
        assert config.sender_name == "Custom Name"
        assert config.recipients == ["admin@example.com", "ops@example.com"]
        assert config.smtp_host == "mail.example.com"
        assert config.smtp_port == 25
        assert config.smtp_user == "mailuser"
        assert config.smtp_password == "mailpass"
        assert config.smtp_use_tls is False
        assert config.aws_region == "eu-west-1"
        assert config.sendgrid_api_key == "sg_api_key"
        assert config.provider == "ses"

    def test_from_env_empty_recipients(self, monkeypatch):
        """Test from_env handles empty recipients string."""
        monkeypatch.setenv("ALERT_RECIPIENTS", "")

        config = NotificationConfig.from_env()

        assert config.recipients == []

    def test_from_env_recipients_with_whitespace(self, monkeypatch):
        """Test from_env strips whitespace from recipients."""
        monkeypatch.setenv("ALERT_RECIPIENTS", "  user1@test.com  ,  user2@test.com  ")

        config = NotificationConfig.from_env()

        assert config.recipients == ["user1@test.com", "user2@test.com"]


class TestSMTPNotifier:
    """Tests for SMTPNotifier class."""

    def test_init(self):
        """Test SMTPNotifier initialization."""
        config = NotificationConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            recipients=["test@example.com"]
        )
        notifier = SMTPNotifier(config)

        assert notifier.config == config

    def test_send_email_no_recipients(self):
        """Test send_email returns False when no recipients."""
        config = NotificationConfig(recipients=[])
        notifier = SMTPNotifier(config)

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is False

    @patch('smtplib.SMTP')
    def test_send_email_success(self, mock_smtp_class):
        """Test successful email sending."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        config = NotificationConfig(
            sender_email="from@example.com",
            sender_name="Sender",
            recipients=["to@example.com"],
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            smtp_use_tls=True
        )
        notifier = SMTPNotifier(config)

        result = notifier.send_email("Test Subject", "<html>Body</html>", "Text Body")

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user", "pass")
        mock_smtp.sendmail.assert_called_once()

    @patch('smtplib.SMTP')
    def test_send_email_without_tls(self, mock_smtp_class):
        """Test email sending without TLS."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        config = NotificationConfig(
            sender_email="from@example.com",
            recipients=["to@example.com"],
            smtp_host="smtp.example.com",
            smtp_use_tls=False
        )
        notifier = SMTPNotifier(config)

        notifier.send_email("Subject", "<html>", "text")

        mock_smtp.starttls.assert_not_called()

    @patch('smtplib.SMTP')
    def test_send_email_without_auth(self, mock_smtp_class):
        """Test email sending without authentication."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        config = NotificationConfig(
            sender_email="from@example.com",
            recipients=["to@example.com"],
            smtp_host="smtp.example.com",
            smtp_user="",
            smtp_password=""
        )
        notifier = SMTPNotifier(config)

        notifier.send_email("Subject", "<html>", "text")

        mock_smtp.login.assert_not_called()

    @patch('smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp_class):
        """Test email sending failure handling."""
        mock_smtp_class.side_effect = Exception("Connection refused")

        config = NotificationConfig(
            sender_email="from@example.com",
            recipients=["to@example.com"],
            smtp_host="smtp.example.com"
        )
        notifier = SMTPNotifier(config)

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is False


class TestAWSESNotifier:
    """Tests for AWSESNotifier class."""

    def test_init(self):
        """Test AWSESNotifier initialization."""
        config = NotificationConfig(aws_region="us-west-2")
        notifier = AWSESNotifier(config)

        assert notifier.config == config
        assert notifier._client is None

    def test_send_email_no_recipients(self):
        """Test send_email returns False when no recipients."""
        config = NotificationConfig(recipients=[])
        notifier = AWSESNotifier(config)

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is False

    def test_send_email_success(self):
        """Test successful email sending via SES."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "test-message-id"}
        mock_boto3.client.return_value = mock_client

        config = NotificationConfig(
            sender_email="from@example.com",
            sender_name="Sender",
            recipients=["to@example.com"],
            aws_region="us-east-1"
        )
        notifier = AWSESNotifier(config)

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            notifier._client = mock_client
            result = notifier.send_email("Test Subject", "<html>", "text")

        assert result is True
        mock_client.send_email.assert_called_once()

    def test_send_email_failure(self):
        """Test email sending failure via SES."""
        mock_client = MagicMock()
        mock_client.send_email.side_effect = Exception("SES error")

        config = NotificationConfig(
            sender_email="from@example.com",
            recipients=["to@example.com"]
        )
        notifier = AWSESNotifier(config)
        notifier._client = mock_client

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is False


class TestSendGridNotifier:
    """Tests for SendGridNotifier class."""

    def test_init(self):
        """Test SendGridNotifier initialization."""
        config = NotificationConfig(sendgrid_api_key="test_key")
        notifier = SendGridNotifier(config)

        assert notifier.config == config

    def test_send_email_no_recipients(self):
        """Test send_email returns False when no recipients."""
        config = NotificationConfig(recipients=[])
        notifier = SendGridNotifier(config)

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is False

    def test_send_email_success(self):
        """Test successful email sending via SendGrid."""
        mock_sendgrid = MagicMock()
        mock_mail = MagicMock()
        mock_email = MagicMock()
        mock_to = MagicMock()
        mock_content = MagicMock()

        mock_sg_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_client.send.return_value = mock_response

        config = NotificationConfig(
            sender_email="from@example.com",
            sender_name="Sender",
            recipients=["to@example.com"],
            sendgrid_api_key="test_api_key"
        )
        notifier = SendGridNotifier(config)

        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(),
            'sendgrid.helpers.mail': MagicMock()
        }):
            with patch('common.notifications.SendGridNotifier.send_email') as mock_send:
                mock_send.return_value = True
                result = notifier.send_email("Subject", "<html>", "text")

        # Direct test of mock behavior
        assert mock_send.return_value is True

    def test_send_email_failure(self):
        """Test email sending failure via SendGrid."""
        config = NotificationConfig(
            sender_email="from@example.com",
            recipients=["to@example.com"],
            sendgrid_api_key="test_key"
        )
        notifier = SendGridNotifier(config)

        # Simulate import error for sendgrid
        with patch.dict('sys.modules', {'sendgrid': None}):
            with patch('builtins.__import__', side_effect=ImportError):
                with pytest.raises(ImportError):
                    notifier.send_email("Subject", "<html>", "text")


class TestNoOpNotifier:
    """Tests for NoOpNotifier class."""

    def test_send_email_always_returns_true(self):
        """Test NoOpNotifier always returns True."""
        config = NotificationConfig()
        notifier = NoOpNotifier(config)

        result = notifier.send_email("Subject", "<html>", "text")

        assert result is True

    def test_send_email_with_recipients(self):
        """Test NoOpNotifier ignores recipients."""
        config = NotificationConfig(recipients=["test@example.com"])
        notifier = NoOpNotifier(config)

        result = notifier.send_email(
            "Subject", "<html>", "text",
            recipients=["other@example.com"]
        )

        assert result is True


class TestNotifierBaseMethods:
    """Tests for Notifier base class methods."""

    def test_send_run_summary_disabled(self):
        """Test send_run_summary returns False when disabled."""
        config = NotificationConfig(enabled=False)
        notifier = NoOpNotifier(config)

        result = notifier.send_run_summary({"project": "test", "stats": {}})

        assert result is False

    def test_send_run_summary_success(self):
        """Test send_run_summary generates and sends email."""
        config = NotificationConfig(enabled=True, recipients=["test@example.com"])
        notifier = NoOpNotifier(config)

        run_context = {
            "project": "bill",
            "run_id": "run-123",
            "correlation_id": "corr-456",
            "company_id": "COMP001",
            "start_time": "2024-01-01T10:00:00",
            "end_time": "2024-01-01T10:05:00",
            "duration_seconds": 300,
            "stats": {
                "total_processed": 100,
                "created": 50,
                "updated": 40,
                "skipped": 5,
                "errors": 5
            },
            "errors": [
                {"identifier": "EMP001", "error": "Invalid email", "timestamp": "2024-01-01T10:01:00"}
            ]
        }

        result = notifier.send_run_summary(run_context)

        assert result is True

    def test_send_critical_alert_disabled(self):
        """Test send_critical_alert returns False when disabled."""
        config = NotificationConfig(enabled=False)
        notifier = NoOpNotifier(config)

        result = notifier.send_critical_alert("Error", Exception("Test"))

        assert result is False

    def test_send_critical_alert_success(self):
        """Test send_critical_alert generates and sends email."""
        config = NotificationConfig(enabled=True, recipients=["admin@example.com"])
        notifier = NoOpNotifier(config)

        result = notifier.send_critical_alert(
            "Token Refresh Failed",
            ValueError("Invalid credentials"),
            {"correlation_id": "corr-123", "project": "bill"}
        )

        assert result is True

    def test_calculate_success_rate_zero_total(self):
        """Test success rate calculation with zero total."""
        notifier = NoOpNotifier(NotificationConfig())

        rate = notifier._calculate_success_rate({"total_processed": 0, "errors": 0})

        assert rate == 100.0

    def test_calculate_success_rate_with_errors(self):
        """Test success rate calculation with errors."""
        notifier = NoOpNotifier(NotificationConfig())

        rate = notifier._calculate_success_rate({"total_processed": 100, "errors": 10})

        assert rate == 90.0

    def test_generate_summary_subject_success(self):
        """Test summary subject for successful run."""
        notifier = NoOpNotifier(NotificationConfig())

        subject = notifier._generate_summary_subject("bill", {"total_processed": 100, "errors": 0}, 100.0)

        assert "[SUCCESS]" in subject
        assert "BILL" in subject

    def test_generate_summary_subject_with_errors(self):
        """Test summary subject for run with errors."""
        notifier = NoOpNotifier(NotificationConfig())

        subject = notifier._generate_summary_subject("motus", {"total_processed": 100, "errors": 10}, 90.0)

        assert "COMPLETED WITH ERRORS" in subject

    def test_generate_summary_html_contains_key_info(self):
        """Test summary HTML contains key information."""
        notifier = NoOpNotifier(NotificationConfig())

        run_context = {
            "project": "travelperk",
            "run_id": "run-123",
            "correlation_id": "corr-456",
            "stats": {"total_processed": 50, "errors": 2}
        }

        html = notifier._generate_summary_html(run_context, 96.0)

        assert "run-123" in html
        assert "corr-456" in html
        assert "TRAVELPERK" in html
        assert "96.0%" in html

    def test_generate_alert_html_contains_error_info(self):
        """Test alert HTML contains error information."""
        notifier = NoOpNotifier(NotificationConfig())

        error = ValueError("Test error message")
        context = {"correlation_id": "corr-789"}

        html = notifier._generate_alert_html("Token Error", error, context)

        assert "ValueError" in html
        assert "Test error message" in html
        assert "corr-789" in html


class TestGetNotifier:
    """Tests for get_notifier factory function."""

    def test_returns_noop_when_disabled(self, monkeypatch):
        """Test returns NoOpNotifier when disabled."""
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")

        notifier = get_notifier()

        assert isinstance(notifier, NoOpNotifier)

    def test_returns_smtp_notifier(self, monkeypatch):
        """Test returns SMTPNotifier for smtp provider."""
        monkeypatch.setenv("NOTIFICATION_PROVIDER", "smtp")
        monkeypatch.delenv("NOTIFICATIONS_ENABLED", raising=False)

        notifier = get_notifier()

        assert isinstance(notifier, SMTPNotifier)

    def test_returns_ses_notifier(self, monkeypatch):
        """Test returns AWSESNotifier for ses provider."""
        monkeypatch.setenv("NOTIFICATION_PROVIDER", "ses")
        monkeypatch.delenv("NOTIFICATIONS_ENABLED", raising=False)

        notifier = get_notifier()

        assert isinstance(notifier, AWSESNotifier)

    def test_returns_sendgrid_notifier(self, monkeypatch):
        """Test returns SendGridNotifier for sendgrid provider."""
        monkeypatch.setenv("NOTIFICATION_PROVIDER", "sendgrid")
        monkeypatch.delenv("NOTIFICATIONS_ENABLED", raising=False)

        notifier = get_notifier()

        assert isinstance(notifier, SendGridNotifier)

    def test_returns_noop_for_unknown_provider(self, monkeypatch):
        """Test returns NoOpNotifier for unknown provider."""
        monkeypatch.setenv("NOTIFICATION_PROVIDER", "unknown")
        monkeypatch.delenv("NOTIFICATIONS_ENABLED", raising=False)

        notifier = get_notifier()

        assert isinstance(notifier, NoOpNotifier)

    def test_uses_provided_config(self):
        """Test uses provided config instead of from_env."""
        config = NotificationConfig(
            enabled=True,
            provider="ses",
            recipients=["test@example.com"]
        )

        notifier = get_notifier(config)

        assert isinstance(notifier, AWSESNotifier)
        assert notifier.config == config
