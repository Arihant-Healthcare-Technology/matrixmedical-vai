"""Tests for UKG authentication utilities."""

import pytest
import base64
from unittest.mock import patch

from src.infrastructure.adapters.ukg.auth import UKGAuthenticator
from src.domain.exceptions import AuthenticationError


class TestUKGAuthenticatorInit:
    """Test cases for UKGAuthenticator initialization."""

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            basic_b64="dGVzdHVzZXI6dGVzdHBhc3M=",
            customer_api_key="test-api-key",
        )

        assert auth.username == "testuser"
        assert auth.password == "testpass"
        assert auth.basic_b64 == "dGVzdHVzZXI6dGVzdHBhc3M="
        assert auth.customer_api_key == "test-api-key"
        assert auth._cached_token is None

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        auth = UKGAuthenticator()

        assert auth.username is None
        assert auth.password is None
        assert auth.basic_b64 is None
        assert auth.customer_api_key is None


class TestGetToken:
    """Test cases for get_token method."""

    def test_get_token_from_username_password(self):
        """Test generating token from username/password."""
        auth = UKGAuthenticator(username="testuser", password="testpass")

        token = auth.get_token()

        expected = base64.b64encode(b"testuser:testpass").decode()
        assert token == expected

    def test_get_token_caches_result(self):
        """Test token is cached after first call."""
        auth = UKGAuthenticator(username="testuser", password="testpass")

        token1 = auth.get_token()
        token2 = auth.get_token()

        assert token1 == token2
        assert auth._cached_token == token1

    def test_get_token_from_basic_b64(self):
        """Test using pre-encoded base64 token."""
        valid_b64 = base64.b64encode(b"user:pass").decode()
        auth = UKGAuthenticator(basic_b64=valid_b64)

        token = auth.get_token()

        assert token == valid_b64

    def test_get_token_prefers_b64_over_username_password(self):
        """Test basic_b64 is preferred over username/password."""
        valid_b64 = base64.b64encode(b"b64user:b64pass").decode()
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            basic_b64=valid_b64,
        )

        token = auth.get_token()

        # Should use basic_b64, not username/password
        assert token == valid_b64

    def test_get_token_missing_credentials_raises_error(self):
        """Test error when both credentials missing."""
        auth = UKGAuthenticator()

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_token()

        assert "Missing UKG_USERNAME/UKG_PASSWORD" in str(exc_info.value)

    def test_get_token_invalid_b64_falls_back_to_username(self):
        """Test invalid base64 falls back to username/password."""
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            basic_b64="not-valid-base64!!!",
        )

        token = auth.get_token()

        # Should fall back to username/password
        expected = base64.b64encode(b"testuser:testpass").decode()
        assert token == expected

    def test_get_token_with_special_characters(self):
        """Test token generation with special characters in password."""
        auth = UKGAuthenticator(
            username="user@domain.com",
            password="P@ss!word#123",
        )

        token = auth.get_token()

        decoded = base64.b64decode(token).decode()
        assert decoded == "user@domain.com:P@ss!word#123"

    def test_get_token_empty_username_raises_error(self):
        """Test error when username is empty."""
        auth = UKGAuthenticator(username="", password="testpass")

        with pytest.raises(AuthenticationError):
            auth.get_token()

    def test_get_token_empty_password_raises_error(self):
        """Test error when password is empty."""
        auth = UKGAuthenticator(username="testuser", password="")

        with pytest.raises(AuthenticationError):
            auth.get_token()


class TestValidateB64Token:
    """Test cases for _validate_b64_token method."""

    def test_validate_valid_token(self):
        """Test validating a valid base64 token."""
        auth = UKGAuthenticator()
        valid_token = base64.b64encode(b"user:pass").decode()

        result = auth._validate_b64_token(valid_token)

        assert result == valid_token

    def test_validate_token_with_whitespace(self):
        """Test token with whitespace is cleaned."""
        auth = UKGAuthenticator()
        valid_token = base64.b64encode(b"user:pass").decode()
        token_with_spaces = f"  {valid_token}  "

        result = auth._validate_b64_token(token_with_spaces)

        assert result == valid_token

    def test_validate_token_with_newlines(self):
        """Test token with newlines is cleaned."""
        auth = UKGAuthenticator()
        valid_token = base64.b64encode(b"user:pass").decode()
        # Simulate multiline token
        token_with_newlines = valid_token[:5] + "\n" + valid_token[5:]

        result = auth._validate_b64_token(token_with_newlines)

        # Whitespace should be removed
        assert result == valid_token

    def test_validate_invalid_token_returns_none(self):
        """Test invalid base64 returns None."""
        auth = UKGAuthenticator()

        result = auth._validate_b64_token("not-valid-base64!!!")

        assert result is None

    def test_validate_empty_token(self):
        """Test empty token returns empty string (valid base64)."""
        auth = UKGAuthenticator()

        result = auth._validate_b64_token("")

        # Empty string is technically valid base64 (decodes to empty bytes)
        assert result == ""


class TestGetHeaders:
    """Test cases for get_headers method."""

    def test_get_headers_success(self):
        """Test successful header generation."""
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            customer_api_key="test-api-key",
        )

        headers = auth.get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["US-CUSTOMER-API-KEY"] == "test-api-key"
        assert headers["Accept"] == "application/json"

    def test_get_headers_missing_api_key_raises_error(self):
        """Test error when API key is missing."""
        auth = UKGAuthenticator(username="testuser", password="testpass")

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_headers()

        assert "Missing UKG_CUSTOMER_API_KEY" in str(exc_info.value)

    def test_get_headers_empty_api_key_raises_error(self):
        """Test error when API key is empty."""
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            customer_api_key="",
        )

        with pytest.raises(AuthenticationError):
            auth.get_headers()

    def test_get_headers_includes_correct_token(self):
        """Test headers include correct Basic auth token."""
        auth = UKGAuthenticator(
            username="testuser",
            password="testpass",
            customer_api_key="test-api-key",
        )

        headers = auth.get_headers()

        expected_token = base64.b64encode(b"testuser:testpass").decode()
        assert headers["Authorization"] == f"Basic {expected_token}"


class TestClearCache:
    """Test cases for clear_cache method."""

    def test_clear_cache_clears_token(self):
        """Test clear_cache removes cached token."""
        auth = UKGAuthenticator(username="testuser", password="testpass")
        auth.get_token()  # Cache the token
        assert auth._cached_token is not None

        auth.clear_cache()

        assert auth._cached_token is None

    def test_clear_cache_allows_regeneration(self):
        """Test token can be regenerated after clear."""
        auth = UKGAuthenticator(username="testuser", password="testpass")
        token1 = auth.get_token()

        auth.clear_cache()
        token2 = auth.get_token()

        # Tokens should be the same value
        assert token1 == token2

    def test_clear_cache_on_fresh_instance(self):
        """Test clear_cache on fresh instance doesn't raise."""
        auth = UKGAuthenticator()

        # Should not raise
        auth.clear_cache()

        assert auth._cached_token is None
