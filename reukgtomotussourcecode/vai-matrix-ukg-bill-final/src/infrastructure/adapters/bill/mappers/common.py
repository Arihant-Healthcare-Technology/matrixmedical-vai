"""
Common mapping utility functions.

Provides shared functions for date parsing, formatting, and normalization.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse BILL date string to date object.

    Handles formats:
    - ISO 8601: 2024-01-15T00:00:00Z
    - ISO date: 2024-01-15

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date or None
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


def format_date(d: Optional[date]) -> str:
    """
    Format date to BILL API format (YYYY-MM-DD).

    Args:
        d: Date to format

    Returns:
        Formatted date string or empty string
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
        Decimal value
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def normalize_email(email: Optional[str]) -> str:
    """
    Normalize email address.

    Args:
        email: Email to normalize

    Returns:
        Lowercase trimmed email
    """
    if not email:
        return ""
    return email.lower().strip()


def format_cost_center(code: str, description: str) -> str:
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


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize phone number to XXX-XXX-XXXX format for US numbers.

    Args:
        phone: Phone string to normalize

    Returns:
        Normalized phone string
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"{digits[1:4]}-{digits[4:7]}-{digits[7:11]}"
    return phone
