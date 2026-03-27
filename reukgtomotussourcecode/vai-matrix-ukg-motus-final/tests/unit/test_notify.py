"""
Unit tests for notification module.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from notify import NotificationConfig, NotificationService, get_notification_service


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NotificationConfig()

        assert config.enabled is False
        assert config.provider == "smtp"
        assert config.smtp_host == ""
        assert config.smtp_port == 587
        assert config.smtp_user == ""
        assert config.smtp_password == ""
        assert config.from_email == ""
        assert config.to_emails == ""

    def test_custom_values(self):
        """Test custom configuration values."""
        config = NotificationConfig(
            enabled=True,
            provider="ses",
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_user="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails="to@example.com",
        )

        assert config.enabled is True
        assert config.provider == "ses"
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465

    def test_from_env_disabled_by_default(self, monkeypatch):
        """Test disabled by default when loading from env."""
        monkeypatch.delenv("NOTIFY_ENABLED", raising=False)

        config = NotificationConfig.from_env()

        assert config.enabled is False

    def test_from_env_enabled(self, monkeypatch):
        """Test enabled from environment."""
        monkeypatch.setenv("NOTIFY_ENABLED", "1")
        monkeypatch.setenv("NOTIFY_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USER", "testuser")
        monkeypatch.setenv("SMTP_PASSWORD", "testpass")
        monkeypatch.setenv("NOTIFY_FROM", "from@example.com")
        monkeypatch.setenv("NOTIFY_TO", "to@example.com")

        config = NotificationConfig.from_env()

        assert config.enabled is True
        assert config.provider == "smtp"
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.smtp_user == "testuser"
        assert config.smtp_password == "testpass"
        assert config.from_email == "from@example.com"
        assert config.to_emails == "to@example.com"

    def test_from_env_ses_provider(self, monkeypatch):
        """Test SES provider configuration."""
        monkeypatch.setenv("NOTIFY_ENABLED", "1")
        monkeypatch.setenv("NOTIFY_PROVIDER", "ses")

        config = NotificationConfig.from_env()

        assert config.provider == "ses"


class TestNotificationService:
    """Tests for NotificationService."""

    def test_init_with_default_config(self, monkeypatch):
        """Test initializes with default config."""
        monkeypatch.delenv("NOTIFY_ENABLED", raising=False)

        service = NotificationService()

        assert service.config.enabled is False

    def test_init_with_custom_config(self):
        """Test initializes with custom config."""
        config = NotificationConfig(enabled=True, provider="smtp")
        service = NotificationService(config)

        assert service.config.enabled is True
        assert service.config.provider == "smtp"

    def test_send_batch_summary_disabled(self):
        """Test returns False when disabled."""
        config = NotificationConfig(enabled=False)
        service = NotificationService(config)

        result = service.send_batch_summary(
            correlation_id="test-123",
            total=100,
            saved=95,
            skipped=3,
            errors=2,
            duration_seconds=10.5
        )

        assert result is False

    @patch.object(NotificationService, "_send_email")
    def test_send_batch_summary_enabled(self, mock_send):
        """Test sends email when enabled."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        result = service.send_batch_summary(
            correlation_id="test-123",
            total=100,
            saved=95,
            skipped=3,
            errors=2,
            duration_seconds=10.5
        )

        assert result is True
        mock_send.assert_called_once()

    @patch.object(NotificationService, "_send_email")
    def test_send_batch_summary_content(self, mock_send):
        """Test batch summary contains expected content."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_batch_summary(
            correlation_id="test-123",
            total=100,
            saved=95,
            skipped=3,
            errors=2,
            duration_seconds=10.5
        )

        call_args = mock_send.call_args[0]
        subject, body = call_args[0], call_args[1]

        assert "test-123" in body
        assert "100" in body
        assert "95" in body
        assert "COMPLETED WITH ERRORS" in subject  # has errors

    @patch.object(NotificationService, "_send_email")
    def test_send_batch_summary_success_status(self, mock_send):
        """Test batch summary shows SUCCESS when no errors."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_batch_summary(
            correlation_id="test-123",
            total=100,
            saved=100,
            skipped=0,
            errors=0,
            duration_seconds=10.5
        )

        call_args = mock_send.call_args[0]
        subject = call_args[0]

        assert "SUCCESS" in subject

    def test_send_error_alert_disabled(self):
        """Test send_error_alert returns False when disabled."""
        config = NotificationConfig(enabled=False)
        service = NotificationService(config)

        result = service.send_error_alert(
            correlation_id="test-123",
            error_message="Test error occurred",
            context={"employee": "12345"}
        )

        assert result is False

    @patch.object(NotificationService, "_send_email")
    def test_send_error_alert_enabled(self, mock_send):
        """Test sends error alert when enabled."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        result = service.send_error_alert(
            correlation_id="test-123",
            error_message="Test error occurred",
            context={"employee": "12345"}
        )

        assert result is True
        call_args = mock_send.call_args[0]
        assert "ERROR" in call_args[0]  # Subject

    @patch.object(NotificationService, "_send_email")
    def test_send_error_alert_content(self, mock_send):
        """Test error alert contains expected content."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_error_alert(
            correlation_id="error-cid-456",
            error_message="Connection timeout",
            context={"employee": "12345", "attempt": 3}
        )

        call_args = mock_send.call_args[0]
        body = call_args[1]

        assert "error-cid-456" in body
        assert "Connection timeout" in body

    def test_send_warning_disabled(self):
        """Test send_warning returns False when disabled."""
        config = NotificationConfig(enabled=False)
        service = NotificationService(config)

        result = service.send_warning(
            correlation_id="test-123",
            warning_message="High error rate detected"
        )

        assert result is False

    @patch.object(NotificationService, "_send_email")
    def test_send_warning_enabled(self, mock_send):
        """Test sends warning when enabled."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        result = service.send_warning(
            correlation_id="test-123",
            warning_message="High error rate detected",
            details="50% of records failed"
        )

        assert result is True
        call_args = mock_send.call_args[0]
        assert "WARNING" in call_args[0]

    @patch("smtplib.SMTP")
    def test_send_smtp_success(self, mock_smtp):
        """Test SMTP send success."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        config = NotificationConfig(
            enabled=True,
            provider="smtp",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails="to@example.com"
        )
        service = NotificationService(config)

        result = service._send_smtp("Test Subject", "Test Body")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_smtp_without_auth(self, mock_smtp):
        """Test SMTP send without authentication."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        config = NotificationConfig(
            enabled=True,
            provider="smtp",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="",  # No auth
            smtp_password="",
            from_email="from@example.com",
            to_emails="to@example.com"
        )
        service = NotificationService(config)

        result = service._send_smtp("Test Subject", "Test Body")

        assert result is True
        mock_server.login.assert_not_called()  # No login when no credentials

    @patch("smtplib.SMTP")
    def test_send_smtp_failure(self, mock_smtp):
        """Test SMTP send failure."""
        mock_smtp.return_value.__enter__.side_effect = Exception("Connection failed")

        config = NotificationConfig(enabled=True, provider="smtp")
        service = NotificationService(config)

        result = service._send_smtp("Test Subject", "Test Body")

        assert result is False

    def test_send_ses_not_configured(self):
        """Test SES without boto3 fails gracefully."""
        config = NotificationConfig(enabled=True, provider="ses")
        service = NotificationService(config)

        # Should not raise, just return False if boto3 not available
        result = service._send_ses("Test", "Body")
        # Result depends on boto3 availability - may be True or False

    def test_send_email_unknown_provider(self):
        """Test unknown provider returns False."""
        config = NotificationConfig(enabled=True, provider="unknown")
        service = NotificationService(config)

        result = service._send_email("Subject", "Body")

        assert result is False


class TestGetNotificationService:
    """Tests for get_notification_service function."""

    def test_returns_service_instance(self, monkeypatch):
        """Test returns NotificationService instance."""
        monkeypatch.delenv("NOTIFY_ENABLED", raising=False)

        service = get_notification_service()

        assert isinstance(service, NotificationService)

    def test_uses_env_config(self, monkeypatch):
        """Test uses environment configuration."""
        monkeypatch.setenv("NOTIFY_ENABLED", "1")
        monkeypatch.setenv("NOTIFY_PROVIDER", "ses")

        service = get_notification_service()

        assert service.config.enabled is True
        assert service.config.provider == "ses"


class TestBatchSummaryEdgeCases:
    """Tests for edge cases in batch summary."""

    @patch.object(NotificationService, "_send_email")
    def test_zero_total(self, mock_send):
        """Test handles zero total records."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_batch_summary(
            correlation_id="test",
            total=0,
            saved=0,
            skipped=0,
            errors=0,
            duration_seconds=0.1
        )

        call_args = mock_send.call_args[0]
        body = call_args[1]
        assert "0" in body

    @patch.object(NotificationService, "_send_email")
    def test_all_errors(self, mock_send):
        """Test handles all records erroring."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_batch_summary(
            correlation_id="test",
            total=100,
            saved=0,
            skipped=0,
            errors=100,
            duration_seconds=60.0
        )

        call_args = mock_send.call_args[0]
        subject = call_args[0]
        assert "COMPLETED WITH ERRORS" in subject

    @patch.object(NotificationService, "_send_email")
    def test_long_duration(self, mock_send):
        """Test handles long duration."""
        mock_send.return_value = True
        config = NotificationConfig(enabled=True)
        service = NotificationService(config)

        service.send_batch_summary(
            correlation_id="test",
            total=10000,
            saved=9999,
            skipped=1,
            errors=0,
            duration_seconds=3600.5
        )

        call_args = mock_send.call_args[0]
        body = call_args[1]
        assert "3600.5" in body
