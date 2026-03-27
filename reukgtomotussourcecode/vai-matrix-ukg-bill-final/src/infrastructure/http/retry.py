"""
Retry strategies with exponential backoff and jitter.

This module extracts the duplicated backoff_sleep() functions from:
- upsert-bill-entity.py (lines 100-102)
- upsert-bill-vendor.py (lines 103-104)
- upsert-bill-invoice.py (lines 103-104)
- process-bill-payment.py (lines 121-122)
"""

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, Set, TypeVar

from src.infrastructure.config.constants import (
    BACKOFF_FACTOR,
    BACKOFF_MAX,
    JITTER_FACTOR,
    MAX_RETRIES,
)

T = TypeVar("T")


class RetryStrategy(ABC):
    """Abstract base class for retry strategies."""

    @abstractmethod
    def should_retry(self, attempt: int, exception: Optional[Exception] = None) -> bool:
        """Determine if another retry should be attempted."""
        pass

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Calculate the delay before the next retry in seconds."""
        pass

    @abstractmethod
    def sleep(self, attempt: int) -> None:
        """Sleep for the calculated delay."""
        pass


@dataclass
class ExponentialBackoff(RetryStrategy):
    """
    Exponential backoff retry strategy with optional jitter.

    This is the extracted and improved version of backoff_sleep() that was
    duplicated across multiple upsert-*.py files.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (default: 1.0)
        factor: Exponential factor (default: 2.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        jitter: Jitter factor (0.1 = add up to 10% random variation)
        retryable_status_codes: HTTP status codes that trigger retry
    """

    max_retries: int = MAX_RETRIES
    base_delay: float = 1.0
    factor: float = BACKOFF_FACTOR
    max_delay: float = BACKOFF_MAX
    jitter: float = JITTER_FACTOR
    retryable_status_codes: Set[int] = None

    def __post_init__(self) -> None:
        if self.retryable_status_codes is None:
            # Default: retry on server errors and rate limits
            self.retryable_status_codes = {429, 500, 502, 503, 504}

    def should_retry(self, attempt: int, exception: Optional[Exception] = None) -> bool:
        """
        Determine if another retry should be attempted.

        Args:
            attempt: Current attempt number (0-indexed)
            exception: The exception that occurred (if any)

        Returns:
            True if retry should be attempted
        """
        return attempt < self.max_retries

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay using exponential backoff with jitter.

        Formula: min(base * factor^attempt + jitter, max_delay)

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Base exponential delay: base * factor^attempt
        delay = self.base_delay * (self.factor ** attempt)

        # Add random jitter to prevent thundering herd
        if self.jitter > 0:
            jitter_amount = delay * self.jitter * random.random()
            delay += jitter_amount

        # Cap at maximum delay
        return min(delay, self.max_delay)

    def sleep(self, attempt: int) -> None:
        """
        Sleep for the calculated backoff delay.

        This is the replacement for the duplicated backoff_sleep() functions.
        """
        delay = self.get_delay(attempt)
        time.sleep(delay)

    def is_retryable_status(self, status_code: int) -> bool:
        """Check if an HTTP status code should trigger a retry."""
        return status_code in self.retryable_status_codes


def with_retry(
    func: Callable[..., T],
    strategy: Optional[RetryStrategy] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[..., T]:
    """
    Decorator/wrapper to add retry logic to a function.

    Args:
        func: The function to wrap
        strategy: Retry strategy to use (defaults to ExponentialBackoff)
        on_retry: Optional callback called before each retry

    Returns:
        Wrapped function with retry logic

    Example:
        @with_retry
        def make_api_call():
            return requests.get(url)

        # Or with custom strategy:
        result = with_retry(make_api_call, ExponentialBackoff(max_retries=5))()
    """
    if strategy is None:
        strategy = ExponentialBackoff()

    def wrapper(*args, **kwargs) -> T:
        last_exception: Optional[Exception] = None

        for attempt in range(strategy.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if not strategy.should_retry(attempt, e):
                    raise

                if on_retry:
                    on_retry(attempt, e)

                strategy.sleep(attempt)

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic failed unexpectedly")

    return wrapper


# Convenience function for backward compatibility
def backoff_sleep(attempt: int, factor: float = BACKOFF_FACTOR) -> None:
    """
    Legacy-compatible backoff sleep function.

    This maintains backward compatibility with existing code that uses:
        backoff_sleep(attempt)

    For new code, use ExponentialBackoff class instead.
    """
    delay = factor ** attempt
    time.sleep(delay)
