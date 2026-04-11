"""
HTTP utilities for API integrations.

This module provides reusable components for HTTP API clients:
- BaseHTTPClient: Abstract base class with common patterns
- RetryConfig: Configuration for retry behavior
- Retry decorators and utilities
- Shared utilities for JSON parsing and URL sanitization
"""

from .base_client import BaseHTTPClient
from .retry import (
    RetryConfig,
    with_retry,
    retry_on_rate_limit,
    get_retry_after_seconds,
    DEFAULT_RETRYABLE_STATUS_CODES,
    DEFAULT_RETRYABLE_EXCEPTIONS,
)
from .utils import (
    parse_json_response,
    sanitize_url_for_logging,
    extract_retry_after,
)

__all__ = [
    # Base client
    "BaseHTTPClient",
    # Retry utilities
    "RetryConfig",
    "with_retry",
    "retry_on_rate_limit",
    "get_retry_after_seconds",
    "DEFAULT_RETRYABLE_STATUS_CODES",
    "DEFAULT_RETRYABLE_EXCEPTIONS",
    # Shared utilities
    "parse_json_response",
    "sanitize_url_for_logging",
    "extract_retry_after",
]
