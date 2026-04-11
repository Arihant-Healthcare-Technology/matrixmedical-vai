"""
TravelPerk API error handling.

Provides error handling logic specific to TravelPerk SCIM API responses.
"""

import logging
from typing import Dict, Any

import requests

from ....domain.exceptions import TravelPerkApiError
from ...http.utils import (
    parse_json_response,
    sanitize_url_for_logging,
    extract_retry_after as _extract_retry_after,
)


logger = logging.getLogger(__name__)


class TravelPerkErrorHandler:
    """Handles TravelPerk API error responses."""

    @staticmethod
    def parse_error_body(response: requests.Response) -> Dict[str, Any]:
        """
        Parse error response body.

        Args:
            response: HTTP response

        Returns:
            Parsed error body or dict with raw text
        """
        return parse_json_response(response)

    @classmethod
    def handle_response(
        cls,
        response: requests.Response,
        url: str,
        context: str = "",
    ) -> None:
        """
        Handle error response from TravelPerk API.

        Args:
            response: HTTP response
            url: Request URL
            context: Additional context for error message

        Raises:
            TravelPerkApiError: For all error responses
        """
        if response.status_code < 400:
            return  # Success

        error_body = cls.parse_error_body(response)
        error_message = (
            error_body.get("detail")
            or error_body.get("message")
            or response.text[:200]
        )

        log_message = (
            f"TravelPerk API error: status={response.status_code} "
            f"url={sanitize_url_for_logging(url)} error={error_message}"
        )
        if context:
            log_message = f"{log_message} context={context}"

        logger.error(log_message)

        raise TravelPerkApiError(
            message=f"TravelPerk API error: {error_message}",
            status_code=response.status_code,
            response_body=error_body,
        )

    @staticmethod
    def extract_retry_after(response: requests.Response, default: int = 60) -> int:
        """
        Extract Retry-After seconds from response headers.

        Args:
            response: HTTP response
            default: Default value if header not present

        Returns:
            Wait time in seconds
        """
        return _extract_retry_after(response, default)
