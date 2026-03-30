"""API-related exceptions."""

from typing import Optional, Dict, Any


class ApiError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"{self.message} (HTTP {self.status_code})"
        return self.message


class UkgApiError(ApiError):
    """Exception for UKG API errors."""

    pass


class TravelPerkApiError(ApiError):
    """Exception for TravelPerk API errors."""

    pass


class AuthenticationError(ApiError):
    """Exception for authentication failures."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class RateLimitError(ApiError):
    """Exception for rate limiting (HTTP 429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
    ):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after
