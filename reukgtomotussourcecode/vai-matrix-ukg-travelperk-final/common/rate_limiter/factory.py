"""
Rate limiter factory.

Provides pre-configured rate limiters for different integrations.
"""

import os
from typing import Dict

from .token_bucket import RateLimiter


# Pre-configured rate limiters for each integration
_rate_limiters: Dict[str, RateLimiter] = {}


def _get_integration_configs() -> Dict[str, Dict]:
    """
    Get integration configurations with environment variable overrides.

    Environment variables:
        BILL_RATE_LIMIT: Rate limit for Bill.com (default: 60)
        MOTUS_RATE_LIMIT: Rate limit for Motus (default: 100)
        TRAVELPERK_RATE_LIMIT: Rate limit for TravelPerk (default: 200)
    """
    return {
        "bill": {
            "calls_per_minute": int(os.getenv("BILL_RATE_LIMIT", "60")),
            "name": "bill.com",
        },
        "motus": {
            "calls_per_minute": int(os.getenv("MOTUS_RATE_LIMIT", "100")),
            "name": "motus",
        },
        "travelperk": {
            "calls_per_minute": int(os.getenv("TRAVELPERK_RATE_LIMIT", "200")),
            "name": "travelperk",
        },
    }


# Default configurations for integrations (legacy, use _get_integration_configs())
INTEGRATION_CONFIGS = {
    "bill": {"calls_per_minute": 60, "name": "bill.com"},
    "motus": {"calls_per_minute": 100, "name": "motus"},
    "travelperk": {"calls_per_minute": 200, "name": "travelperk"},
}


def get_rate_limiter(integration: str) -> RateLimiter:
    """
    Get a pre-configured rate limiter for an integration.

    Rate limits can be configured via environment variables:
        - TRAVELPERK_RATE_LIMIT: TravelPerk API (default: 200 calls/min)
        - BILL_RATE_LIMIT: Bill.com API (default: 60 calls/min)
        - MOTUS_RATE_LIMIT: Motus API (default: 100 calls/min)

    Args:
        integration: One of 'bill', 'motus', 'travelperk'

    Returns:
        Configured RateLimiter instance

    Raises:
        ValueError: If integration is not recognized
    """
    configs = _get_integration_configs()

    if integration not in _rate_limiters:
        if integration not in configs:
            raise ValueError(
                f"Unknown integration: {integration}. "
                f"Valid options: {list(configs.keys())}"
            )

        config = configs[integration]
        _rate_limiters[integration] = RateLimiter(**config)

    return _rate_limiters[integration]


def reset_rate_limiters() -> None:
    """Reset all rate limiters (useful for testing)."""
    global _rate_limiters
    _rate_limiters = {}


def register_integration(
    name: str,
    calls_per_minute: int,
    display_name: str = None,
) -> None:
    """
    Register a new integration configuration.

    Args:
        name: Integration key
        calls_per_minute: Rate limit
        display_name: Optional display name for logging
    """
    INTEGRATION_CONFIGS[name] = {
        "calls_per_minute": calls_per_minute,
        "name": display_name or name,
    }
