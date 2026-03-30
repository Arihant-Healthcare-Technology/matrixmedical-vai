"""Tests for API exceptions."""

import pytest

from src.domain.exceptions.api_exceptions import (
    ApiError,
    UkgApiError,
    MotusApiError,
    AuthenticationError,
    RateLimitError,
)


class TestApiError:
    """Test cases for ApiError base exception."""

    def test_create_basic(self):
        """Test creating basic ApiError."""
        error = ApiError("Test error message")

        assert str(error) == "Test error message"
        assert error.status_code is None
        assert error.response_body == {}

    def test_create_with_status_code(self):
        """Test creating ApiError with status code."""
        error = ApiError("Test error", status_code=500)

        assert error.status_code == 500

    def test_create_with_response_body(self):
        """Test creating ApiError with response body."""
        body = {"error": "details", "code": "ERROR_001"}
        error = ApiError("Test error", response_body=body)

        assert error.response_body == body

    def test_create_with_all_params(self):
        """Test creating ApiError with all parameters."""
        body = {"error": "details"}
        error = ApiError("Test error", status_code=404, response_body=body)

        assert str(error) == "Test error"
        assert error.status_code == 404
        assert error.response_body == body

    def test_is_exception(self):
        """Test ApiError is an Exception."""
        error = ApiError("Test")
        assert isinstance(error, Exception)


class TestUkgApiError:
    """Test cases for UkgApiError."""

    def test_create_basic(self):
        """Test creating basic UkgApiError."""
        error = UkgApiError("UKG API error")

        assert str(error) == "UKG API error"
        assert error.status_code is None
        assert error.response_body == {}
        assert error.endpoint is None

    def test_create_with_endpoint(self):
        """Test creating UkgApiError with endpoint."""
        error = UkgApiError(
            "UKG API error",
            endpoint="/personnel/v1/person-details",
        )

        assert error.endpoint == "/personnel/v1/person-details"

    def test_create_with_all_params(self):
        """Test creating UkgApiError with all parameters."""
        body = {"error": "Employee not found"}
        error = UkgApiError(
            "UKG API error",
            status_code=404,
            response_body=body,
            endpoint="/personnel/v1/person-details",
        )

        assert error.status_code == 404
        assert error.response_body == body
        assert error.endpoint == "/personnel/v1/person-details"

    def test_inherits_from_api_error(self):
        """Test UkgApiError inherits from ApiError."""
        error = UkgApiError("Test")
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestMotusApiError:
    """Test cases for MotusApiError."""

    def test_create_basic(self):
        """Test creating basic MotusApiError."""
        error = MotusApiError("Motus API error")

        assert str(error) == "Motus API error"
        assert error.status_code is None
        assert error.response_body == {}
        assert error.driver_id is None

    def test_create_with_driver_id(self):
        """Test creating MotusApiError with driver_id."""
        error = MotusApiError(
            "Motus API error",
            driver_id="12345",
        )

        assert error.driver_id == "12345"

    def test_create_with_all_params(self):
        """Test creating MotusApiError with all parameters."""
        body = {"error": "Driver not found"}
        error = MotusApiError(
            "Motus API error",
            status_code=404,
            response_body=body,
            driver_id="12345",
        )

        assert error.status_code == 404
        assert error.response_body == body
        assert error.driver_id == "12345"

    def test_inherits_from_api_error(self):
        """Test MotusApiError inherits from ApiError."""
        error = MotusApiError("Test")
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestAuthenticationError:
    """Test cases for AuthenticationError."""

    def test_create_default_message(self):
        """Test creating AuthenticationError with default message."""
        error = AuthenticationError()

        assert str(error) == "Authentication failed"
        assert error.status_code == 401
        assert error.provider is None

    def test_create_custom_message(self):
        """Test creating AuthenticationError with custom message."""
        error = AuthenticationError("Custom auth error")

        assert str(error) == "Custom auth error"

    def test_create_with_provider(self):
        """Test creating AuthenticationError with provider."""
        error = AuthenticationError(provider="motus")

        assert error.provider == "motus"
        assert error.status_code == 401

    def test_create_with_all_params(self):
        """Test creating AuthenticationError with all parameters."""
        error = AuthenticationError(
            message="Token expired",
            provider="ukg",
        )

        assert str(error) == "Token expired"
        assert error.provider == "ukg"
        assert error.status_code == 401

    def test_inherits_from_api_error(self):
        """Test AuthenticationError inherits from ApiError."""
        error = AuthenticationError()
        assert isinstance(error, ApiError)
        assert isinstance(error, Exception)


class TestRateLimitError:
    """Test cases for RateLimitError."""

    def test_create_default_message(self):
        """Test creating RateLimitError with default message."""
        error = RateLimitError()

        assert str(error) == "Rate limit exceeded"
        assert error.status_code == 429
        assert error.retry_after == 60  # Default

    def test_create_custom_message(self):
        """Test creating RateLimitError with custom message."""
        error = RateLimitError("Too many requests")

        assert str(error) == "Too many requests"

    def test_create_with_retry_after(self):
        """Test creating RateLimitError with retry_after."""
        error = RateLimitError(retry_after=30)

        assert error.retry_after == 30
        assert error.status_code == 429

    def test_create_with_all_params(self):
        """Test creating RateLimitError with all parameters."""
        error = RateLimitError(
            message="Slow down",
            retry_after=120,
        )

        assert str(error) == "Slow down"
        assert error.retry_after == 120
        assert error.status_code == 429

    def test_retry_after_none_uses_default(self):
        """Test retry_after None uses default value."""
        error = RateLimitError(retry_after=None)

        assert error.retry_after == 60

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

    def test_catch_api_error_catches_motus_error(self):
        """Test catching ApiError catches MotusApiError."""
        try:
            raise MotusApiError("Test")
        except ApiError as e:
            assert isinstance(e, MotusApiError)

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
            MotusApiError("Test"),
            AuthenticationError(),
            RateLimitError(),
        ]

        for error in errors:
            try:
                raise error
            except Exception as e:
                assert e is error
