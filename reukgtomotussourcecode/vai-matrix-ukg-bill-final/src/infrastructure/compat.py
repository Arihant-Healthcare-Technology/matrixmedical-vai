"""
Backward compatibility shims for legacy scripts.

This module provides function signatures matching the old code in:
- upsert-bill-entity.py
- upsert-bill-vendor.py
- upsert-bill-invoice.py
- process-bill-payment.py

Legacy scripts can import from here to use the new infrastructure
while maintaining the same API.

Usage in legacy scripts:
    # Old imports (deprecated):
    # from upsert_bill_entity import headers, safe_json, fail, backoff_sleep

    # New imports (using compatibility layer):
    from src.infrastructure.compat import (
        bill_headers,
        safe_json,
        fail,
        backoff_sleep,
        get_bill_client,
    )
"""

import os
import warnings
from typing import Any, Callable, Dict, Optional

import requests

from src.infrastructure.http.retry import backoff_sleep as _backoff_sleep
from src.infrastructure.http.response import (
    ResponseHandler,
    safe_json as _safe_json,
)
from src.infrastructure.http.client import BillHttpClient


# Global response handler for fail()
_response_handler = ResponseHandler()


def safe_json(response: requests.Response) -> Any:
    """
    Backward compatible safe_json function.

    Replaces the duplicated safe_json() functions in upsert-*.py files.
    """
    return _safe_json(response)


def fail(response: requests.Response) -> None:
    """
    Backward compatible fail function.

    Replaces the duplicated fail() functions in upsert-*.py files.
    Raises appropriate exception based on response status.
    """
    _response_handler.fail(response)


def backoff_sleep(attempt: int) -> None:
    """
    Backward compatible backoff_sleep function.

    Replaces the duplicated backoff_sleep() functions:
        def backoff_sleep(attempt: int):
            time.sleep(2 ** attempt)
    """
    _backoff_sleep(attempt, factor=2.0)


def bill_headers(api_token: Optional[str] = None) -> Dict[str, str]:
    """
    Backward compatible headers function for BILL API.

    Replaces the duplicated headers() functions:
        def headers() -> Dict[str, str]:
            return {
                "apiToken": BILL_API_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

    Args:
        api_token: API token (uses env var if not provided)

    Returns:
        Headers dict for BILL API requests
    """
    token = api_token or os.getenv("BILL_API_TOKEN", "")
    if not token:
        raise SystemExit("Missing BILL_API_TOKEN env var")

    return {
        "apiToken": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def ukg_headers(
    basic_b64: Optional[str] = None,
    customer_api_key: Optional[str] = None,
) -> Dict[str, str]:
    """
    Backward compatible headers function for UKG API.

    Args:
        basic_b64: Base64-encoded Basic auth token
        customer_api_key: UKG Customer API key

    Returns:
        Headers dict for UKG API requests
    """
    token = basic_b64 or os.getenv("UKG_BASIC_B64", "")
    key = customer_api_key or os.getenv("UKG_CUSTOMER_API_KEY", "")

    if not token or not key:
        raise SystemExit("Missing UKG_BASIC_B64 or UKG_CUSTOMER_API_KEY env var")

    return {
        "Authorization": f"Basic {token}",
        "US-Customer-Api-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# Cached client instances
_bill_client: Optional[BillHttpClient] = None


def get_bill_client(
    api_base: Optional[str] = None,
    api_token: Optional[str] = None,
    rate_limiter: Optional[Any] = None,
) -> BillHttpClient:
    """
    Get or create a BILL HTTP client.

    This provides a singleton-like pattern for scripts that make
    multiple API calls.

    Args:
        api_base: BILL API base URL (uses env var if not provided)
        api_token: API token (uses env var if not provided)
        rate_limiter: Optional rate limiter

    Returns:
        BillHttpClient instance
    """
    global _bill_client

    if _bill_client is None:
        base = api_base or os.getenv(
            "BILL_API_BASE",
            "https://gateway.stage.bill.com/connect/v3/spend"
        )
        token = api_token or os.getenv("BILL_API_TOKEN", "")

        _bill_client = BillHttpClient(
            api_base=base,
            api_token=token,
            rate_limiter=rate_limiter,
        )

    return _bill_client


def reset_bill_client() -> None:
    """Reset the cached BILL client (useful for testing)."""
    global _bill_client
    if _bill_client:
        _bill_client.close()
    _bill_client = None


# Deprecation wrapper for old imports
def _deprecated(func: Callable, old_name: str, new_location: str) -> Callable:
    """Wrap a function with a deprecation warning."""
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"{old_name} is deprecated. Use {new_location} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)
    return wrapper


# Aliases matching old function names (with deprecation warnings)
headers = _deprecated(bill_headers, "headers()", "bill_headers() or BillHttpClient")


# For scripts that do `from compat import *`
__all__ = [
    "safe_json",
    "fail",
    "backoff_sleep",
    "bill_headers",
    "ukg_headers",
    "get_bill_client",
    "reset_bill_client",
    "headers",  # Deprecated alias
]
