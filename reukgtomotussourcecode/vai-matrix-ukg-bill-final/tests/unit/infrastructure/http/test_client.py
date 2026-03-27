"""
Unit tests for HTTP client with retry logic.
"""
import pytest
from unittest.mock import MagicMock, patch
import requests


class TestHttpClient:
    """Tests for HttpClient class."""

    def test_init_with_defaults(self):
        """Test initializes with default values."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        assert client.base_url == "https://api.example.com"
        assert client.timeout > 0

    def test_init_strips_trailing_slash(self):
        """Test strips trailing slash from base URL."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com/")

        assert client.base_url == "https://api.example.com"

    def test_headers_returns_default_headers(self):
        """Test returns default Content-Type and Accept headers."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")
        headers = client.headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_headers_merges_custom_headers(self):
        """Test merges custom headers from headers_func."""
        from src.infrastructure.http.client import HttpClient

        def custom_headers():
            return {"Authorization": "Bearer token123"}

        client = HttpClient(
            base_url="https://api.example.com",
            headers_func=custom_headers,
        )
        headers = client.headers()

        assert headers["Authorization"] == "Bearer token123"
        assert headers["Content-Type"] == "application/json"

    def test_apply_rate_limit_calls_limiter(self):
        """Test applies rate limit when limiter is configured."""
        from src.infrastructure.http.client import HttpClient

        mock_limiter = MagicMock()
        client = HttpClient(
            base_url="https://api.example.com",
            rate_limiter=mock_limiter,
        )

        client._apply_rate_limit()

        mock_limiter.acquire.assert_called_once()

    def test_apply_rate_limit_noop_without_limiter(self):
        """Test does nothing when no rate limiter configured."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        # Should not raise
        client._apply_rate_limit()

    def test_make_request_prepends_base_url(self):
        """Test prepends base URL to relative paths."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            client._make_request("GET", "/users")

            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["url"] == "https://api.example.com/users"

    def test_make_request_uses_absolute_url(self):
        """Test uses absolute URL as-is."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            client._make_request("GET", "https://other.api.com/resource")

            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["url"] == "https://other.api.com/resource"

    def test_make_request_merges_custom_headers(self):
        """Test merges additional headers from kwargs."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            client._make_request("GET", "/users", headers={"X-Custom": "value"})

            call_kwargs = mock_request.call_args.kwargs
            assert "X-Custom" in call_kwargs["headers"]
            assert call_kwargs["headers"]["X-Custom"] == "value"

    def test_make_request_raises_timeout_error(self):
        """Test raises TimeoutError on request timeout."""
        from src.infrastructure.http.client import HttpClient
        from src.domain.exceptions import TimeoutError

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "request") as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout()

            with pytest.raises(TimeoutError):
                client._make_request("GET", "/users")

    def test_make_request_raises_api_error(self):
        """Test raises ApiError on request exception."""
        from src.infrastructure.http.client import HttpClient
        from src.domain.exceptions import ApiError

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "request") as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError()

            with pytest.raises(ApiError):
                client._make_request("GET", "/users")

    def test_request_with_retry_succeeds_first_try(self):
        """Test returns response on first successful try."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client, "_make_request") as mock_make:
            mock_make.return_value = MagicMock(status_code=200)
            response = client._request_with_retry("GET", "/users")

            assert response.status_code == 200
            mock_make.assert_called_once()

    def test_request_with_retry_retries_on_500(self):
        """Test retries on 500 status code."""
        from src.infrastructure.http.client import HttpClient
        from src.infrastructure.http.retry import ExponentialBackoff

        strategy = ExponentialBackoff(max_retries=2, base_delay=0.01)
        client = HttpClient(
            base_url="https://api.example.com",
            retry_strategy=strategy,
        )

        with patch.object(client, "_make_request") as mock_make:
            mock_make.side_effect = [
                MagicMock(status_code=500),
                MagicMock(status_code=200),
            ]
            response = client._request_with_retry("GET", "/users")

            assert response.status_code == 200
            assert mock_make.call_count == 2

    def test_get_makes_get_request(self):
        """Test get method makes GET request."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client, "_request_with_retry") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            client.get("/users", params={"page": 1})

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"

    def test_post_makes_post_request(self):
        """Test post method makes POST request."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client, "_request_with_retry") as mock_request:
            mock_request.return_value = MagicMock(status_code=201)
            client.post("/users", json={"name": "Test"})

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"

    def test_patch_makes_patch_request(self):
        """Test patch method makes PATCH request."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client, "_request_with_retry") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            client.patch("/users/1", json={"name": "Updated"})

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "PATCH"

    def test_delete_makes_delete_request(self):
        """Test delete method makes DELETE request."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client, "_request_with_retry") as mock_request:
            mock_request.return_value = MagicMock(status_code=204)
            client.delete("/users/1")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "DELETE"

    def test_context_manager(self):
        """Test can be used as context manager."""
        from src.infrastructure.http.client import HttpClient

        with HttpClient(base_url="https://api.example.com") as client:
            assert client is not None

    def test_close_closes_session(self):
        """Test close method closes session."""
        from src.infrastructure.http.client import HttpClient

        client = HttpClient(base_url="https://api.example.com")

        with patch.object(client.session, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()


class TestBillHttpClient:
    """Tests for BillHttpClient class."""

    def test_raises_without_api_token(self):
        """Test raises ConfigurationError without API token."""
        from src.infrastructure.http.client import BillHttpClient
        from src.domain.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="BILL API token"):
            BillHttpClient(api_base="https://api.bill.com", api_token="")

    def test_init_with_api_token(self):
        """Test initializes with API token."""
        from src.infrastructure.http.client import BillHttpClient

        client = BillHttpClient(
            api_base="https://api.bill.com",
            api_token="token123",
        )

        assert client._api_token == "token123"

    def test_headers_includes_api_token(self):
        """Test headers include API token."""
        from src.infrastructure.http.client import BillHttpClient

        client = BillHttpClient(
            api_base="https://api.bill.com",
            api_token="token123",
        )
        headers = client.headers()

        assert headers["apiToken"] == "token123"


class TestUKGHttpClient:
    """Tests for UKGHttpClient class."""

    def test_raises_without_basic_auth(self):
        """Test raises ConfigurationError without basic auth token."""
        from src.infrastructure.http.client import UKGHttpClient
        from src.domain.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="Basic auth"):
            UKGHttpClient(
                base_url="https://api.ukg.com",
                basic_auth_token="",
                customer_api_key="key123",
            )

    def test_raises_without_api_key(self):
        """Test raises ConfigurationError without customer API key."""
        from src.infrastructure.http.client import UKGHttpClient
        from src.domain.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="Customer API key"):
            UKGHttpClient(
                base_url="https://api.ukg.com",
                basic_auth_token="auth123",
                customer_api_key="",
            )

    def test_init_with_credentials(self):
        """Test initializes with credentials."""
        from src.infrastructure.http.client import UKGHttpClient

        client = UKGHttpClient(
            base_url="https://api.ukg.com",
            basic_auth_token="auth123",
            customer_api_key="key123",
        )

        assert client._basic_auth_token == "auth123"
        assert client._customer_api_key == "key123"

    def test_headers_includes_auth(self):
        """Test headers include authorization."""
        from src.infrastructure.http.client import UKGHttpClient

        client = UKGHttpClient(
            base_url="https://api.ukg.com",
            basic_auth_token="auth123",
            customer_api_key="key123",
        )
        headers = client.headers()

        assert headers["Authorization"] == "Basic auth123"
        assert headers["US-Customer-Api-Key"] == "key123"
