"""
API-related exceptions for UKG-TravelPerk integration.

This module re-exports all API exceptions from their respective modules
for backward compatibility.

Structure:
- base.py: Base ApiError class
- http.py: HTTP-related exceptions (auth, rate limit, timeout, etc.)
- providers.py: Provider-specific exceptions (UKG, TravelPerk)
"""

# Re-export from base
from .base import ApiError

# Re-export from HTTP exceptions
from .http import (
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    NotFoundError,
    ConflictError,
    TimeoutError,
    ServerError,
)

# Re-export from provider exceptions
from .providers import (
    UkgApiError,
    TravelPerkApiError,
)

__all__ = [
    # Base
    "ApiError",
    # HTTP errors
    "AuthenticationError",
    "RateLimitError",
    "BadRequestError",
    "NotFoundError",
    "ConflictError",
    "TimeoutError",
    "ServerError",
    # Provider errors
    "UkgApiError",
    "TravelPerkApiError",
]
