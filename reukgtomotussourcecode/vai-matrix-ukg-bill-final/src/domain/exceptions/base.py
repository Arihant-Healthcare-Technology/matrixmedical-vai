"""
Base exception hierarchy for the UKG-BILL integration suite.

This module defines the foundational exceptions that all other
domain-specific exceptions inherit from.
"""

from typing import Any, Dict, Optional


class IntegrationError(Exception):
    """
    Base exception for all integration errors.

    All custom exceptions in this codebase should inherit from this class
    to enable consistent error handling and logging.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code for categorization
        details: Additional context about the error
        correlation_id: Request correlation ID for tracing
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "INTEGRATION_ERROR"
        self.details = details or {}
        self.correlation_id = correlation_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id,
        }

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.correlation_id:
            base = f"[{self.correlation_id}] {base}"
        return base


class ConfigurationError(IntegrationError):
    """
    Raised when configuration is missing or invalid.

    Examples:
        - Missing required environment variable
        - Invalid API endpoint URL
        - Missing credentials
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CONFIG_ERROR",
            details={**(details or {}), "config_key": config_key} if config_key else details,
        )
        self.config_key = config_key


class AuthenticationError(IntegrationError):
    """
    Raised when authentication fails.

    Examples:
        - Invalid API token
        - Expired credentials
        - Missing authentication headers
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AUTH_ERROR",
            details={**(details or {}), "provider": provider} if provider else details,
        )
        self.provider = provider


class RateLimitError(IntegrationError):
    """
    Raised when API rate limit is exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying (if provided by API)
        limit: The rate limit that was exceeded
        remaining: Remaining requests (if known)
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "retry_after": retry_after,
            "limit": limit,
            "remaining": remaining,
        }
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining


class ValidationError(IntegrationError):
    """
    Raised when data validation fails.

    Attributes:
        field: The field that failed validation
        value: The invalid value (will be redacted in logs)
        constraint: The constraint that was violated
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "field": field,
            "constraint": constraint,
            # Note: value intentionally not included to avoid PII leakage
        }
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.field = field
        self.value = value  # Stored but not serialized
        self.constraint = constraint
