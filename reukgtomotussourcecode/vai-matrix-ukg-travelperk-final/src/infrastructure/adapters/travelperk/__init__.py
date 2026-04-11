"""
TravelPerk API adapter module.

Provides client and utilities for interacting with TravelPerk SCIM API.

Structure:
- client.py: Main TravelPerkClient class
- endpoints.py: API endpoint definitions
- error_handler.py: Error handling
- scim.py: SCIM protocol utilities
"""

from .client import TravelPerkClient
from .endpoints import TravelPerkEndpoints
from .error_handler import TravelPerkErrorHandler
from .scim import (
    SCIMSchemas,
    SCIMOperations,
    build_patch_operation,
    build_patch_payload,
    extract_resources,
    get_user_id,
    get_external_id,
)

__all__ = [
    "TravelPerkClient",
    "TravelPerkEndpoints",
    "TravelPerkErrorHandler",
    "SCIMSchemas",
    "SCIMOperations",
    "build_patch_operation",
    "build_patch_payload",
    "extract_resources",
    "get_user_id",
    "get_external_id",
]
