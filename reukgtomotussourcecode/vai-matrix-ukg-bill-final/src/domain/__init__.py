"""
Domain layer - Core business entities, exceptions, and interfaces.

This is the innermost layer of the architecture. It has no dependencies
on external frameworks or infrastructure concerns.
"""

from src.domain.exceptions import (
    IntegrationError,
    ConfigurationError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ApiError,
    NotFoundError,
    ConflictError,
    TimeoutError,
)

__all__ = [
    "IntegrationError",
    "ConfigurationError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "ApiError",
    "NotFoundError",
    "ConflictError",
    "TimeoutError",
]
