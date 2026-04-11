"""
Formatters Module - Common data formatting and normalization utilities.

Provides shared functions for date parsing, phone normalization,
email normalization, and other data formatting operations.

Usage:
    from common.formatters import (
        normalize_phone,
        normalize_email,
        parse_date,
        format_date,
        parse_decimal,
    )
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, Union


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize phone number to XXX-XXX-XXXX format for US numbers.

    Handles:
    - 10-digit US numbers: (555) 123-4567 -> 555-123-4567
    - 11-digit US numbers with country code: 1-555-123-4567 -> 555-123-4567
    - International numbers are returned as-is

    Args:
        phone: Phone string to normalize

    Returns:
        Normalized phone string, or original if cannot normalize
    """
    if not phone:
        return ""

    # Extract only digits
    digits = re.sub(r"\D", "", phone)

    # Format 10-digit US numbers
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"

    # Handle 11-digit with leading 1 (US country code)
    if len(digits) == 11 and digits[0] == "1":
        return f"{digits[1:4]}-{digits[4:7]}-{digits[7:11]}"

    # Return original if unable to normalize
    return phone


def normalize_email(email: Optional[str]) -> str:
    """
    Normalize email address.

    Args:
        email: Email to normalize

    Returns:
        Lowercase trimmed email, or empty string if None
    """
    if not email:
        return ""
    return email.lower().strip()


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string to date object.

    Handles formats:
    - ISO 8601: 2024-01-15T00:00:00Z
    - ISO date: 2024-01-15
    - ISO 8601 with timezone: 2024-01-15T00:00:00+00:00

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date or None if invalid/empty
    """
    if not date_str:
        return None

    try:
        # Handle ISO 8601 with timezone
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.date()
    except Exception:
        try:
            # Handle plain date
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse date string to datetime object.

    Similar to parse_date but returns datetime instead of date.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime or None if invalid/empty
    """
    if not date_str:
        return None

    try:
        # Handle ISO 8601 with timezone
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        try:
            # Handle plain date
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return None


def format_date(d: Optional[date]) -> str:
    """
    Format date to ISO format (YYYY-MM-DD).

    Args:
        d: Date to format

    Returns:
        Formatted date string or empty string if None
    """
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def parse_decimal(value: Any) -> Decimal:
    """
    Parse value to Decimal for monetary amounts.

    Args:
        value: Value to parse (str, int, float, Decimal)

    Returns:
        Decimal value, or Decimal("0") if invalid
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def format_cost_center(code: str, description: str = "") -> str:
    """
    Format cost center as 'CODE - Description'.

    Client expects format: "5230 - Cost Center Name"

    Args:
        code: Cost center code
        description: Cost center description

    Returns:
        Formatted cost center string
    """
    if not code:
        return ""
    if not description:
        return code
    return f"{code} – {description}"


def sanitize_string(value: Optional[str], max_length: int = None) -> str:
    """
    Sanitize string by trimming whitespace and optionally truncating.

    Args:
        value: String to sanitize
        max_length: Maximum length (optional)

    Returns:
        Sanitized string
    """
    if not value:
        return ""
    result = value.strip()
    if max_length and len(result) > max_length:
        result = result[:max_length]
    return result
