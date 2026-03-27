"""
HTTP response handling utilities.

This module extracts the duplicated response handling code from:
- upsert-bill-entity.py (lines 86-90: safe_json, lines 92-98: fail)
- upsert-bill-vendor.py (lines 88-92, 95-100)
- upsert-bill-invoice.py (lines 88-92, 95-100)
- process-bill-payment.py (lines 106-110, 113-118)
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

import requests

from src.domain.exceptions import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

logger = logging.getLogger(__name__)


def safe_json(response: requests.Response) -> Any:
    """
    Safely extract JSON from a response, with fallback for invalid JSON.

    This is the extracted version of safe_json() that was duplicated
    across multiple files.

    Args:
        response: The requests Response object

    Returns:
        Parsed JSON data, or a fallback dict with truncated text
    """
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        # Return truncated text for debugging
        return {"_raw_text": response.text[:500] if response.text else ""}


def extract_error_message(response_body: Any) -> str:
    """
    Extract error message from various API response formats.

    Different APIs return errors in different formats:
    - {"message": "..."} - Common format
    - {"error": {"message": "..."}} - Nested format
    - {"errors": [{"message": "..."}]} - Array format
    - {"detail": "..."} - FastAPI format

    Args:
        response_body: Parsed JSON response body

    Returns:
        Extracted error message or generic message
    """
    if not isinstance(response_body, dict):
        return str(response_body)[:500] if response_body else "Unknown error"

    # Try common error message locations
    if "message" in response_body:
        return str(response_body["message"])

    if "error" in response_body:
        error = response_body["error"]
        if isinstance(error, dict) and "message" in error:
            return str(error["message"])
        return str(error)

    if "errors" in response_body:
        errors = response_body["errors"]
        if isinstance(errors, list) and errors:
            first_error = errors[0]
            if isinstance(first_error, dict) and "message" in first_error:
                return str(first_error["message"])
            return str(first_error)

    if "detail" in response_body:
        return str(response_body["detail"])

    # Fallback to stringified response
    return json.dumps(response_body)[:500]


class ResponseHandler:
    """
    Centralized response handling with error conversion.

    This class handles the common response patterns found across
    all upsert-*.py files, converting HTTP errors to typed exceptions.
    """

    def __init__(
        self,
        redact_response: bool = True,
        max_response_length: int = 1000,
    ) -> None:
        """
        Initialize response handler.

        Args:
            redact_response: Whether to redact sensitive data in error messages
            max_response_length: Max length of response body in error details
        """
        self.redact_response = redact_response
        self.max_response_length = max_response_length

    def handle_response(
        self,
        response: requests.Response,
        expected_status: Optional[Union[int, List[int]]] = None,
    ) -> Any:
        """
        Handle HTTP response, raising appropriate exceptions for errors.

        This is the replacement for the duplicated fail() functions.

        Args:
            response: The requests Response object
            expected_status: Expected successful status code(s), defaults to [200, 201, 204]

        Returns:
            Parsed JSON response body for successful requests

        Raises:
            AuthenticationError: For 401/403 responses
            NotFoundError: For 404 responses
            ConflictError: For 409 responses
            RateLimitError: For 429 responses
            BadRequestError: For 400 responses
            ServerError: For 5xx responses
            ApiError: For other error responses
        """
        if expected_status is None:
            expected_status = [200, 201, 204]
        elif isinstance(expected_status, int):
            expected_status = [expected_status]

        status = response.status_code

        # Success case
        if status in expected_status:
            if status == 204:
                return None  # No content
            return safe_json(response)

        # Error case - parse response and raise appropriate exception
        body = safe_json(response)
        message = extract_error_message(body)
        response_text = response.text[:self.max_response_length] if response.text else ""

        # Authentication errors
        if status in (401, 403):
            raise AuthenticationError(
                message=f"Authentication failed: {message}",
                provider="BILL" if "bill" in response.url.lower() else "API",
                details={"status_code": status, "url": response.url},
            )

        # Not found
        if status == 404:
            raise NotFoundError(
                message=f"Resource not found: {message}",
                url=response.url,
            )

        # Conflict (duplicate)
        if status == 409:
            raise ConflictError(
                message=f"Conflict: {message}",
                url=response.url,
                details={"response_body": body},
            )

        # Rate limit
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                message=f"Rate limit exceeded: {message}",
                retry_after=int(retry_after) if retry_after and retry_after.isdigit() else None,
            )

        # Bad request
        if status == 400:
            raise BadRequestError(
                message=f"Bad request: {message}",
                url=response.url,
                method=response.request.method if response.request else None,
                response_body=response_text,
                validation_errors=body.get("errors") if isinstance(body, dict) else None,
            )

        # Server errors
        if 500 <= status < 600:
            raise ServerError(
                message=f"Server error: {message}",
                status_code=status,
                url=response.url,
                method=response.request.method if response.request else None,
                response_body=response_text,
            )

        # Generic API error for other status codes
        raise ApiError(
            message=f"API error ({status}): {message}",
            status_code=status,
            url=response.url,
            method=response.request.method if response.request else None,
            response_body=response_text,
        )

    def fail(self, response: requests.Response) -> None:
        """
        Legacy-compatible fail function.

        This raises an exception for any response, used when you know
        the response is an error.

        Replaces the duplicated fail() functions in upsert-*.py files.
        """
        self.handle_response(response, expected_status=[])


# Module-level convenience instances
_default_handler = ResponseHandler()


def handle_response(
    response: requests.Response,
    expected_status: Optional[Union[int, List[int]]] = None,
) -> Any:
    """Module-level convenience function for response handling."""
    return _default_handler.handle_response(response, expected_status)


def fail(response: requests.Response) -> None:
    """Legacy-compatible fail function."""
    _default_handler.fail(response)
