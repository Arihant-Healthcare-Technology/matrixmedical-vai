"""
Common mapping utility functions.

This module re-exports shared functions from common/formatters.py
for backward compatibility. Import directly from common.formatters
for new code.

Usage:
    # Preferred (direct import)
    from common.formatters import parse_date, format_date, normalize_phone

    # Legacy (still supported)
    from src.infrastructure.adapters.bill.mappers.common import parse_date
"""

from common.formatters import (
    format_cost_center,
    format_date,
    normalize_email,
    normalize_phone,
    parse_date,
    parse_decimal,
)

__all__ = [
    "format_cost_center",
    "format_date",
    "normalize_email",
    "normalize_phone",
    "parse_date",
    "parse_decimal",
]
