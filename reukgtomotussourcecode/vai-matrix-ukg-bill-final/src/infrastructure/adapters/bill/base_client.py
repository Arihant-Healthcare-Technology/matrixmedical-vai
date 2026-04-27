"""
BILL.com API base client adapter.

This module provides the base BILL.com API client that is extended
by the S&E and AP adapters.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.domain.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from src.infrastructure.config.constants import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)
from src.infrastructure.http.client import BillHttpClient
from src.infrastructure.http.response import safe_json

logger = logging.getLogger(__name__)


class BillClient:
    """
    Base BILL.com API client.

    Provides common functionality for BILL API operations.
    Extended by SpendExpenseClient and AccountsPayableClient.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """
        Initialize BILL client.

        Args:
            api_base: BILL API base URL
            api_token: BILL API token
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limiter: Optional rate limiter
        """
        if not api_token:
            raise ConfigurationError(
                "Missing BILL API token",
                config_key="BILL_API_TOKEN",
            )

        self._http = BillHttpClient(
            api_base=api_base,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )
        self._api_base = api_base

    def _handle_response(
        self,
        response: Any,
        expected_status: Optional[List[int]] = None,
        request_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle API response and convert to dict.

        Args:
            response: HTTP response object
            expected_status: List of expected status codes
            request_payload: Optional request payload for error logging

        Returns:
            Response data as dict

        Raises:
            AuthenticationError: For 401/403 responses
            NotFoundError: For 404 responses
            RateLimitError: For 429 responses
            ApiError: For other error responses
        """
        expected = expected_status or [200, 201, 204]

        if response.status_code in expected:
            if response.status_code == 204:
                return {}
            return safe_json(response)

        # Handle error responses
        error_data = safe_json(response)
        error_message = self._extract_error_message(error_data)

        # Log detailed request/response for 400 Bad Request errors
        if response.status_code == 400:
            logger.error(
                f"BILL API 400 Bad Request Error:\n"
                f"  URL: {response.url}\n"
                f"  Request Payload: {request_payload}\n"
                f"  Response Body: {error_data}"
            )

        if response.status_code == 401:
            raise AuthenticationError(
                message=f"BILL API authentication failed: {error_message}",
                auth_type="api_token",
            )
        elif response.status_code == 403:
            raise AuthenticationError(
                message=f"BILL API access denied: {error_message}",
                auth_type="api_token",
            )
        elif response.status_code == 404:
            raise NotFoundError(
                message=f"Resource not found: {error_message}",
                status_code=404,
            )
        elif response.status_code == 429:
            raise RateLimitError(
                message=f"BILL API rate limit exceeded: {error_message}",
                limit=60,
                retry_after=60,
            )
        else:
            raise ApiError(
                message=f"BILL API error: {error_message}",
                status_code=response.status_code,
                response_body=error_data,
            )

    @staticmethod
    def _extract_error_message(error_data: Dict[str, Any]) -> str:
        """Extract error message from API response."""
        if isinstance(error_data, dict):
            return (
                error_data.get("message")
                or error_data.get("error")
                or error_data.get("errorMessage")
                or error_data.get("_raw_text", "")[:200]
                or str(error_data)[:200]
            )
        return str(error_data)[:200]

    def _extract_items(
        self,
        data: Any,
        item_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract items list from varying API response formats.

        BILL API returns items in different formats:
        - Direct list
        - {"items": [...]}
        - {"data": [...]}
        - {"users": [...]}
        - etc.

        Args:
            data: Response data
            item_keys: List of keys to check for items

        Returns:
            List of items
        """
        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            return []

        # Check common keys
        keys_to_check = item_keys or [
            "items",
            "data",
            "content",
            "values",
            "results",
        ]

        for key in keys_to_check:
            val = data.get(key)
            if isinstance(val, list):
                return val

        # Single object with ID
        if data.get("id") or data.get("uuid"):
            return [data]

        return []

    def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        item_keys: Optional[List[str]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginate through API results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            item_keys: Keys to extract items from response
            page_size: Page size
            max_pages: Maximum pages to fetch (None = all)

        Returns:
            All items from all pages
        """
        all_items = []
        page = 1
        params = params or {}

        while True:
            # Add delay before EVERY pagination request to avoid rate limiting
            time.sleep(5)

            page_params = {**params, "page": page, "pageSize": page_size}
            response = self._http.get(endpoint, params=page_params)
            data = self._handle_response(response)
            items = self._extract_items(data, item_keys)

            all_items.extend(items)

            # Check if we have more pages
            if len(items) < page_size:
                break

            if max_pages and page >= max_pages:
                break

            page += 1

        return all_items

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> "BillClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
