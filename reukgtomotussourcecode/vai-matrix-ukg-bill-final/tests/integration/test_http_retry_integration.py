"""
Integration tests for HTTP retry and error handling.

Tests verify retry logic, rate limiting, and error recovery behavior.
Run with: pytest tests/integration/test_http_retry_integration.py -v -m integration
"""
import time
from unittest.mock import patch, MagicMock

import pytest
import responses
import requests

from src.infrastructure.http.client import HttpClient
from src.infrastructure.http.retry import RetryConfig, with_retry


@pytest.mark.integration
class TestRetryOnTimeout:
    """Test retry behavior on timeout errors."""

    @responses.activate
    def test_retry_on_timeout_success(self):
        """Test that request retries and succeeds after timeout."""
        call_count = [0]

        def request_callback(request):
            call_count[0] += 1
            if call_count[0] < 2:
                raise requests.exceptions.Timeout("Connection timed out")
            return (200, {}, '{"success": true}')

        responses.add_callback(
            responses.GET,
            "https://api.example.com/test",
            callback=request_callback,
            content_type="application/json",
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        result = client.get("/test")

        assert result["success"] is True
        assert call_count[0] == 2

    @responses.activate
    def test_retry_on_timeout_max_retries_exceeded(self):
        """Test that max retries exceeded raises exception."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            body=requests.exceptions.Timeout("Connection timed out"),
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            body=requests.exceptions.Timeout("Connection timed out"),
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=2,
        )

        with pytest.raises(requests.exceptions.Timeout):
            client.get("/test")


@pytest.mark.integration
class TestRetryOn5xx:
    """Test retry behavior on 5xx server errors."""

    @responses.activate
    def test_retry_on_500_success(self):
        """Test retry and success after 500 error."""
        # First request returns 500
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Internal Server Error"},
            status=500,
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        result = client.get("/test")

        assert result["success"] is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_retry_on_502_bad_gateway(self):
        """Test retry on 502 Bad Gateway."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Bad Gateway"},
            status=502,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        result = client.get("/test")
        assert result["success"] is True

    @responses.activate
    def test_retry_on_503_service_unavailable(self):
        """Test retry on 503 Service Unavailable."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Service Unavailable"},
            status=503,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        result = client.get("/test")
        assert result["success"] is True

    @responses.activate
    def test_no_retry_on_4xx_client_errors(self):
        """Test that 4xx errors are not retried (except 429)."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Bad Request"},
            status=400,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        with pytest.raises(Exception):
            client.get("/test")

        # Only one call should be made
        assert len(responses.calls) == 1


@pytest.mark.integration
class TestRateLimiting429:
    """Test rate limiting with 429 responses."""

    @responses.activate
    def test_rate_limit_429_with_retry_after(self):
        """Test handling 429 with Retry-After header."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Too Many Requests"},
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
        )

        start_time = time.time()
        result = client.get("/test")
        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed >= 1.0  # Should have waited at least 1 second

    @responses.activate
    def test_rate_limit_429_without_retry_after(self):
        """Test handling 429 without Retry-After header (default wait)."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Too Many Requests"},
            status=429,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            default_retry_wait=0.5,  # 500ms default wait
        )

        result = client.get("/test")
        assert result["success"] is True
        assert len(responses.calls) == 2


@pytest.mark.integration
class TestExponentialBackoff:
    """Test exponential backoff behavior."""

    @responses.activate
    def test_exponential_backoff_timing(self):
        """Test that backoff increases exponentially."""
        # All requests fail with 500
        for _ in range(4):
            responses.add(
                responses.GET,
                "https://api.example.com/test",
                json={"error": "Server Error"},
                status=500,
            )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            backoff_factor=0.1,  # Fast for testing
        )

        with pytest.raises(Exception):
            client.get("/test")

        # Should have made 4 calls (initial + 3 retries)
        assert len(responses.calls) == 4

    @responses.activate
    def test_exponential_backoff_success_on_last_retry(self):
        """Test success on the last retry attempt."""
        # First 3 fail, last one succeeds
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://api.example.com/test",
                json={"error": "Server Error"},
                status=500,
            )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            backoff_factor=0.01,  # Fast for testing
        )

        result = client.get("/test")
        assert result["success"] is True
        assert len(responses.calls) == 4


@pytest.mark.integration
class TestMaxRetriesExceeded:
    """Test behavior when max retries is exceeded."""

    @responses.activate
    def test_max_retries_exceeded_raises_original_error(self):
        """Test that original error is raised after max retries."""
        for _ in range(5):
            responses.add(
                responses.GET,
                "https://api.example.com/test",
                json={"error": "Server Error", "code": "SERVER_ERROR"},
                status=500,
            )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            backoff_factor=0.01,
        )

        with pytest.raises(Exception) as exc_info:
            client.get("/test")

        # Should include error information
        assert "500" in str(exc_info.value) or "Server" in str(exc_info.value)


@pytest.mark.integration
class TestRetryConfiguration:
    """Test retry configuration options."""

    def test_retry_config_defaults(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.backoff_factor > 0

    def test_retry_config_custom(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            backoff_factor=0.5,
            retry_on_status=[500, 502, 503, 504],
        )

        assert config.max_retries == 5
        assert config.backoff_factor == 0.5
        assert 500 in config.retry_on_status

    @responses.activate
    def test_retry_on_specific_status_codes(self):
        """Test retry only on specific status codes."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"error": "Gateway Timeout"},
            status=504,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            retry_on_status=[504],  # Only retry on 504
            backoff_factor=0.01,
        )

        result = client.get("/test")
        assert result["success"] is True


@pytest.mark.integration
class TestConnectionErrors:
    """Test handling of connection errors."""

    @responses.activate
    def test_retry_on_connection_error(self):
        """Test retry on connection error."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"success": True},
            status=200,
        )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            max_retries=3,
            backoff_factor=0.01,
        )

        result = client.get("/test")
        assert result["success"] is True


@pytest.mark.integration
class TestConcurrentRequests:
    """Test concurrent request handling."""

    @responses.activate
    def test_concurrent_rate_limiting(self):
        """Test that rate limiter works with concurrent requests."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Add multiple responses
        for i in range(10):
            responses.add(
                responses.GET,
                f"https://api.example.com/item/{i}",
                json={"id": i},
                status=200,
            )

        client = HttpClient(
            base_url="https://api.example.com",
            timeout=5.0,
            rate_limit_per_second=10,
        )

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(client.get, f"/item/{i}")
                for i in range(10)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        assert len(results) == 10
        assert all(r is not None for r in results)
