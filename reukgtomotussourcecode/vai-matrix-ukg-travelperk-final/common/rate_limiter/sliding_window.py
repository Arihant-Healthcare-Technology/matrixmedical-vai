"""
Sliding window rate limiter implementation.

More accurate than token bucket for strict rate limiting
but uses more memory to track request timestamps.
"""

import threading
import time
from typing import List

from .stats import RateLimitStats


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter implementation.

    More accurate than token bucket for strict rate limiting
    but uses more memory to track request timestamps.
    """

    def __init__(
        self,
        calls_per_minute: int,
        name: str = "sliding_window",
        window_size_seconds: int = 60,
    ):
        """
        Initialize sliding window rate limiter.

        Args:
            calls_per_minute: Maximum calls allowed in the window
            name: Identifier for this limiter
            window_size_seconds: Size of the sliding window
        """
        self.name = name
        self.max_calls = calls_per_minute
        self.window_size = window_size_seconds
        self._timestamps: List[float] = []
        self._lock = threading.Lock()
        self._stats = RateLimitStats()

    def _cleanup_old_timestamps(self, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - self.window_size
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

    def acquire(self, timeout: float = 60.0) -> bool:
        """
        Acquire permission to make a request.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if permission was acquired, False if timeout
        """
        start_time = time.monotonic()

        while True:
            now = time.monotonic()

            with self._lock:
                self._cleanup_old_timestamps(now)
                self._stats.total_requests += 1

                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return True

                # Calculate when the oldest request will expire
                oldest = self._timestamps[0]
                wait_time = (oldest + self.window_size) - now

                if wait_time <= 0:
                    continue

                if (now - start_time) + wait_time > timeout:
                    return False

                self._stats.throttled_requests += 1
                self._stats.total_wait_time += wait_time
                self._stats.max_wait_time = max(self._stats.max_wait_time, wait_time)

            time.sleep(min(wait_time, 0.1))

    def try_acquire(self) -> bool:
        """
        Try to acquire permission without blocking.

        Returns:
            True if permission was acquired, False otherwise
        """
        now = time.monotonic()

        with self._lock:
            self._cleanup_old_timestamps(now)

            if len(self._timestamps) < self.max_calls:
                self._timestamps.append(now)
                self._stats.total_requests += 1
                return True
            return False

    def wait_time(self) -> float:
        """
        Get estimated wait time.

        Returns:
            Estimated wait time in seconds (0 if permission is available)
        """
        now = time.monotonic()

        with self._lock:
            self._cleanup_old_timestamps(now)

            if len(self._timestamps) < self.max_calls:
                return 0.0

            oldest = self._timestamps[0]
            return max(0.0, (oldest + self.window_size) - now)

    def get_stats(self) -> RateLimitStats:
        """Get current statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = RateLimitStats()

    @property
    def current_count(self) -> int:
        """Get current number of requests in the window."""
        now = time.monotonic()
        with self._lock:
            self._cleanup_old_timestamps(now)
            return len(self._timestamps)
