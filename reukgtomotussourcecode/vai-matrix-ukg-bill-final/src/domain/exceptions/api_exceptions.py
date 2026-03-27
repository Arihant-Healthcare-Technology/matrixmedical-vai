"""
API-specific exceptions for HTTP client operations.

These exceptions map to common HTTP error scenarios and provide
structured error information for retry logic and error reporting.
"""

from typing import Any, Dict, Optional

from src.domain.exceptions.base import IntegrationError


class ApiError(IntegrationError):
    """
    Base exception for API-related errors.

    Attributes:
        status_code: HTTP status code from the response
        url: The URL that was requested
        method: HTTP method used (GET, POST, etc.)
        response_body: Raw response body (truncated for safety)
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
        response_body: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extra_details = {
            "status_code": status_code,
            "url": url,
            "method": method,
            "response_body": response_body[:500] if response_body else None,
        }
        super().__init__(
            message=message,
            code=f"API_ERROR_{status_code}" if status_code else "API_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
            correlation_id=correlation_id,
        )
        self.status_code = status_code
        self.url = url
        self.method = method
        self.response_body = response_body

    @property
    def is_retryable(self) -> bool:
        """Check if the error is potentially retryable."""
        if self.status_code is None:
            return True  # Network errors are retryable
        return self.status_code >= 500 or self.status_code == 429


class NotFoundError(ApiError):
    """
    Raised when a requested resource is not found (HTTP 404).

    Attributes:
        resource_type: Type of resource (e.g., 'user', 'vendor')
        resource_id: Identifier of the missing resource
    """

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        url: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        super().__init__(
            message=message,
            status_code=404,
            url=url,
            method="GET",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ApiError):
    """
    Raised when there's a conflict with existing data (HTTP 409).

    Common scenarios:
        - Duplicate email address
        - Resource already exists
        - Concurrent modification conflict

    Attributes:
        conflict_field: Field that caused the conflict
        existing_id: ID of the conflicting existing resource
    """

    def __init__(
        self,
        message: str,
        conflict_field: Optional[str] = None,
        existing_id: Optional[str] = None,
        url: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "conflict_field": conflict_field,
            "existing_id": existing_id,
        }
        super().__init__(
            message=message,
            status_code=409,
            url=url,
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.conflict_field = conflict_field
        self.existing_id = existing_id


class TimeoutError(ApiError):
    """
    Raised when an API request times out.

    Attributes:
        timeout_seconds: The timeout value that was exceeded
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=None,  # Timeouts don't have HTTP status
            url=url,
            method=method,
            details={**(details or {}), "timeout_seconds": timeout_seconds},
        )
        self.timeout_seconds = timeout_seconds


class ServerError(ApiError):
    """
    Raised when the server returns a 5xx error.

    These errors are typically retryable after a delay.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        url: Optional[str] = None,
        method: Optional[str] = None,
        response_body: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if status_code < 500 or status_code >= 600:
            raise ValueError(f"ServerError requires 5xx status code, got {status_code}")
        super().__init__(
            message=message,
            status_code=status_code,
            url=url,
            method=method,
            response_body=response_body,
            details=details,
        )


class BadRequestError(ApiError):
    """
    Raised when the request is malformed (HTTP 400).

    Attributes:
        validation_errors: List of specific validation failures from API
    """

    def __init__(
        self,
        message: str,
        validation_errors: Optional[list] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
        response_body: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            url=url,
            method=method,
            response_body=response_body,
            details={**(details or {}), "validation_errors": validation_errors},
        )
        self.validation_errors = validation_errors or []
