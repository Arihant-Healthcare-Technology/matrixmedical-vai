"""
Unit tests for HTTP client infrastructure.

Tests the extracted HTTP utilities (retry, response handling, clients).
"""

import pytest
import responses
from unittest.mock import MagicMock, patch

from src.domain.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from src.infrastructure.http.retry import ExponentialBackoff, backoff_sleep
from src.infrastructure.http.response import (
    ResponseHandler,
    extract_error_message,
    safe_json,
)
from src.infrastructure.http.client import BillHttpClient, HttpClient, UKGHttpClient


class TestExponentialBackoff:
    """Tests for ExponentialBackoff retry strategy."""

    def test_should_retry_within_limit(self):
        """Should return True when attempt is within max_retries."""
        strategy = ExponentialBackoff(max_retries=3)
        assert strategy.should_retry(0) is True
        assert strategy.should_retry(1) is True
        assert strategy.should_retry(2) is True

    def test_should_not_retry_at_limit(self):
        """Should return False when attempt equals max_retries."""
        strategy = ExponentialBackoff(max_retries=3)
        assert strategy.should_retry(3) is False
        assert strategy.should_retry(4) is False

    def test_get_delay_exponential(self):
        """Should calculate exponential delay."""
        strategy = ExponentialBackoff(
            base_delay=1.0,
            factor=2.0,
            jitter=0,  # Disable jitter for predictable test
            max_delay=100.0,
        )
        assert strategy.get_delay(0) == 1.0  # 1 * 2^0 = 1
        assert strategy.get_delay(1) == 2.0  # 1 * 2^1 = 2
        assert strategy.get_delay(2) == 4.0  # 1 * 2^2 = 4
        assert strategy.get_delay(3) == 8.0  # 1 * 2^3 = 8

    def test_get_delay_respects_max(self):
        """Should cap delay at max_delay."""
        strategy = ExponentialBackoff(
            base_delay=1.0,
            factor=2.0,
            jitter=0,
            max_delay=5.0,
        )
        assert strategy.get_delay(10) == 5.0

    def test_is_retryable_status_5xx(self):
        """Should identify 5xx as retryable."""
        strategy = ExponentialBackoff()
        assert strategy.is_retryable_status(500) is True
        assert strategy.is_retryable_status(502) is True
        assert strategy.is_retryable_status(503) is True
        assert strategy.is_retryable_status(504) is True

    def test_is_retryable_status_429(self):
        """Should identify 429 as retryable."""
        strategy = ExponentialBackoff()
        assert strategy.is_retryable_status(429) is True

    def test_is_not_retryable_4xx(self):
        """Should not retry 4xx errors (except 429)."""
        strategy = ExponentialBackoff()
        assert strategy.is_retryable_status(400) is False
        assert strategy.is_retryable_status(401) is False
        assert strategy.is_retryable_status(403) is False
        assert strategy.is_retryable_status(404) is False

    @patch("time.sleep")
    def test_sleep_calls_time_sleep(self, mock_sleep):
        """Should call time.sleep with calculated delay."""
        strategy = ExponentialBackoff(base_delay=1.0, factor=2.0, jitter=0)
        strategy.sleep(2)
        mock_sleep.assert_called_once_with(4.0)


class TestBackoffSleep:
    """Tests for legacy backoff_sleep function."""

    @patch("time.sleep")
    def test_backoff_sleep_default_factor(self, mock_sleep):
        """Should use default factor of 2.0."""
        backoff_sleep(2)
        mock_sleep.assert_called_once_with(4.0)  # 2^2

    @patch("time.sleep")
    def test_backoff_sleep_custom_factor(self, mock_sleep):
        """Should use custom factor."""
        backoff_sleep(2, factor=3.0)
        mock_sleep.assert_called_once_with(9.0)  # 3^2


class TestSafeJson:
    """Tests for safe_json function."""

    def test_valid_json(self):
        """Should parse valid JSON."""
        response = MagicMock()
        response.json.return_value = {"key": "value"}
        result = safe_json(response)
        assert result == {"key": "value"}

    def test_invalid_json(self):
        """Should return fallback for invalid JSON."""
        response = MagicMock()
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "Not JSON content"
        result = safe_json(response)
        assert "_raw_text" in result
        assert result["_raw_text"] == "Not JSON content"

    def test_truncates_long_text(self):
        """Should truncate long text in fallback."""
        response = MagicMock()
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "x" * 1000
        result = safe_json(response)
        assert len(result["_raw_text"]) == 500


class TestExtractErrorMessage:
    """Tests for extract_error_message function."""

    def test_message_key(self):
        """Should extract message from 'message' key."""
        assert extract_error_message({"message": "Error occurred"}) == "Error occurred"

    def test_nested_error(self):
        """Should extract from nested error object."""
        body = {"error": {"message": "Nested error"}}
        assert extract_error_message(body) == "Nested error"

    def test_errors_array(self):
        """Should extract from errors array."""
        body = {"errors": [{"message": "First error"}]}
        assert extract_error_message(body) == "First error"

    def test_detail_key(self):
        """Should extract from 'detail' key (FastAPI format)."""
        assert extract_error_message({"detail": "Detail message"}) == "Detail message"

    def test_fallback_to_json(self):
        """Should fallback to JSON string."""
        body = {"unknown_key": "value"}
        result = extract_error_message(body)
        assert "unknown_key" in result


class TestResponseHandler:
    """Tests for ResponseHandler class."""

    def test_success_200(self):
        """Should return parsed JSON for 200."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": "value"}

        result = handler.handle_response(response)
        assert result == {"data": "value"}

    def test_success_201(self):
        """Should return parsed JSON for 201."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 201
        response.json.return_value = {"id": "123"}

        result = handler.handle_response(response)
        assert result == {"id": "123"}

    def test_success_204(self):
        """Should return None for 204 No Content."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 204

        result = handler.handle_response(response)
        assert result is None

    def test_401_raises_auth_error(self):
        """Should raise AuthenticationError for 401."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 401
        response.url = "https://api.bill.com/test"
        response.json.return_value = {"message": "Invalid token"}
        response.text = '{"message": "Invalid token"}'

        with pytest.raises(AuthenticationError) as exc:
            handler.handle_response(response)
        assert "Authentication failed" in str(exc.value)

    def test_404_raises_not_found(self):
        """Should raise NotFoundError for 404."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 404
        response.url = "https://api.bill.com/users/123"
        response.json.return_value = {"message": "User not found"}
        response.text = '{"message": "User not found"}'

        with pytest.raises(NotFoundError) as exc:
            handler.handle_response(response)
        assert "not found" in str(exc.value).lower()

    def test_409_raises_conflict(self):
        """Should raise ConflictError for 409."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 409
        response.url = "https://api.bill.com/users"
        response.json.return_value = {"message": "Email already exists"}
        response.text = '{"message": "Email already exists"}'

        with pytest.raises(ConflictError) as exc:
            handler.handle_response(response)
        assert "Conflict" in str(exc.value)

    def test_429_raises_rate_limit(self):
        """Should raise RateLimitError for 429."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 429
        response.url = "https://api.bill.com/users"
        response.headers = {"Retry-After": "60"}
        response.json.return_value = {"message": "Rate limit exceeded"}
        response.text = '{"message": "Rate limit exceeded"}'

        with pytest.raises(RateLimitError) as exc:
            handler.handle_response(response)
        assert exc.value.retry_after == 60

    def test_500_raises_server_error(self):
        """Should raise ServerError for 5xx."""
        handler = ResponseHandler()
        response = MagicMock()
        response.status_code = 500
        response.url = "https://api.bill.com/users"
        response.request.method = "POST"
        response.json.return_value = {"message": "Internal error"}
        response.text = '{"message": "Internal error"}'

        with pytest.raises(ServerError) as exc:
            handler.handle_response(response)
        assert exc.value.status_code == 500


class TestBillHttpClient:
    """Tests for BillHttpClient."""

    def test_missing_token_raises_error(self):
        """Should raise ConfigurationError if token is missing."""
        with pytest.raises(ConfigurationError) as exc:
            BillHttpClient(
                api_base="https://api.bill.com",
                api_token="",
            )
        assert "BILL API token" in str(exc.value)

    def test_headers_include_api_token(self):
        """Should include apiToken in headers."""
        client = BillHttpClient(
            api_base="https://api.bill.com",
            api_token="test-token-123",
        )
        headers = client.headers()
        assert headers["apiToken"] == "test-token-123"
        assert headers["Content-Type"] == "application/json"

    @responses.activate
    def test_get_request(self):
        """Should make GET request."""
        responses.add(
            responses.GET,
            "https://api.bill.com/users",
            json={"users": []},
            status=200,
        )

        client = BillHttpClient(
            api_base="https://api.bill.com",
            api_token="test-token",
        )
        response = client.get("/users")
        assert response.status_code == 200


class TestUKGHttpClient:
    """Tests for UKGHttpClient."""

    def test_missing_auth_raises_error(self):
        """Should raise ConfigurationError if auth is missing."""
        with pytest.raises(ConfigurationError):
            UKGHttpClient(
                base_url="https://service.ultipro.com",
                basic_auth_token="",
                customer_api_key="key",
            )

    def test_headers_include_auth(self):
        """Should include Authorization and Customer API key."""
        client = UKGHttpClient(
            base_url="https://service.ultipro.com",
            basic_auth_token="base64token",
            customer_api_key="customer-key",
        )
        headers = client.headers()
        assert headers["Authorization"] == "Basic base64token"
        assert headers["US-Customer-Api-Key"] == "customer-key"
