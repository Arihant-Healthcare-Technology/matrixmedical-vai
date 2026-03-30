"""
API exceptions.

Provides exception classes for API-related errors.
"""

from typing import Any, Dict, Optional


class ApiError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}


class UkgApiError(ApiError):
    """Exception for UKG API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None,
    ):
        super().__init__(message, status_code, response_body)
        self.endpoint = endpoint


class MotusApiError(ApiError):
    """Exception for Motus API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        driver_id: Optional[str] = None,
    ):
        super().__init__(message, status_code, response_body)
        self.driver_id = driver_id


class AuthenticationError(ApiError):
    """Exception for authentication failures."""

    def __init__(
        self,
        message: str = "Authentication failed",
        provider: Optional[str] = None,
    ):
        super().__init__(message, status_code=401)
        self.provider = provider


class RateLimitError(ApiError):
    """Exception for rate limit errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after or 60
