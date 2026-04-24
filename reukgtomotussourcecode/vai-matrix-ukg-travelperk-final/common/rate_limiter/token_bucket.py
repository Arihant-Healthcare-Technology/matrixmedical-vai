"""
Token bucket rate limiter implementations.

Provides token bucket algorithm based rate limiters:
- RateLimiter: Basic token bucket implementation
- AdaptiveRateLimiter: Self-adjusting based on API responses
"""

import logging
import threading
import time
from functools import wraps
from typing import Callable, Optional, TypeVar

from .stats import RateLimitStats


logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimiter:
    """
    Token bucket rate limiter implementation.

    Thread-safe rate limiter that uses the token bucket algorithm.
    Tokens are added at a constant rate, and each request consumes one token.
    If no tokens are available, the request blocks until a token is available.
    """

    def __init__(
        self,
        calls_per_minute: int,
        name: str = "default",
        burst_size: Optional[int] = None,
        max_wait_seconds: float = 60.0,
    ):
        """
        Initialize the rate limiter.

        Args:
            calls_per_minute: Maximum number of calls allowed per minute
            name: Identifier for this limiter (for logging)
            burst_size: Maximum burst size (defaults to calls_per_minute)
            max_wait_seconds: Maximum time to wait for a token
        """
        self.name = name
        self.calls_per_minute = calls_per_minute
        self.rate = calls_per_minute / 60.0  # tokens per second
        self.max_tokens = burst_size or calls_per_minute
        self.tokens = float(self.max_tokens)
        self.last_update = time.monotonic()
        self.max_wait_seconds = max_wait_seconds
        self._lock = threading.Lock()
        self._stats = RateLimitStats()

        logger.info(
            f"Rate limiter '{name}' initialized: {calls_per_minute} calls/min, "
            f"burst={self.max_tokens}"
        )

    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time since last update."""
        now = time.monotonic()
        elapsed = now - self.last_update
        new_tokens = elapsed * self.rate
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_update = now

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire (default 1)
            timeout: Maximum time to wait (defaults to max_wait_seconds)

        Returns:
            True if tokens were acquired, False if timeout occurred
        """
        timeout = timeout if timeout is not None else self.max_wait_seconds

        with self._lock:
            self._add_tokens()
            self._stats.total_requests += 1

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate

            if wait_time > timeout:
                logger.warning(
                    f"Rate limiter '{self.name}': Would need to wait {wait_time:.2f}s "
                    f"but timeout is {timeout:.2f}s"
                )
                return False

            # Track throttling stats
            self._stats.throttled_requests += 1
            self._stats.total_wait_time += wait_time
            self._stats.max_wait_time = max(self._stats.max_wait_time, wait_time)

            logger.debug(
                f"Rate limiter '{self.name}': Throttling for {wait_time:.3f}s "
                f"(tokens needed: {tokens_needed:.2f})"
            )

        # Wait outside the lock to allow other threads to proceed
        time.sleep(wait_time)

        with self._lock:
            self._add_tokens()
            self.tokens -= tokens
            return True

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        with self._lock:
            self._add_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                self._stats.total_requests += 1
                return True
            return False

    def wait_time(self, tokens: int = 1) -> float:
        """
        Get estimated wait time for acquiring tokens.

        Args:
            tokens: Number of tokens needed

        Returns:
            Estimated wait time in seconds (0 if tokens are available)
        """
        with self._lock:
            self._add_tokens()

            if self.tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self.tokens
            return tokens_needed / self.rate

    def get_stats(self) -> RateLimitStats:
        """Get current rate limiter statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = RateLimitStats()

    def rate_limited(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to rate limit a function.

        Usage:
            @rate_limiter.rate_limited
            def make_api_call():
                return requests.post(...)
        """

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            self.acquire()
            return func(*args, **kwargs)

        return wrapper

    def __enter__(self) -> "RateLimiter":
        """Context manager entry - acquires a token."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        pass


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on API responses.

    Automatically reduces rate when receiving 429 responses
    and gradually increases when successful.
    """

    def __init__(
        self,
        calls_per_minute: int,
        name: str = "adaptive",
        min_rate: int = 10,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
        recovery_threshold: int = 100,
    ):
        """
        Initialize adaptive rate limiter.

        Args:
            calls_per_minute: Initial/maximum calls per minute
            name: Identifier for this limiter
            min_rate: Minimum calls per minute
            backoff_factor: Multiply rate by this on 429 (default: halve)
            recovery_factor: Multiply rate by this on recovery
            recovery_threshold: Successful calls before increasing rate
        """
        super().__init__(calls_per_minute, name)
        self.max_rate = calls_per_minute
        self.min_rate = min_rate
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.recovery_threshold = recovery_threshold
        self._success_count = 0

    def report_success(self) -> None:
        """Report a successful API call."""
        with self._lock:
            self._success_count += 1
            if self._success_count >= self.recovery_threshold:
                self._increase_rate()
                self._success_count = 0

    def report_rate_limited(self) -> None:
        """Report a 429 rate limit response."""
        with self._lock:
            self._decrease_rate()
            self._success_count = 0

    def _decrease_rate(self) -> None:
        """Decrease the rate after hitting a limit."""
        new_cpm = max(self.min_rate, int(self.calls_per_minute * self.backoff_factor))
        if new_cpm != self.calls_per_minute:
            logger.warning(
                f"Rate limiter '{self.name}': Reducing rate from "
                f"{self.calls_per_minute} to {new_cpm} calls/min"
            )
            self.calls_per_minute = new_cpm
            self.rate = new_cpm / 60.0

    def _increase_rate(self) -> None:
        """Increase the rate after sustained success."""
        new_cpm = min(self.max_rate, int(self.calls_per_minute * self.recovery_factor))
        if new_cpm != self.calls_per_minute:
            logger.info(
                f"Rate limiter '{self.name}': Increasing rate from "
                f"{self.calls_per_minute} to {new_cpm} calls/min"
            )
            self.calls_per_minute = new_cpm
            self.rate = new_cpm / 60.0
