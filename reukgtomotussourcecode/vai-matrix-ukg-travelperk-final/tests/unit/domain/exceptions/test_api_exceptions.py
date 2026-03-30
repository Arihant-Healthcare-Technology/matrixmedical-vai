"""Tests for API exceptions."""

import pytest

from src.domain.exceptions.api_exceptions import (
    ApiError,
    UkgApiError,
    TravelPerkApiError,
    AuthenticationError,
    RateLimitError,
)


class TestApiError:
    """Test cases for ApiError base exception."""

    def test_create_basic(self):
        """Test creating basic ApiError."""
        error = ApiError("Test error message")

        assert error.message == "Test error message"
        assert error.status_code is None
        assert error.response_body == {}

    def test_create_with_status_code(self):
        """Test creating ApiError with status code."""
        error = ApiError("Test error", status_code=500)

        assert error.status_code == 500
        assert str(error) == "Test error (HTTP 500)"

    def test_create_with_response_body(self):
        """Test creating ApiError with response body."""
        body = {"error": "details", "code": "ERROR_001"}
        error = ApiError("Test error", response_body=body)

        assert error.response_body == body

    def test_str_without_status(self):
        """Test string representation without status code."""
        error = ApiError("Test error")
        assert str(error) == "Test error"

    def test_str_with_status(self):
        """Test string representation with status code."""
        error = ApiError("Test error", status_code=404)
        assert str(error) == "Test error (HTTP 404)"

    def test_is_exception(self):
        """Test ApiError is an Exception."""
        error = ApiError("Test")
        assert isinstance(error, Exception)


class TestUkgApiError:
    """Test cases for UkgApiError."""

    def test_create(self):
        """Test creating UkgApiError."""
        error = UkgApiError("UKG API error")

        assert error.message == "UKG API error"
        assert isinstance(error, ApiError)

    def test_create_with_status(self):
        """Test creating UkgApiError with status code."""
        error = UkgApiError("UKG API error", status_code=404)

        assert error.status_code == 404
        assert str(error) == "UKG API error (HTTP 404)"

    def test_inherits_from_api_error(self):
        """Test UkgApiError inherits from ApiError."""
        error = UkgApiError("Test")
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestTravelPerkApiError:
    """Test cases for TravelPerkApiError."""

    def test_create(self):
        """Test creating TravelPerkApiError."""
        error = TravelPerkApiError("TravelPerk API error")

        assert error.message == "TravelPerk API error"
        assert isinstance(error, ApiError)

    def test_create_with_all_params(self):
        """Test creating TravelPerkApiError with all parameters."""
        body = {"error": "details"}
        error = TravelPerkApiError(
            "TravelPerk API error",
            status_code=400,
            response_body=body,
        )

        assert error.status_code == 400
        assert error.response_body == body

    def test_inherits_from_api_error(self):
        """Test TravelPerkApiError inherits from ApiError."""
        error = TravelPerkApiError("Test")
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestAuthenticationError:
    """Test cases for AuthenticationError."""

    def test_create_default_message(self):
        """Test creating AuthenticationError with default message."""
        error = AuthenticationError()

        assert error.message == "Authentication failed"
        assert error.status_code == 401

    def test_create_custom_message(self):
        """Test creating AuthenticationError with custom message."""
        error = AuthenticationError("Custom auth error")

        assert error.message == "Custom auth error"
        assert error.status_code == 401

    def test_str_representation(self):
        """Test string representation."""
        error = AuthenticationError("Auth failed")
        assert str(error) == "Auth failed (HTTP 401)"

    def test_inherits_from_api_error(self):
        """Test AuthenticationError inherits from ApiError."""
        error = AuthenticationError()
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestRateLimitError:
    """Test cases for RateLimitError."""

    def test_create_default(self):
        """Test creating RateLimitError with defaults."""
        error = RateLimitError()

        assert error.message == "Rate limit exceeded"
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_create_custom(self):
        """Test creating RateLimitError with custom values."""
        error = RateLimitError("Too many requests", retry_after=30)

        assert error.message == "Too many requests"
        assert error.retry_after == 30

    def test_str_representation(self):
        """Test string representation."""
        error = RateLimitError()
        assert str(error) == "Rate limit exceeded (HTTP 429)"

    def test_inherits_from_api_error(self):
        """Test RateLimitError inherits from ApiError."""
        error = RateLimitError()
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestExceptionCatching:
    """Test exception catching scenarios."""

    def test_catch_api_error_catches_ukg_error(self):
        """Test catching ApiError catches UkgApiError."""
        try:
            raise UkgApiError("Test")
        except ApiError as e:
            assert isinstance(e, UkgApiError)

    def test_catch_api_error_catches_travelperk_error(self):
        """Test catching ApiError catches TravelPerkApiError."""
        try:
            raise TravelPerkApiError("Test")
        except ApiError as e:
            assert isinstance(e, TravelPerkApiError)

    def test_catch_api_error_catches_auth_error(self):
        """Test catching ApiError catches AuthenticationError."""
        try:
            raise AuthenticationError()
        except ApiError as e:
            assert isinstance(e, AuthenticationError)

    def test_catch_api_error_catches_rate_limit_error(self):
        """Test catching ApiError catches RateLimitError."""
        try:
            raise RateLimitError()
        except ApiError as e:
            assert isinstance(e, RateLimitError)

    def test_catch_exception_catches_all(self):
        """Test catching Exception catches all API errors."""
        errors = [
            ApiError("Test"),
            UkgApiError("Test"),
            TravelPerkApiError("Test"),
            AuthenticationError(),
            RateLimitError(),
        ]

        for error in errors:
            try:
                raise error
            except Exception as e:
                assert e is error
