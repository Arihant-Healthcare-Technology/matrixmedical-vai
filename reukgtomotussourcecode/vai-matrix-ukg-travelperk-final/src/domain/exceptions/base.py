"""
Base API exception class.

Provides the foundation for all API-related exceptions with support for:
- Machine-readable error codes
- Retry decisions via is_retryable property
- Serialization via to_dict() method
- Correlation ID tracking
"""

from typing import Optional, Dict, Any


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
