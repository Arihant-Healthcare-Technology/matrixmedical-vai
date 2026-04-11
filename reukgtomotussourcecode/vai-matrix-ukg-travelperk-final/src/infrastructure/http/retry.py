"""
Retry utilities for HTTP requests.

Provides decorators and utilities for implementing retry logic
with exponential backoff.
"""

import logging
import time
from functools import wraps
from typing import Callable, Optional, Set, Tuple, Type, TypeVar, Union

import requests

from ...domain.exceptions import RateLimitError, ServerError, TimeoutError


logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retryable status codes
DEFAULT_RETRYABLE_STATUS_CODES: Set[int] = {408, 429, 500, 502, 503, 504}

# Default retryable exceptions
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    RateLimitError,
    ServerError,
    TimeoutError,
)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_status_codes: Optional[Set[int]] = None,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff calculation
            retryable_status_codes: Set of HTTP status codes to retry on
            retryable_exceptions: Tuple of exception types to retry on
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_status_codes = (
            retryable_status_codes or DEFAULT_RETRYABLE_STATUS_CODES
        )
        self.retryable_exceptions = (
            retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS
        )

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt using exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)

    def is_retryable_status(self, status_code: int) -> bool:
        """Check if status code is retryable."""
        return status_code in self.retryable_status_codes

    def is_retryable_exception(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        return isinstance(exception, self.retryable_exceptions)


def with_retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic to a function.

    Args:
        config: Retry configuration
        on_retry: Optional callback called before each retry

    Returns:
        Decorated function with retry logic

    Usage:
        @with_retry(RetryConfig(max_retries=3))
        def make_api_call():
            return requests.get(url)
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not config.is_retryable_exception(e):
                        raise

                    if attempt >= config.max_retries:
                        raise

                    delay = config.calculate_delay(attempt)

                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                        f"{type(e).__name__} - {e}. Waiting {delay:.1f}s"
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(delay)

            # Should not reach here, but raise last exception if we do
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


def retry_on_rate_limit(
    max_retries: int = 3,
    default_wait: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator specifically for handling rate limit (429) responses.

    Args:
        max_retries: Maximum number of retry attempts
        default_wait: Default wait time if Retry-After not provided

    Returns:
        Decorated function with rate limit retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    if attempt >= max_retries:
                        raise

                    wait_time = getattr(e, "retry_after", default_wait)
                    logger.warning(
                        f"Rate limited, waiting {wait_time}s before retry "
                        f"{attempt + 1}/{max_retries}"
                    )
                    time.sleep(wait_time)

            raise RuntimeError("Unexpected state in rate limit retry logic")

        return wrapper

    return decorator


def get_retry_after_seconds(
    response: requests.Response,
    default: float = 60.0,
) -> float:
    """
    Extract retry-after seconds from HTTP response.

    Args:
        response: HTTP response
        default: Default value if header not present or invalid

    Returns:
        Wait time in seconds
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return default
