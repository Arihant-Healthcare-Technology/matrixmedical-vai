"""
External Service Adapters.

Provides API clients for external services.

Structure:
- ukg/: UKG Personnel API client
- travelperk/: TravelPerk SCIM API client
"""

from .ukg import UKGClient, UKGAuthenticator, UKGEndpoints
from .travelperk import TravelPerkClient, TravelPerkEndpoints, SCIMSchemas

__all__ = [
    # UKG
    "UKGClient",
    "UKGAuthenticator",
    "UKGEndpoints",
    # TravelPerk
    "TravelPerkClient",
    "TravelPerkEndpoints",
    "SCIMSchemas",
]
