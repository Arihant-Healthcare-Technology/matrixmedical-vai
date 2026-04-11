"""
Rate Limiter Package.

Implements rate limiting for API calls to ensure compliance
with third-party API rate limits:
- BILL.com: 60 calls/minute
- Motus: Configurable (default 100 calls/minute)
- TravelPerk: Configurable (default 100 calls/minute)

Usage:
    from common.rate_limiter import RateLimiter, get_rate_limiter

    # Get a pre-configured limiter
    bill_limiter = get_rate_limiter('bill')

    # Use before API calls
    bill_limiter.acquire()
    response = requests.post(...)

    # Or use as context manager
    with bill_limiter:
        response = requests.post(...)

    # Or as decorator
    @bill_limiter.rate_limited
    def make_api_call():
        return requests.post(...)

Structure:
- stats.py: RateLimitStats for monitoring
- token_bucket.py: RateLimiter, AdaptiveRateLimiter
- sliding_window.py: SlidingWindowRateLimiter
- factory.py: get_rate_limiter factory function
"""

from .stats import RateLimitStats
from .token_bucket import RateLimiter, AdaptiveRateLimiter
from .sliding_window import SlidingWindowRateLimiter
from .factory import (
    get_rate_limiter,
    reset_rate_limiters,
    register_integration,
    INTEGRATION_CONFIGS,
)

__all__ = [
    # Stats
    "RateLimitStats",
    # Rate limiters
    "RateLimiter",
    "AdaptiveRateLimiter",
    "SlidingWindowRateLimiter",
    # Factory
    "get_rate_limiter",
    "reset_rate_limiters",
    "register_integration",
    "INTEGRATION_CONFIGS",
]
