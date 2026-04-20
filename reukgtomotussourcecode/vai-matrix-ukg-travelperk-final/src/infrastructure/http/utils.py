"""
Shared HTTP utilities.

Provides common functions used across HTTP clients and error handlers.
"""

import logging
from typing import Any, Dict

import requests


logger = logging.getLogger(__name__)


def parse_json_response(response: requests.Response) -> Dict[str, Any]:
    """
    Safely parse JSON from HTTP response.

    Args:
        response: HTTP response object

    Returns:
        Parsed JSON dict, or dict with raw text on parse failure
    """
    try:
        return response.json()
    except Exception as e:
        logger.warning(f"Failed to parse JSON response: {type(e).__name__}: {e}")
        return {"raw_text": response.text[:500], "parse_error": str(e)}


def sanitize_url_for_logging(url: str) -> str:
    """
    Remove query parameters from URL for safe logging.

    Args:
        url: Full URL potentially containing query params

    Returns:
        URL path without query parameters
    """
    return url.split("?")[0]


def extract_retry_after(response: requests.Response, default: int = 60) -> int:
    """
    Extract Retry-After seconds from response headers.

    Args:
        response: HTTP response
        default: Default value if header not present or invalid

    Returns:
        Wait time in seconds
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            logger.debug(f"Invalid Retry-After header value: {retry_after}, using default: {default}")
    return default
