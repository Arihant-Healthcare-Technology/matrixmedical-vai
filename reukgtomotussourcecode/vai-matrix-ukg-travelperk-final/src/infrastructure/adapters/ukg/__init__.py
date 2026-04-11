"""
UKG API adapter module.

Provides client and utilities for interacting with UKG Personnel API.

Structure:
- client.py: Main UKGClient class
- auth.py: Authentication utilities
- endpoints.py: API endpoint definitions
- error_handler.py: Error handling
"""

from .client import UKGClient
from .auth import UKGAuthenticator
from .endpoints import UKGEndpoints
from .error_handler import UKGErrorHandler

__all__ = [
    "UKGClient",
    "UKGAuthenticator",
    "UKGEndpoints",
    "UKGErrorHandler",
]
