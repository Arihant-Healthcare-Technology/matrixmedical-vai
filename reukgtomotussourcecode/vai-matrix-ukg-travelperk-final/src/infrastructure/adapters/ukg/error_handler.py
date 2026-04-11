"""
UKG API error handling.

Provides error handling logic specific to UKG API responses.
"""

import logging
from typing import Dict, Any, Optional

import requests

from ....domain.exceptions import (
    UkgApiError,
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    NotFoundError,
    ServerError,
)
from ...http.utils import parse_json_response, extract_retry_after


logger = logging.getLogger(__name__)


class UKGErrorHandler:
    """Handles UKG API error responses."""

    @staticmethod
    def parse_error_body(response: requests.Response) -> Dict[str, Any]:
        """
        Parse error response body.

        Args:
            response: HTTP response

        Returns:
            Parsed error body or raw text dict
        """
        return parse_json_response(response)

    @staticmethod
    def extract_error_message(error_body: Dict[str, Any], response_text: str) -> str:
        """
        Extract error message from error body.

        Args:
            error_body: Parsed error body
            response_text: Raw response text

        Returns:
            Error message string
        """
        return (
            error_body.get("message")
            or error_body.get("error")
            or response_text[:200]
        )

    @classmethod
    def handle_response(
        cls,
        response: requests.Response,
        url: str,
    ) -> None:
        """
        Handle HTTP response status codes.

        Args:
            response: HTTP response object
            url: Request URL for error messages

        Raises:
            Appropriate exception based on status code
        """
        status = response.status_code

        if status < 400:
            return  # Success

        error_body = cls.parse_error_body(response)
        error_message = cls.extract_error_message(error_body, response.text)

        if status == 400:
            logger.warning(f"UKG bad request: {url} - {error_message}")
            raise BadRequestError(
                message=f"UKG bad request: {error_message}",
                response_body=error_body,
            )

        if status == 401:
            logger.error(f"UKG authentication failed: {url}")
            raise AuthenticationError(
                message="UKG authentication failed - check credentials",
                status_code=401,
            )

        if status == 403:
            logger.error(f"UKG access forbidden: {url}")
            raise AuthenticationError(
                message="UKG access forbidden - check API key permissions",
                status_code=403,
            )

        if status == 404:
            logger.debug(f"UKG resource not found: {url}")
            raise NotFoundError(
                message=f"UKG resource not found: {url}",
                resource_type="employee",
            )

        if status == 429:
            retry_after = extract_retry_after(response, default=60)
            logger.warning(f"UKG rate limit exceeded, retry after {retry_after}s")
            raise RateLimitError(
                message="UKG rate limit exceeded",
                retry_after=retry_after,
            )

        if status >= 500:
            logger.error(f"UKG server error {status}: {url} - {error_message}")
            raise ServerError(
                message=f"UKG server error: {error_message}",
                status_code=status,
                response_body=error_body,
            )

        # Generic error
        logger.error(f"UKG API error {status}: {url} - {error_message}")
        raise UkgApiError(
            message=f"UKG API error: {error_message}",
            status_code=status,
            response_body=error_body,
        )
