"""
Base HTTP client with retry logic and standardized error handling.

This module extracts the duplicated HTTP code from:
- upsert-bill-entity.py (headers, API calls, error handling)
- upsert-bill-vendor.py
- upsert-bill-invoice.py
- process-bill-payment.py
- build-bill-entity.py (UKG API calls)
"""

import logging
from typing import Any, Callable, Dict, Optional

import requests

from src.domain.exceptions import (
    ApiError,
    ConfigurationError,
    TimeoutError as IntegrationTimeoutError,
)
from src.infrastructure.config.constants import (
    CONTENT_TYPE_JSON,
    ACCEPT_JSON,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)
from src.infrastructure.http.retry import ExponentialBackoff, RetryStrategy
from src.infrastructure.http.response import ResponseHandler, safe_json

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Base HTTP client with retry logic and standardized error handling.

    This is a reusable HTTP client that can be extended for specific APIs
    (BILL, UKG, etc.).
    """

    def __init__(
        self,
        base_url: str,
        headers_func: Optional[Callable[[], Dict[str, str]]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_strategy: Optional[RetryStrategy] = None,
        response_handler: Optional[ResponseHandler] = None,
        rate_limiter: Optional[Any] = None,  # Type hint for rate limiter
    ) -> None:
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            headers_func: Function that returns headers dict (called fresh each request)
            timeout: Default request timeout in seconds
            retry_strategy: Retry strategy (defaults to ExponentialBackoff)
            response_handler: Response handler (defaults to ResponseHandler)
            rate_limiter: Optional rate limiter to apply before requests
        """
        self.base_url = base_url.rstrip("/")
        self._headers_func = headers_func or (lambda: {})
        self.timeout = timeout
        self.retry_strategy = retry_strategy or ExponentialBackoff()
        self.response_handler = response_handler or ResponseHandler()
        self.rate_limiter = rate_limiter
        self.session = requests.Session()

    def headers(self) -> Dict[str, str]:
        """
        Get request headers.

        This method can be overridden in subclasses or configured via headers_func.
        """
        base_headers = {
            "Content-Type": CONTENT_TYPE_JSON,
            "Accept": ACCEPT_JSON,
        }
        custom_headers = self._headers_func()
        return {**base_headers, **custom_headers}

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting if configured."""
        if self.rate_limiter:
            self.rate_limiter.acquire()

    def _make_request(
        self,
        method: str,
        url: str,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Make an HTTP request with rate limiting.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            url: Full URL or path (will be prefixed with base_url if relative)
            timeout: Request timeout (uses default if not specified)
            **kwargs: Additional arguments passed to requests

        Returns:
            requests.Response object
        """
        # Ensure URL is absolute
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"

        # Apply rate limiting
        self._apply_rate_limit()

        # Merge headers
        request_headers = self.headers()
        if "headers" in kwargs:
            request_headers.update(kwargs.pop("headers"))

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=request_headers,
                timeout=timeout or self.timeout,
                **kwargs,
            )
            return response
        except requests.exceptions.Timeout as e:
            raise IntegrationTimeoutError(
                message=f"Request timed out after {timeout or self.timeout}s",
                timeout_seconds=timeout or self.timeout,
                url=url,
                method=method,
            ) from e
        except requests.exceptions.RequestException as e:
            raise ApiError(
                message=f"Request failed: {str(e)}",
                url=url,
                method=method,
            ) from e

    def _request_with_retry(
        self,
        method: str,
        url: str,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Make request with retry logic.

        This implements the retry pattern that was duplicated across
        all upsert-*.py files.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.retry_strategy.max_retries + 1):
            try:
                response = self._make_request(method, url, timeout, **kwargs)

                # Check if we should retry based on status code
                if (
                    isinstance(self.retry_strategy, ExponentialBackoff)
                    and self.retry_strategy.is_retryable_status(response.status_code)
                    and attempt < self.retry_strategy.max_retries
                ):
                    logger.warning(
                        f"{method} {url} returned {response.status_code}, "
                        f"retry {attempt + 1}/{self.retry_strategy.max_retries}"
                    )
                    self.retry_strategy.sleep(attempt)
                    continue

                return response

            except IntegrationTimeoutError:
                # Timeouts are retryable
                if attempt < self.retry_strategy.max_retries:
                    logger.warning(
                        f"{method} {url} timed out, "
                        f"retry {attempt + 1}/{self.retry_strategy.max_retries}"
                    )
                    self.retry_strategy.sleep(attempt)
                    continue
                raise

            except Exception as e:
                last_exception = e
                if not self.retry_strategy.should_retry(attempt, e):
                    raise
                logger.warning(
                    f"{method} {url} failed with {type(e).__name__}, "
                    f"retry {attempt + 1}/{self.retry_strategy.max_retries}"
                )
                self.retry_strategy.sleep(attempt)

        # This shouldn't happen, but handle it gracefully
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic failed unexpectedly")

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make GET request with retry."""
        return self._request_with_retry("GET", url, timeout, params=params, **kwargs)

    def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make POST request with retry."""
        return self._request_with_retry("POST", url, timeout, json=json, data=data, **kwargs)

    def patch(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make PATCH request with retry."""
        return self._request_with_retry("PATCH", url, timeout, json=json, **kwargs)

    def delete(
        self,
        url: str,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make DELETE request with retry."""
        return self._request_with_retry("DELETE", url, timeout, **kwargs)

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class BillHttpClient(HttpClient):
    """
    BILL.com API HTTP client.

    Extracts the common BILL API patterns from upsert-bill-entity.py,
    upsert-bill-vendor.py, etc.
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
        Initialize BILL HTTP client.

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

        self._api_token = api_token

        super().__init__(
            base_url=api_base,
            timeout=timeout,
            retry_strategy=ExponentialBackoff(max_retries=max_retries),
            rate_limiter=rate_limiter,
        )

    def headers(self) -> Dict[str, str]:
        """
        Get BILL API headers.

        This is the extracted version of headers() from upsert-bill-entity.py:
            def headers() -> Dict[str, str]:
                return {
                    "apiToken": BILL_API_TOKEN,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
        """
        return {
            "apiToken": self._api_token,
            "Content-Type": CONTENT_TYPE_JSON,
            "Accept": ACCEPT_JSON,
        }


class UKGHttpClient(HttpClient):
    """
    UKG Pro API HTTP client.

    Extracts the common UKG API patterns from build-bill-entity.py.
    """

    def __init__(
        self,
        base_url: str,
        basic_auth_token: str,
        customer_api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """
        Initialize UKG HTTP client.

        Args:
            base_url: UKG API base URL
            basic_auth_token: Base64-encoded Basic auth token
            customer_api_key: UKG Customer API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limiter: Optional rate limiter
        """
        if not basic_auth_token:
            raise ConfigurationError(
                "Missing UKG Basic auth token",
                config_key="UKG_BASIC_B64",
            )
        if not customer_api_key:
            raise ConfigurationError(
                "Missing UKG Customer API key",
                config_key="UKG_CUSTOMER_API_KEY",
            )

        self._basic_auth_token = basic_auth_token
        self._customer_api_key = customer_api_key

        super().__init__(
            base_url=base_url,
            timeout=timeout,
            retry_strategy=ExponentialBackoff(max_retries=max_retries),
            rate_limiter=rate_limiter,
        )

    def headers(self) -> Dict[str, str]:
        """
        Get UKG API headers.

        This is the extracted version of headers() from build-bill-entity.py.
        """
        return {
            "Authorization": f"Basic {self._basic_auth_token}",
            "US-Customer-Api-Key": self._customer_api_key,
            "Content-Type": CONTENT_TYPE_JSON,
            "Accept": ACCEPT_JSON,
        }
