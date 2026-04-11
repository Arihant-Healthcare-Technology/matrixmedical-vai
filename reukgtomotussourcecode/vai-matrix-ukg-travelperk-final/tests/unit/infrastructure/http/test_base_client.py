"""Tests for BaseHTTPClient."""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock
import requests

from src.infrastructure.http.base_client import BaseHTTPClient
from common.rate_limiter import RateLimiter


class ConcreteHTTPClient(BaseHTTPClient):
    """Concrete implementation for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._test_headers = {"Authorization": "Bearer test-token"}
        self._error_raised = False

    def _get_headers(self):
        return self._test_headers.copy()

    def _handle_error_response(self, response, url):
        self._error_raised = True
        if response.status_code == 401:
            raise ValueError("Unauthorized")
        elif response.status_code == 404:
            raise ValueError("Not found")
        elif response.status_code >= 500:
            raise ValueError(f"Server error: {response.status_code}")
        raise ValueError(f"Error: {response.status_code}")


class TestBaseHTTPClientInit:
    """Test cases for BaseHTTPClient initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        assert client.base_url == "https://api.example.com"
        assert client.timeout == 60.0
        assert client.max_retries == 2
        assert client.rate_limiter is None
        assert client.debug is False

    def test_init_strips_trailing_slash(self):
        """Test base_url trailing slash is stripped."""
        client = ConcreteHTTPClient(base_url="https://api.example.com/")

        assert client.base_url == "https://api.example.com"

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        rate_limiter = MagicMock(spec=RateLimiter)
        client = ConcreteHTTPClient(
            base_url="https://api.example.com",
            timeout=30.0,
            max_retries=5,
            rate_limiter=rate_limiter,
            debug=True,
        )

        assert client.timeout == 30.0
        assert client.max_retries == 5
        assert client.rate_limiter == rate_limiter
        assert client.debug is True

    def test_client_name_set_from_class(self):
        """Test _client_name is set from class name."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        assert client._client_name == "ConcreteHTTPClient"


class TestBuildUrl:
    """Test cases for _build_url method."""

    def test_build_url_with_path(self):
        """Test building URL with path."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        url = client._build_url("/users/123")

        assert url == "https://api.example.com/users/123"

    def test_build_url_without_leading_slash(self):
        """Test building URL without leading slash in path."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        url = client._build_url("users/123")

        assert url == "https://api.example.com/users/123"

    def test_build_url_with_multiple_slashes(self):
        """Test building URL handles multiple leading slashes."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        url = client._build_url("//users/123")

        assert url == "https://api.example.com/users/123"

    def test_build_url_empty_path(self):
        """Test building URL with empty path."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        url = client._build_url("")

        assert url == "https://api.example.com/"


class TestLogRequest:
    """Test cases for _log_request method."""

    def test_log_request_returns_start_time(self):
        """Test _log_request returns start time."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        before = time.time()
        start_time = client._log_request("GET", "https://api.example.com/users")
        after = time.time()

        assert before <= start_time <= after

    def test_log_request_sanitizes_url(self):
        """Test _log_request removes query params from logged URL."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_request(
                "GET",
                "https://api.example.com/users?api_key=secret",
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "api_key=secret" not in call_args
            assert "https://api.example.com/users" in call_args

    def test_log_request_with_payload(self):
        """Test _log_request logs payload keys."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_request(
                "POST",
                "https://api.example.com/users",
                payload={"name": "John", "email": "john@example.com"},
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "payload_keys=" in call_args

    def test_log_request_debug_mode(self):
        """Test _log_request logs full URL in debug mode."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", debug=True)

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_request(
                "GET",
                "https://api.example.com/users?api_key=secret",
            )

            # Check debug was called with full URL
            debug_call_args = mock_logger.debug.call_args[0][0]
            assert "api_key=secret" in debug_call_args


class TestLogResponse:
    """Test cases for _log_response method."""

    def test_log_response_success(self):
        """Test _log_response for successful response."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        start_time = time.time() - 0.1  # 100ms ago

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_response(
                "GET",
                "https://api.example.com/users",
                200,
                start_time,
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "status=200" in call_args
            assert "elapsed=" in call_args

    def test_log_response_error(self):
        """Test _log_response for error response uses warning."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        start_time = time.time()

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_response(
                "GET",
                "https://api.example.com/users",
                500,
                start_time,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "status=500" in call_args

    def test_log_response_debug_dict_data(self):
        """Test _log_response logs dict data in debug mode."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", debug=True)
        start_time = time.time()

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_response(
                "GET",
                "https://api.example.com/users",
                200,
                start_time,
                data={"id": 1, "name": "John"},
            )

            mock_logger.debug.assert_called()

    def test_log_response_debug_list_data(self):
        """Test _log_response logs list length in debug mode."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", debug=True)
        start_time = time.time()

        with patch("src.infrastructure.http.base_client.logger") as mock_logger:
            client._log_response(
                "GET",
                "https://api.example.com/users",
                200,
                start_time,
                data=[{"id": 1}, {"id": 2}],
            )

            debug_call_args = mock_logger.debug.call_args[0][0]
            assert "len=2" in debug_call_args


class TestSafeJson:
    """Test cases for _safe_json method."""

    def test_safe_json_valid_response(self):
        """Test _safe_json with valid JSON."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}

        result = client._safe_json(mock_response)

        assert result == {"key": "value"}

    def test_safe_json_invalid_response(self):
        """Test _safe_json with invalid JSON."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not JSON"

        result = client._safe_json(mock_response)

        assert "raw_text" in result


class TestShouldRetry:
    """Test cases for _should_retry method."""

    def test_should_retry_on_429(self):
        """Test should retry on rate limit."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", max_retries=3)

        assert client._should_retry(429, 0) is True
        assert client._should_retry(429, 1) is True
        assert client._should_retry(429, 2) is True

    def test_should_retry_on_server_errors(self):
        """Test should retry on server errors."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", max_retries=3)

        assert client._should_retry(500, 0) is True
        assert client._should_retry(502, 0) is True
        assert client._should_retry(503, 0) is True
        assert client._should_retry(504, 0) is True

    def test_should_not_retry_on_client_errors(self):
        """Test should not retry on client errors."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", max_retries=3)

        assert client._should_retry(400, 0) is False
        assert client._should_retry(401, 0) is False
        assert client._should_retry(403, 0) is False
        assert client._should_retry(404, 0) is False

    def test_should_not_retry_after_max_retries(self):
        """Test should not retry after max retries exceeded."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", max_retries=2)

        assert client._should_retry(500, 0) is True
        assert client._should_retry(500, 1) is True
        assert client._should_retry(500, 2) is False
        assert client._should_retry(500, 3) is False


class TestGetRetryWaitTime:
    """Test cases for _get_retry_wait_time method."""

    def test_rate_limit_with_retry_after_header(self):
        """Test wait time from Retry-After header for 429."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        wait_time = client._get_retry_wait_time(mock_response, 0)

        assert wait_time == 120.0

    def test_rate_limit_default_wait_time(self):
        """Test default wait time for 429 without header."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        wait_time = client._get_retry_wait_time(mock_response, 0)

        assert wait_time == 60.0

    def test_server_error_exponential_backoff(self):
        """Test exponential backoff for server errors."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 500

        assert client._get_retry_wait_time(mock_response, 0) == 1.0   # 2^0
        assert client._get_retry_wait_time(mock_response, 1) == 2.0   # 2^1
        assert client._get_retry_wait_time(mock_response, 2) == 4.0   # 2^2
        assert client._get_retry_wait_time(mock_response, 3) == 8.0   # 2^3


class TestAcquireRateLimit:
    """Test cases for _acquire_rate_limit method."""

    def test_acquires_rate_limit_when_configured(self):
        """Test rate limiter is called when configured."""
        rate_limiter = MagicMock(spec=RateLimiter)
        client = ConcreteHTTPClient(
            base_url="https://api.example.com",
            rate_limiter=rate_limiter,
        )

        client._acquire_rate_limit()

        rate_limiter.acquire.assert_called_once()

    def test_no_op_when_no_rate_limiter(self):
        """Test no error when rate limiter not configured."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")

        # Should not raise
        client._acquire_rate_limit()


class TestRequest:
    """Test cases for _request method."""

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_successful_get_request(self, mock_request):
        """Test successful GET request."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_request.return_value = mock_response

        response = client._request("GET", "/users")

        assert response == mock_response
        mock_request.assert_called_once()

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_with_params(self, mock_request):
        """Test request with query parameters."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        client._request("GET", "/users", params={"page": 1})

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"] == {"page": 1}

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_with_json_data(self, mock_request):
        """Test request with JSON body."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        client._request("POST", "/users", json_data={"name": "John"})

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"] == {"name": "John"}

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_handles_timeout(self, mock_request):
        """Test request handles timeout exception."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_request.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(requests.exceptions.Timeout):
            client._request("GET", "/users")

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_handles_connection_error(self, mock_request):
        """Test request handles connection error."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            client._request("GET", "/users")

    @patch("src.infrastructure.http.base_client.time.sleep")
    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_retries_on_server_error(self, mock_request, mock_sleep):
        """Test request retries on server error."""
        client = ConcreteHTTPClient(base_url="https://api.example.com", max_retries=2)

        # First two calls return 500, third returns 200
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.json.return_value = {"error": "Server error"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": "success"}

        mock_request.side_effect = [error_response, error_response, success_response]

        response = client._request("GET", "/users")

        assert response.status_code == 200
        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_calls_error_handler_on_client_error(self, mock_request):
        """Test request calls error handler on client error."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        mock_request.return_value = mock_response

        with pytest.raises(ValueError, match="Not found"):
            client._request("GET", "/users/999")

        assert client._error_raised is True

    @patch("src.infrastructure.http.base_client.requests.request")
    def test_request_acquires_rate_limit(self, mock_request):
        """Test request acquires rate limit before each attempt."""
        rate_limiter = MagicMock(spec=RateLimiter)
        client = ConcreteHTTPClient(
            base_url="https://api.example.com",
            rate_limiter=rate_limiter,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        client._request("GET", "/users")

        rate_limiter.acquire.assert_called_once()


class TestConvenienceMethods:
    """Test cases for convenience HTTP methods."""

    @patch.object(ConcreteHTTPClient, "_request")
    def test_get_method(self, mock_request):
        """Test get convenience method."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_request.return_value = mock_response

        client.get("/users", params={"page": 1})

        mock_request.assert_called_once_with("GET", "/users", params={"page": 1})

    @patch.object(ConcreteHTTPClient, "_request")
    def test_post_method(self, mock_request):
        """Test post convenience method."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_request.return_value = mock_response

        client.post("/users", json_data={"name": "John"})

        mock_request.assert_called_once_with(
            "POST", "/users", params=None, json_data={"name": "John"}
        )

    @patch.object(ConcreteHTTPClient, "_request")
    def test_patch_method(self, mock_request):
        """Test patch convenience method."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_request.return_value = mock_response

        client.patch("/users/1", json_data={"name": "Jane"})

        mock_request.assert_called_once_with(
            "PATCH", "/users/1", json_data={"name": "Jane"}
        )

    @patch.object(ConcreteHTTPClient, "_request")
    def test_put_method(self, mock_request):
        """Test put convenience method."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_request.return_value = mock_response

        client.put("/users/1", json_data={"name": "Jane"})

        mock_request.assert_called_once_with(
            "PUT", "/users/1", json_data={"name": "Jane"}
        )

    @patch.object(ConcreteHTTPClient, "_request")
    def test_delete_method(self, mock_request):
        """Test delete convenience method."""
        client = ConcreteHTTPClient(base_url="https://api.example.com")
        mock_response = MagicMock()
        mock_request.return_value = mock_response

        client.delete("/users/1")

        mock_request.assert_called_once_with("DELETE", "/users/1", params=None)
