"""Configuration management."""

from .settings import UKGSettings, TravelPerkSettings, BatchSettings
from .constants import (
    DEFAULT_UKG_TIMEOUT,
    DEFAULT_TRAVELPERK_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_WORKERS,
    UKG_MAX_PAGE_SIZE,
    SCIM_CORE_SCHEMA,
    SCIM_ENTERPRISE_SCHEMA,
    SCIM_TRAVELPERK_SCHEMA,
    SCIM_PATCH_SCHEMA,
)

__all__ = [
    "UKGSettings",
    "TravelPerkSettings",
    "BatchSettings",
    "DEFAULT_UKG_TIMEOUT",
    "DEFAULT_TRAVELPERK_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_WORKERS",
    "UKG_MAX_PAGE_SIZE",
    "SCIM_CORE_SCHEMA",
    "SCIM_ENTERPRISE_SCHEMA",
    "SCIM_TRAVELPERK_SCHEMA",
    "SCIM_PATCH_SCHEMA",
]
