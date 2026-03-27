"""
Domain exceptions - Custom exception hierarchy for the integration suite.

All exceptions inherit from IntegrationError, allowing for consistent
error handling across the application.
"""

from src.domain.exceptions.base import (
    IntegrationError,
    ConfigurationError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from src.domain.exceptions.api_exceptions import (
    ApiError,
    NotFoundError,
    ConflictError,
    TimeoutError,
    ServerError,
    BadRequestError,
)
from src.domain.exceptions.business_exceptions import (
    EmployeeValidationError,
    EmployeeSyncError,
    VendorCreationError,
    InvoiceProcessingError,
    PaymentAuthorizationError,
    BudgetAssignmentError,
    CostCenterMappingError,
)

__all__ = [
    # Base exceptions
    "IntegrationError",
    "ConfigurationError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    # API exceptions
    "ApiError",
    "NotFoundError",
    "ConflictError",
    "TimeoutError",
    "ServerError",
    "BadRequestError",
    # Business exceptions
    "EmployeeValidationError",
    "EmployeeSyncError",
    "VendorCreationError",
    "InvoiceProcessingError",
    "PaymentAuthorizationError",
    "BudgetAssignmentError",
    "CostCenterMappingError",
]
