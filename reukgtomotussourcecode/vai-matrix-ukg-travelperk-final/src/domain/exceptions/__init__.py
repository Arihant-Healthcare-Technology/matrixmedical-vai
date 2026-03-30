"""Domain exceptions."""

from .api_exceptions import (
    ApiError,
    UkgApiError,
    TravelPerkApiError,
    AuthenticationError,
    RateLimitError,
)
from .business_exceptions import (
    UserValidationError,
    EmployeeNotFoundError,
    SupervisorNotFoundError,
)

__all__ = [
    "ApiError",
    "UkgApiError",
    "TravelPerkApiError",
    "AuthenticationError",
    "RateLimitError",
    "UserValidationError",
    "EmployeeNotFoundError",
    "SupervisorNotFoundError",
]
