"""
Domain exceptions module.

Provides a comprehensive exception hierarchy for API errors with support for:
- Machine-readable error codes
- Retry decisions via is_retryable property
- Serialization via to_dict() method
- Correlation ID tracking

Structure:
- base.py: Base ApiError class
- http.py: HTTP-related exceptions
- providers.py: Provider-specific exceptions (UKG, TravelPerk)
- business_exceptions.py: Business logic exceptions
"""

# API Exceptions - Base
from .base import ApiError

# API Exceptions - HTTP
from .http import (
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    NotFoundError,
    ConflictError,
    TimeoutError,
    ServerError,
)

# API Exceptions - Providers
from .providers import (
    UkgApiError,
    TravelPerkApiError,
)

# Business Exceptions
from .business_exceptions import (
    UserValidationError,
    EmployeeNotFoundError,
    SupervisorNotFoundError,
)

__all__ = [
    # Base API Exception
    "ApiError",
    # HTTP Exceptions
    "AuthenticationError",
    "RateLimitError",
    "BadRequestError",
    "NotFoundError",
    "ConflictError",
    "TimeoutError",
    "ServerError",
    # Provider Exceptions
    "UkgApiError",
    "TravelPerkApiError",
    # Business Exceptions
    "UserValidationError",
    "EmployeeNotFoundError",
    "SupervisorNotFoundError",
]
