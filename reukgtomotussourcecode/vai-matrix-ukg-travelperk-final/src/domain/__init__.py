"""
Domain Layer.

Contains business entities, interfaces, and exceptions.

Structure:
- models/: Domain entities (TravelPerkUser, etc.)
- interfaces/: Abstract interfaces
- exceptions/: Business and API exceptions
"""

from .models import TravelPerkUser
from .exceptions import (
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
    UserValidationError,
    EmployeeNotFoundError,
    SupervisorNotFoundError,
)

__all__ = [
    # Models
    "TravelPerkUser",
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
