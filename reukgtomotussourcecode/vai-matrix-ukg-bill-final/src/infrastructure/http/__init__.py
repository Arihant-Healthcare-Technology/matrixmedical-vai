"""
HTTP client infrastructure with retry logic and response handling.

This module provides a centralized HTTP client that extracts duplicated
code from upsert-bill-entity.py, upsert-bill-vendor.py, etc.
"""

from src.infrastructure.http.retry import RetryStrategy, ExponentialBackoff
from src.infrastructure.http.response import ResponseHandler, safe_json
from src.infrastructure.http.client import HttpClient, BillHttpClient, UKGHttpClient

__all__ = [
    # Retry strategies
    "RetryStrategy",
    "ExponentialBackoff",
    # Response handling
    "ResponseHandler",
    "safe_json",
    # HTTP clients
    "HttpClient",
    "BillHttpClient",
    "UKGHttpClient",
]
