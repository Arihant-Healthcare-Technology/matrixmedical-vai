"""
Base HTTP client with common patterns for API integrations.

Provides reusable functionality for:
- Request/response logging with timing
- Retry logic with exponential backoff
- Rate limiting integration
- Error handling
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, TypeVar

import requests

from common import sanitize_for_logging, get_rate_limiter, RateLimiter
from .utils import parse_json_response, sanitize_url_for_logging


logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseHTTPClient(ABC):
    """
    Abstract base class for HTTP API clients.

    Provides common functionality:
    - Request/response logging with timing
    - Retry logic with exponential backoff
    - Rate limiting integration
    - JSON response handling
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        rate_limiter: Optional[RateLimiter] = None,
        debug: bool = False,
    ):
        """
        Initialize base HTTP client.

        Args:
            base_url: Base URL for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limiter: Optional rate limiter instance
            debug: Enable debug logging
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter
        self.debug = debug
        self._client_name = self.__class__.__name__

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _handle_error_response(
        self,
        response: requests.Response,
        url: str,
    ) -> None:
        """Handle error responses. Must be implemented by subclasses."""
        pass

    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.base_url}/{path.lstrip('/')}"

    def _log_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict] = None,
    ) -> float:
        """
        Log API request and return start time for timing.

        Args:
            method: HTTP method
            url: Request URL
            payload: Optional request payload

        Returns:
            Start time for calculating elapsed time
        """
        start_time = time.time()
        safe_url = sanitize_url_for_logging(url)

        if payload:
            safe_payload = sanitize_for_logging(payload)
            logger.info(
                f"{self._client_name} request: {method} {safe_url} "
                f"payload_keys={list(safe_payload.keys()) if isinstance(safe_payload, dict) else 'N/A'}"
            )
        else:
            logger.info(f"{self._client_name} request: {method} {safe_url}")

        if self.debug:
            logger.debug(f"{self._client_name} full URL: {url}")

        return start_time

    def _log_response(
        self,
        method: str,
        url: str,
        status: int,
        start_time: float,
        data: Any = None,
    ) -> None:
        """
        Log API response with timing.

        Args:
            method: HTTP method
            url: Request URL
            status: HTTP status code
            start_time: Request start time
            data: Optional response data
        """
        elapsed_ms = (time.time() - start_time) * 1000
        safe_url = sanitize_url_for_logging(url)

        if status < 400:
            logger.info(
                f"{self._client_name} response: {method} {safe_url} "
                f"status={status} elapsed={elapsed_ms:.0f}ms"
            )
        else:
            logger.warning(
                f"{self._client_name} response: {method} {safe_url} "
                f"status={status} elapsed={elapsed_ms:.0f}ms"
            )

        if self.debug and data:
            if isinstance(data, dict):
                logger.debug(
                    f"{self._client_name} response body keys: {list(data.keys())[:10]}"
                )
            elif isinstance(data, list):
                logger.debug(f"{self._client_name} response body: list len={len(data)}")

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        """
        Safely parse JSON response.

        Args:
            response: HTTP response

        Returns:
            Parsed JSON or dict with raw text on failure
        """
        return parse_json_response(response)

    def _should_retry(
        self,
        status_code: int,
        attempt: int,
    ) -> bool:
        """
        Determine if request should be retried.

        Args:
            status_code: HTTP status code
            attempt: Current attempt number (0-indexed)

        Returns:
            True if request should be retried
        """
        if attempt >= self.max_retries:
            return False

        # Retry on server errors and rate limits
        return status_code in (429, 500, 502, 503, 504)

    def _get_retry_wait_time(
        self,
        response: requests.Response,
        attempt: int,
    ) -> float:
        """
        Calculate wait time before retry.

        Args:
            response: HTTP response
            attempt: Current attempt number

        Returns:
            Wait time in seconds
        """
        if response.status_code == 429:
            # Use Retry-After header if available
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
            return 60.0  # Default for rate limit

        # Exponential backoff for server errors
        return 2 ** attempt

    def _acquire_rate_limit(self) -> None:
        """Acquire rate limit token if rate limiter is configured."""
        if self.rate_limiter:
            self.rate_limiter.acquire()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            path: API endpoint path
            params: Query parameters
            json_data: JSON request body
            headers: Additional headers

        Returns:
            HTTP response

        Raises:
            Exception from _handle_error_response on failure
        """
        url = self._build_url(path)
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        for attempt in range(self.max_retries + 1):
            self._acquire_rate_limit()
            start_time = self._log_request(method, url, json_data)

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{self._client_name} timeout: {method} {path} "
                    f"elapsed={elapsed_ms:.0f}ms timeout={self.timeout}s"
                )
                raise
            except requests.exceptions.ConnectionError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{self._client_name} connection error: {method} {path} "
                    f"elapsed={elapsed_ms:.0f}ms error={e}"
                )
                raise

            data = self._safe_json(response) if response.status_code < 400 else None
            self._log_response(method, url, response.status_code, start_time, data)

            # Check if we should retry
            if self._should_retry(response.status_code, attempt):
                wait_time = self._get_retry_wait_time(response, attempt)
                logger.warning(
                    f"{self._client_name} retrying: status={response.status_code} "
                    f"attempt={attempt + 1}/{self.max_retries} wait={wait_time:.1f}s"
                )
                time.sleep(wait_time)
                continue

            # Handle error responses
            if response.status_code >= 400:
                self._handle_error_response(response, url)

            return response

        # Should not reach here, but handle max retries exceeded
        logger.error(f"{self._client_name} max retries exceeded: {method} {url}")
        raise Exception(f"Max retries exceeded for {method} {url}")

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make GET request."""
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make POST request."""
        return self._request("POST", path, params=params, json_data=json_data)

    def patch(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make PATCH request."""
        return self._request("PATCH", path, json_data=json_data)

    def put(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make PUT request."""
        return self._request("PUT", path, json_data=json_data)

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make DELETE request."""
        return self._request("DELETE", path, params=params)
