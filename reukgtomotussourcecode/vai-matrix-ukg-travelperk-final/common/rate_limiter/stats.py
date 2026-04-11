"""
Rate limiter statistics.

Provides statistics tracking for rate limiter monitoring.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RateLimitStats:
    """Statistics for rate limiter monitoring."""

    total_requests: int = 0
    total_wait_time: float = 0.0
    max_wait_time: float = 0.0
    throttled_requests: int = 0
    start_time: datetime = None

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()

    @property
    def average_wait_time(self) -> float:
        """Get average wait time per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_wait_time / self.total_requests

    @property
    def throttle_rate(self) -> float:
        """Get percentage of throttled requests."""
        if self.total_requests == 0:
            return 0.0
        return self.throttled_requests / self.total_requests

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> dict:
        """Convert stats to dictionary."""
        return {
            "total_requests": self.total_requests,
            "throttled_requests": self.throttled_requests,
            "throttle_rate": f"{self.throttle_rate:.2%}",
            "total_wait_time_seconds": round(self.total_wait_time, 3),
            "average_wait_time_seconds": round(self.average_wait_time, 5),
            "max_wait_time_seconds": round(self.max_wait_time, 3),
            "uptime_seconds": self.uptime_seconds,
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.max_wait_time = 0.0
        self.throttled_requests = 0
        self.start_time = datetime.now()
