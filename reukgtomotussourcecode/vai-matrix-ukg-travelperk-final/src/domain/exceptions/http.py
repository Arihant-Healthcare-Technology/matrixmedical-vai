"""
HTTP-related exceptions.

Provides specific exception classes for common HTTP error scenarios.
"""

from typing import Optional, Dict, Any, List

from .base import ApiError


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
