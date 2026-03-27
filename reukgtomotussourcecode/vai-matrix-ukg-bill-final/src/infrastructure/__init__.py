"""
Infrastructure layer - External adapters and implementations.

This layer contains all implementations that interact with external systems:
- HTTP clients for UKG and BILL APIs
- Browser automation for scraping
- Configuration management
- Persistence (CSV, JSON export)
"""

from src.infrastructure.config import Settings, get_settings
from src.infrastructure.http import HttpClient, RetryStrategy

__all__ = [
    "Settings",
    "get_settings",
    "HttpClient",
    "RetryStrategy",
]
