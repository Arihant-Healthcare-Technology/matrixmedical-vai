"""
UKG Pro API adapter.

Provides UKG API client, repository implementation, and data mappers.
"""

from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.adapters.ukg.repository import UKGEmployeeRepository
from src.infrastructure.adapters.ukg.mappers import (
    map_address,
    map_employee_from_ukg,
    map_employment_status,
    normalize_phone,
    parse_date,
    extract_supervisor_info,
)

__all__ = [
    # Client
    "UKGClient",
    # Repository
    "UKGEmployeeRepository",
    # Mappers
    "map_address",
    "map_employee_from_ukg",
    "map_employment_status",
    "normalize_phone",
    "parse_date",
    "extract_supervisor_info",
]
