"""
API-related exceptions for UKG-TravelPerk integration.

This module provides a comprehensive exception hierarchy for handling
API errors with support for:
- Machine-readable error codes
- Retry decisions via is_retryable property
- Serialization via to_dict() method
- Correlation ID tracking
"""

from typing import Optional, Dict, Any, List


class ApiError(Exception):
    """
    Base exception for API errors.

    Attributes:
        message: Human-readable error message.
        status_code: HTTP status code if applicable.
        error_code: Machine-readable error code (e.g., 'API_ERROR_404').
        response_body: Raw response body from API.
        correlation_id: Request correlation ID for tracing.
        is_retryable: Whether the operation can be retried.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self._derive_error_code(status_code)
        self.response_body = response_body or {}
        self.correlation_id = correlation_id

    def _derive_error_code(self, status_code: Optional[int]) -> str:
        """Derive error code from status code."""
        if status_code:
            return f"API_ERROR_{status_code}"
        return "API_ERROR_UNKNOWN"

    @property
    def is_retryable(self) -> bool:
        """
        Determine if the error is retryable.

        Returns:
            True if the operation can be retried safely.
        """
        retryable_codes = {408, 429, 500, 502, 503, 504}
        return self.status_code in retryable_codes if self.status_code else False

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize exception to dictionary.

        Returns:
            Dict representation of the exception.
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "error_code": self.error_code,
            "correlation_id": self.correlation_id,
            "is_retryable": self.is_retryable,
            "details": self.response_body,
        }

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.error_code}] {self.message} (HTTP {self.status_code})"
        return f"[{self.error_code}] {self.message}"


class UkgApiError(ApiError):
    """Exception for UKG API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"UKG_ERROR_{status_code}" if status_code else "UKG_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )


class TravelPerkApiError(ApiError):
    """Exception for TravelPerk SCIM API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"TRAVELPERK_ERROR_{status_code}" if status_code else "TRAVELPERK_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )


class AuthenticationError(ApiError):
    """
    Exception for authentication failures (HTTP 401/403).

    Raised when API credentials are invalid or expired.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: int = 401,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="AUTH_ERROR",
            correlation_id=correlation_id,
        )

    @property
    def is_retryable(self) -> bool:
        """Auth errors are not retryable without credential refresh."""
        return False


class RateLimitError(ApiError):
    """
    Exception for rate limiting (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_ERROR",
            correlation_id=correlation_id,
        )
        self.retry_after = retry_after

    @property
    def is_retryable(self) -> bool:
        """Rate limit errors are always retryable after waiting."""
        return True

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["retry_after"] = self.retry_after
        return result


class BadRequestError(ApiError):
    """
    Exception for bad request errors (HTTP 400).

    Raised when request validation fails.

    Attributes:
        validation_errors: List of specific validation error messages.
    """

    def __init__(
        self,
        message: str = "Bad request",
        validation_errors: Optional[List[str]] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code="BAD_REQUEST_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )
        self.validation_errors = validation_errors or []

    @property
    def is_retryable(self) -> bool:
        """Bad requests are not retryable without fixing the request."""
        return False

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["validation_errors"] = self.validation_errors
        return result


class NotFoundError(ApiError):
    """
    Exception for resource not found (HTTP 404).

    Raised when a requested resource does not exist.

    Attributes:
        resource_type: Type of resource not found (e.g., 'employee', 'user').
        resource_id: Identifier of the resource that was not found.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND_ERROR",
            correlation_id=correlation_id,
        )
        self.resource_type = resource_type
        self.resource_id = resource_id

    @property
    def is_retryable(self) -> bool:
        """Not found errors are not retryable."""
        return False

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.resource_type:
            result["resource_type"] = self.resource_type
        if self.resource_id:
            result["resource_id"] = self.resource_id
        return result


class ConflictError(ApiError):
    """
    Exception for conflict errors (HTTP 409).

    Raised when a resource already exists or there's a version conflict.

    Attributes:
        conflict_field: Field that caused the conflict (e.g., 'email').
        existing_id: ID of the existing conflicting resource.
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        conflict_field: Optional[str] = None,
        existing_id: Optional[str] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )
        self.conflict_field = conflict_field
        self.existing_id = existing_id

    @property
    def is_retryable(self) -> bool:
        """Conflicts are not retryable without resolving the conflict."""
        return False

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.conflict_field:
            result["conflict_field"] = self.conflict_field
        if self.existing_id:
            result["existing_id"] = self.existing_id
        return result


class TimeoutError(ApiError):
    """
    Exception for request timeout (HTTP 408 or connection timeout).

    Attributes:
        timeout_seconds: The timeout duration that was exceeded.
    """

    def __init__(
        self,
        message: str = "Request timed out",
        timeout_seconds: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=408,
            error_code="TIMEOUT_ERROR",
            correlation_id=correlation_id,
        )
        self.timeout_seconds = timeout_seconds

    @property
    def is_retryable(self) -> bool:
        """Timeout errors are generally retryable."""
        return True

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.timeout_seconds:
            result["timeout_seconds"] = self.timeout_seconds
        return result


class ServerError(ApiError):
    """
    Exception for server errors (HTTP 5xx).

    Raised for internal server errors, bad gateway, etc.
    """

    def __init__(
        self,
        message: str = "Server error",
        status_code: int = 500,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"SERVER_ERROR_{status_code}",
            response_body=response_body,
            correlation_id=correlation_id,
        )

    @property
    def is_retryable(self) -> bool:
        """Server errors are generally retryable."""
        return True
