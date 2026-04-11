"""
Rate limiter factory.

Provides pre-configured rate limiters for different integrations.
"""

from typing import Dict

from .token_bucket import RateLimiter


# Pre-configured rate limiters for each integration
_rate_limiters: Dict[str, RateLimiter] = {}

# Default configurations for integrations
INTEGRATION_CONFIGS = {
    "bill": {"calls_per_minute": 60, "name": "bill.com"},
    "motus": {"calls_per_minute": 100, "name": "motus"},
    "travelperk": {"calls_per_minute": 100, "name": "travelperk"},
}


def get_rate_limiter(integration: str) -> RateLimiter:
    """
    Get a pre-configured rate limiter for an integration.

    Args:
        integration: One of 'bill', 'motus', 'travelperk'

    Returns:
        Configured RateLimiter instance

    Raises:
        ValueError: If integration is not recognized
    """
    if integration not in _rate_limiters:
        if integration not in INTEGRATION_CONFIGS:
            raise ValueError(
                f"Unknown integration: {integration}. "
                f"Valid options: {list(INTEGRATION_CONFIGS.keys())}"
            )

        config = INTEGRATION_CONFIGS[integration]
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
