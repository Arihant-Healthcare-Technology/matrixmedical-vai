"""Domain exceptions - Business and API exceptions."""

from .api_exceptions import (
    ApiError,
    AuthenticationError,
    MotusApiError,
    RateLimitError,
    UkgApiError,
)
from .business_exceptions import (
    DriverValidationError,
    EmployeeNotFoundError,
    ProgramNotFoundError,
)

__all__ = [
    # API exceptions
    "ApiError",
    "UkgApiError",
    "MotusApiError",
    "AuthenticationError",
    "RateLimitError",
    # Business exceptions
    "DriverValidationError",
    "EmployeeNotFoundError",
    "ProgramNotFoundError",
]
