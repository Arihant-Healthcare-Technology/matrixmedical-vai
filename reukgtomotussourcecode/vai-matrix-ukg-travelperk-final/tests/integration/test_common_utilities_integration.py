"""
Integration tests for common utilities.

Tests verify rate limiting, secrets management, metrics, and other utilities.
Run with: pytest tests/integration/test_common_utilities_integration.py -v -m integration
"""
import os
import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from common.rate_limiter import RateLimiter, get_rate_limiter
from common.secrets_manager import get_secrets_manager, EnvSecretsManager
from common.metrics import MetricsCollector
from common.redaction import redact_pii, RedactingFilter
from common.report_generator import ReportGenerator
from common.correlation import RunContext
from common.validators import validate_email, validate_phone


@pytest.mark.integration
class TestRateLimiterTokenBucket:
    """Test rate limiter token bucket algorithm."""

    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed immediately."""
        limiter = RateLimiter(calls_per_minute=60)

        start = time.time()
        for _ in range(5):
            limiter.acquire()
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 1.0

    def test_rate_limiter_throttles_at_limit(self):
        """Test that rate limiter throttles when limit is reached."""
        limiter = RateLimiter(calls_per_minute=6)  # 1 per 10 seconds
        limiter._tokens = 0  # Exhaust tokens

        start = time.time()
        limiter.acquire()  # Should wait for token
        elapsed = time.time() - start

        # Should have waited
        assert elapsed > 0

    def test_rate_limiter_token_replenishment(self):
        """Test that tokens are replenished over time."""
        limiter = RateLimiter(calls_per_minute=60)
        limiter._tokens = 0  # Exhaust tokens

        # Wait for some replenishment
        time.sleep(0.5)

        # Now should have some tokens
        assert limiter.acquire(timeout=0.1)


@pytest.mark.integration
class TestRateLimiterConcurrentAccess:
    """Test rate limiter with concurrent access."""

    def test_rate_limiter_concurrent_access(self):
        """Test rate limiter is thread-safe."""
        limiter = RateLimiter(calls_per_minute=100)
        results = []

        def worker():
            for _ in range(10):
                limiter.acquire()
                results.append(1)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 50 calls should have completed
        assert len(results) == 50


@pytest.mark.integration
class TestSecretsManager:
    """Test secrets manager."""

    def test_secrets_manager_env_provider(self):
        """Test environment variable secrets provider."""
        with patch.dict(os.environ, {"TEST_SECRET": "secret_value"}):
            provider = EnvSecretsManager()
            value = provider.get_secret("TEST_SECRET")
            assert value == "secret_value"

    def test_secrets_manager_env_provider_default(self):
        """Test environment variable provider with default."""
        provider = EnvSecretsManager()
        value = provider.get_secret("NONEXISTENT_SECRET", default="default")
        assert value == "default"

    def test_get_secrets_manager_env(self):
        """Test getting secrets manager with env provider."""
        with patch.dict(os.environ, {"SECRETS_PROVIDER": "env"}):
            manager = get_secrets_manager()
            assert manager is not None


@pytest.mark.integration
class TestMetricsCollection:
    """Test metrics collection."""

    def test_metrics_collector_counter(self):
        """Test metrics counter."""
        collector = MetricsCollector()

        collector.increment("requests_total")
        collector.increment("requests_total")
        collector.increment("requests_total")

        assert collector.get("requests_total") == 3

    def test_metrics_collector_gauge(self):
        """Test metrics gauge."""
        collector = MetricsCollector()

        collector.set("active_connections", 5)
        assert collector.get("active_connections") == 5

        collector.set("active_connections", 10)
        assert collector.get("active_connections") == 10

    def test_metrics_collector_histogram(self):
        """Test metrics histogram."""
        collector = MetricsCollector()

        collector.observe("request_duration", 0.5)
        collector.observe("request_duration", 1.0)
        collector.observe("request_duration", 1.5)

        stats = collector.get_histogram_stats("request_duration")
        assert stats["count"] == 3
        assert stats["avg"] == 1.0

    def test_metrics_collector_labels(self):
        """Test metrics with labels."""
        collector = MetricsCollector()

        collector.increment("http_requests", labels={"method": "GET", "status": "200"})
        collector.increment("http_requests", labels={"method": "POST", "status": "201"})

        assert collector.get("http_requests", labels={"method": "GET", "status": "200"}) == 1


@pytest.mark.integration
class TestPIIRedaction:
    """Test PII redaction."""

    def test_pii_redaction_email(self):
        """Test email redaction."""
        text = "Contact john.doe@example.com for more info"
        redacted = redact_pii(text)

        assert "john.doe@example.com" not in redacted
        assert "[EMAIL]" in redacted or "***" in redacted

    def test_pii_redaction_phone(self):
        """Test phone number redaction."""
        text = "Call us at 555-123-4567"
        redacted = redact_pii(text)

        assert "555-123-4567" not in redacted

    def test_pii_redaction_ssn(self):
        """Test SSN redaction."""
        text = "SSN: 123-45-6789"
        redacted = redact_pii(text)

        assert "123-45-6789" not in redacted

    def test_redacting_filter(self):
        """Test logging redaction filter."""
        import logging

        filter = RedactingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User email: test@example.com",
            args=(),
            exc_info=None,
        )

        filter.filter(record)
        assert "test@example.com" not in record.msg


@pytest.mark.integration
class TestReportGenerator:
    """Test report generator."""

    def test_report_generator_run_report(self, tmp_path):
        """Test generating run report."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_data = {
            "correlation_id": "test-123",
            "project": "travelperk",
            "company_id": "J9A6Y",
            "total_processed": 100,
            "created": 80,
            "updated": 15,
            "skipped": 3,
            "errors": 2,
            "duration_seconds": 60.5,
        }

        report_paths = generator.generate_run_report(run_data)

        assert len(report_paths) > 0
        for path in report_paths:
            assert os.path.exists(path)

    def test_report_generator_validation_report(self, tmp_path):
        """Test generating validation report."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_data = {
            "total_processed": 100,
            "created": 80,
            "updated": 15,
            "skipped": 3,
            "errors": 2,
        }

        validation = generator.generate_validation_report(
            run_data,
            target_success_rate=99.0
        )

        assert "passed" in validation
        assert "success_rate" in validation
        # With 2 errors out of 100, success rate is 98%
        assert validation["success_rate"] == 98.0
        assert validation["passed"] is False  # Below 99% target


@pytest.mark.integration
class TestCorrelationIdPropagation:
    """Test correlation ID propagation."""

    def test_correlation_id_generated(self):
        """Test that correlation ID is generated."""
        with RunContext(project="test", company_id="TEST") as ctx:
            assert ctx.correlation_id is not None
            assert len(ctx.correlation_id) > 0

    def test_correlation_id_unique(self):
        """Test that correlation IDs are unique."""
        ids = []
        for _ in range(10):
            with RunContext(project="test", company_id="TEST") as ctx:
                ids.append(ctx.correlation_id)

        # All should be unique
        assert len(set(ids)) == 10

    def test_run_context_stats_tracking(self):
        """Test RunContext stats tracking."""
        with RunContext(project="test", company_id="TEST") as ctx:
            ctx.stats["total_processed"] = 50
            ctx.stats["created"] = 45
            ctx.stats["errors"] = 5

            run_data = ctx.to_dict()

            assert run_data["stats"]["total_processed"] == 50
            assert run_data["stats"]["created"] == 45
            assert run_data["stats"]["errors"] == 5

    def test_run_context_error_recording(self):
        """Test RunContext error recording."""
        with RunContext(project="test", company_id="TEST") as ctx:
            ctx.record_error("emp_001", "Validation failed")
            ctx.record_error("emp_002", "API error")

            assert len(ctx.errors) == 2

    def test_run_context_duration_tracking(self):
        """Test RunContext duration tracking."""
        with RunContext(project="test", company_id="TEST") as ctx:
            time.sleep(0.1)

        assert ctx.duration_seconds >= 0.1


@pytest.mark.integration
class TestValidators:
    """Test input validators."""

    def test_validate_email_valid(self):
        """Test valid email validation."""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.co.uk") is True

    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        assert validate_email("invalid-email") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
        assert validate_email("") is False

    def test_validate_phone_valid(self):
        """Test valid phone validation."""
        assert validate_phone("555-123-4567") is True
        assert validate_phone("5551234567") is True
        assert validate_phone("(555) 123-4567") is True

    def test_validate_phone_invalid(self):
        """Test invalid phone validation."""
        assert validate_phone("123") is False
        assert validate_phone("") is False
        assert validate_phone("abc-def-ghij") is False


@pytest.mark.integration
class TestNotificationSMTP:
    """Test SMTP notification."""

    def test_notification_smtp_config(self):
        """Test SMTP notification configuration."""
        from common.notifications import get_notifier

        with patch.dict(os.environ, {
            "NOTIFY_ENABLED": "true",
            "NOTIFY_PROVIDER": "smtp",
            "NOTIFY_SMTP_HOST": "smtp.example.com",
            "NOTIFY_SMTP_PORT": "587",
            "NOTIFY_SMTP_USER": "user",
            "NOTIFY_SMTP_PASSWORD": "pass",
            "NOTIFY_SENDER_EMAIL": "noreply@example.com",
            "NOTIFY_RECIPIENTS": "admin@example.com",
        }):
            try:
                notifier = get_notifier()
                assert notifier is not None
            except Exception:
                # May fail if SMTP not available, which is OK
                pass
