"""Domain exceptions."""

from .api_exceptions import (
    ApiError,
    UkgApiError,
    TravelPerkApiError,
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    NotFoundError,
    ConflictError,
    TimeoutError,
    ServerError,
)
from .business_exceptions import (
    UserValidationError,
    EmployeeNotFoundError,
    SupervisorNotFoundError,
)

__all__ = [
    # API Exceptions
    "ApiError",
    "UkgApiError",
    "TravelPerkApiError",
    "AuthenticationError",
    "RateLimitError",
    "BadRequestError",
    "NotFoundError",
    "ConflictError",
    "TimeoutError",
    "ServerError",
    # Business Exceptions
    "UserValidationError",
    "EmployeeNotFoundError",
    "SupervisorNotFoundError",
]
