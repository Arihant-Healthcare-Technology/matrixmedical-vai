"""
Unit tests for rate limiting, 429 handling, correlation IDs, and PII redaction.
Tests for SOW compliance requirements.
"""
import os
import re
import sys
import time
import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_upserter_module(monkeypatch):
    """Helper to get fresh upserter module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upserter",
        str(Path(__file__).parent.parent.parent / "upsert-motus-driver.py")
    )
    upserter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upserter)
    return upserter


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_calls_per_minute(self, monkeypatch):
        """Test initializes with default 60 calls per minute."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter()

        assert limiter.calls_per_minute == 60
        assert limiter.interval == 1.0  # 60/60 = 1 second

    def test_init_custom_calls_per_minute(self, monkeypatch):
        """Test initializes with custom calls per minute."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter(calls_per_minute=120)

        assert limiter.calls_per_minute == 120
        assert limiter.interval == 0.5  # 60/120 = 0.5 seconds

    def test_init_high_rate(self, monkeypatch):
        """Test initializes with high calls per minute."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter(calls_per_minute=600)

        assert limiter.calls_per_minute == 600
        assert limiter.interval == 0.1  # 60/600 = 0.1 seconds

    def test_acquire_first_call_no_wait(self, monkeypatch):
        """Test first call doesn't wait."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter(calls_per_minute=60)

        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 0.1  # First call is instant

    def test_acquire_respects_interval(self, monkeypatch):
        """Test subsequent calls respect rate limit interval."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter(calls_per_minute=600)  # 0.1s interval

        limiter.acquire()
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.09  # Should wait ~0.1s

    def test_acquire_updates_last_call(self, monkeypatch):
        """Test acquire updates last_call timestamp."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter()

        assert limiter.last_call == 0.0
        limiter.acquire()
        assert limiter.last_call > 0

    def test_acquire_multiple_calls_spaced(self, monkeypatch):
        """Test multiple calls are properly spaced."""
        upserter = get_upserter_module(monkeypatch)
        limiter = upserter.RateLimiter(calls_per_minute=1200)  # 0.05s interval

        start = time.time()
        for _ in range(3):
            limiter.acquire()
        elapsed = time.time() - start

        # 3 calls with 0.05s intervals = 2 waits = ~0.1s total
        assert elapsed >= 0.09


class TestHandleRateLimit:
    """Tests for handle_rate_limit function."""

    def test_returns_retry_after_header_value(self, monkeypatch):
        """Test returns Retry-After header value."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "30"}

        result = upserter.handle_rate_limit(mock_resp)
        assert result == 30

    def test_returns_default_without_header(self, monkeypatch):
        """Test returns default 60s without Retry-After header."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.headers = {}

        result = upserter.handle_rate_limit(mock_resp)
        assert result == 60

    def test_returns_default_on_invalid_header(self, monkeypatch):
        """Test returns default on invalid Retry-After value."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "invalid"}

        result = upserter.handle_rate_limit(mock_resp)
        assert result == 60

    def test_handles_large_retry_after(self, monkeypatch):
        """Test handles large Retry-After value."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "300"}

        result = upserter.handle_rate_limit(mock_resp)
        assert result == 300

    def test_handles_small_retry_after(self, monkeypatch):
        """Test handles small Retry-After value."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "1"}

        result = upserter.handle_rate_limit(mock_resp)
        assert result == 1


class TestRateLimitInUpsert:
    """Tests for 429 handling in upsert operations."""

    @pytest.fixture
    def sample_payload(self):
        return {
            "clientEmployeeId1": "12345",
            "programId": 21233,
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com"
        }

    @responses.activate
    def test_retries_on_429_insert(self, monkeypatch, sample_payload):
        """Test retries insert on 429 response."""
        upserter = get_upserter_module(monkeypatch)

        # First GET returns 404 (not found)
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            status=404,
        )
        # First POST returns 429
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            status=429,
            headers={"Retry-After": "1"},
        )
        # Second POST succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"id": "new-id"},
            status=201,
        )

        with patch("time.sleep"):  # Don't actually sleep
            result = upserter.upsert_driver_payload(sample_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_retries_on_429_update(self, monkeypatch, sample_payload):
        """Test retries update on 429 response."""
        upserter = get_upserter_module(monkeypatch)

        # GET returns 200 (exists)
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            json={"id": "existing"},
            status=200,
        )
        # First PUT returns 429
        responses.add(
            responses.PUT,
            re.compile(r".*/drivers/12345.*"),
            status=429,
            headers={"Retry-After": "1"},
        )
        # Second PUT succeeds
        responses.add(
            responses.PUT,
            re.compile(r".*/drivers/12345.*"),
            json={"id": "existing"},
            status=200,
        )

        with patch("time.sleep"):
            result = upserter.upsert_driver_payload(sample_payload)

        assert result["action"] == "update"
        assert result["status"] == 200

    @responses.activate
    def test_429_uses_retry_after_header(self, monkeypatch, sample_payload):
        """Test 429 handling uses Retry-After header."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            status=404,
        )
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            status=429,
            headers={"Retry-After": "5"},
        )
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"id": "new-id"},
            status=201,
        )

        with patch("time.sleep") as mock_sleep:
            upserter.upsert_driver_payload(sample_payload)
            # Verify sleep was called with value from Retry-After header
            mock_sleep.assert_any_call(5)


class TestCorrelationId:
    """Tests for correlation ID functionality."""

    def test_generate_correlation_id_format(self, monkeypatch):
        """Test generates valid UUID format."""
        import uuid
        upserter = get_upserter_module(monkeypatch)

        cid = upserter.generate_correlation_id()

        # Should be valid UUID
        uuid.UUID(cid)  # Raises if invalid
        assert len(cid) == 36  # UUID string length

    def test_generate_unique_ids(self, monkeypatch):
        """Test generates unique IDs."""
        upserter = get_upserter_module(monkeypatch)

        ids = [upserter.generate_correlation_id() for _ in range(100)]

        assert len(set(ids)) == 100  # All unique

    def test_set_and_get_correlation_id(self, monkeypatch):
        """Test set and get correlation ID."""
        upserter = get_upserter_module(monkeypatch)

        upserter.set_correlation_id("test-123")
        assert upserter.get_correlation_id() == "test-123"

    def test_empty_by_default(self, monkeypatch):
        """Test empty by default."""
        upserter = get_upserter_module(monkeypatch)
        upserter._current_correlation_id = ""

        assert upserter.get_correlation_id() == ""

    @responses.activate
    def test_result_includes_correlation_id(self, monkeypatch):
        """Test upsert result includes correlation ID."""
        upserter = get_upserter_module(monkeypatch)

        sample_payload = {
            "clientEmployeeId1": "12345",
            "programId": 21233,
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com"
        }

        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            status=404,
        )
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"id": "new"},
            status=201,
        )

        result = upserter.upsert_driver_payload(
            sample_payload,
            correlation_id="my-cid-123"
        )

        assert result.get("correlation_id") == "my-cid-123"

    @responses.activate
    def test_auto_generates_correlation_id(self, monkeypatch):
        """Test auto-generates correlation ID if not provided."""
        upserter = get_upserter_module(monkeypatch)

        sample_payload = {
            "clientEmployeeId1": "12345",
            "programId": 21233,
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com"
        }

        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            status=404,
        )
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"id": "new"},
            status=201,
        )

        result = upserter.upsert_driver_payload(sample_payload)

        assert "correlation_id" in result
        assert len(result["correlation_id"]) == 36  # UUID length

    def test_log_includes_correlation_id(self, monkeypatch, capsys):
        """Test log includes correlation ID when set."""
        monkeypatch.setenv("DEBUG", "1")
        upserter = get_upserter_module(monkeypatch)

        upserter.set_correlation_id("abc-123")
        upserter._log("Test message")

        captured = capsys.readouterr()
        assert "[abc-123]" in captured.out
        assert "Test message" in captured.out


class TestPiiRedaction:
    """Tests for PII redaction functionality."""

    def test_redact_email_standard(self, monkeypatch):
        """Test redacts standard email."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.redact_email("john.doe@example.com")
        assert result == "jo***@example.com"

    def test_redact_email_short_local(self, monkeypatch):
        """Test handles short local part."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.redact_email("ab@example.com")
        assert result == "***@example.com"

    def test_redact_email_empty(self, monkeypatch):
        """Test handles empty string."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.redact_email("")
        assert result == "***"

    def test_redact_email_no_at_sign(self, monkeypatch):
        """Test handles string without @."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.redact_email("notanemail")
        assert result == "***"

    def test_redact_email_preserves_domain(self, monkeypatch):
        """Test preserves domain."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.redact_email("test@company.org")
        assert "company.org" in result

    def test_redact_log_message_emails(self, monkeypatch):
        """Test _redact_log_message redacts emails."""
        monkeypatch.setenv("REDACT_PII", "1")
        upserter = get_upserter_module(monkeypatch)

        msg = "Processing user john.doe@example.com"
        result = upserter._redact_log_message(msg)

        assert "john.doe@example.com" not in result
        assert "jo***@example.com" in result

    def test_redact_log_message_multiple_emails(self, monkeypatch):
        """Test _redact_log_message redacts multiple emails."""
        monkeypatch.setenv("REDACT_PII", "1")
        upserter = get_upserter_module(monkeypatch)

        msg = "Syncing john@example.com to jane@example.com"
        result = upserter._redact_log_message(msg)

        assert "john@example.com" not in result
        assert "jane@example.com" not in result

    def test_redact_disabled(self, monkeypatch):
        """Test redaction can be disabled via env var."""
        monkeypatch.setenv("REDACT_PII", "0")
        upserter = get_upserter_module(monkeypatch)

        msg = "Processing john.doe@example.com"
        result = upserter._redact_log_message(msg)

        assert "john.doe@example.com" in result  # Not redacted

    def test_log_with_pii_redaction(self, monkeypatch, capsys):
        """Test _log function redacts PII."""
        monkeypatch.setenv("DEBUG", "1")
        monkeypatch.setenv("REDACT_PII", "1")
        upserter = get_upserter_module(monkeypatch)

        upserter._current_correlation_id = ""
        upserter._log("Processing john.doe@example.com")

        captured = capsys.readouterr()
        assert "john.doe@example.com" not in captured.out
        assert "jo***@example.com" in captured.out


class TestGlobalRateLimiter:
    """Tests for global rate limiter instance."""

    def test_global_rate_limiter_exists(self, monkeypatch):
        """Test global rate limiter is created."""
        upserter = get_upserter_module(monkeypatch)

        assert hasattr(upserter, "_rate_limiter")
        assert upserter._rate_limiter is not None

    def test_global_rate_limiter_uses_env_config(self, monkeypatch):
        """Test global rate limiter uses env configuration."""
        monkeypatch.setenv("RATE_LIMIT_CALLS_PER_MINUTE", "120")
        upserter = get_upserter_module(monkeypatch)

        assert upserter._rate_limiter.calls_per_minute == 120

    @responses.activate
    def test_api_calls_use_rate_limiter(self, monkeypatch):
        """Test API calls go through rate limiter."""
        upserter = get_upserter_module(monkeypatch)

        # Mock the rate limiter acquire method
        original_acquire = upserter._rate_limiter.acquire
        acquire_called = []

        def mock_acquire():
            acquire_called.append(True)
            return original_acquire()

        upserter._rate_limiter.acquire = mock_acquire

        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"id": "test"},
            status=200,
        )

        upserter.motus_get_driver("12345")

        assert len(acquire_called) == 1  # Rate limiter was called
