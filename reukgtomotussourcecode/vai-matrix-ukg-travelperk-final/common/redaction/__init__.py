"""
Redaction Package.

Provides PII and secrets redaction for logs and error reporting.
Ensures sensitive data is not exposed in logs or transmitted in reports.

Usage:
    from common.redaction import redact_pii, redact_secrets, RedactingFormatter

    # Redact PII from text
    safe_text = redact_pii("Contact john@example.com for details")
    # Output: "Contact [EMAIL] for details"

    # Redact secrets from dictionary
    safe_dict = redact_secrets({"api_key": "secret123", "name": "John"})
    # Output: {"api_key": "[REDACTED]", "name": "John"}

    # Use with logging
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter())
    logger.addHandler(handler)

Structure:
- patterns.py: Regex patterns for PII and secrets
- core.py: Core redaction functions
- logging.py: Logging formatters and filters
- utils.py: Helper utilities
"""

from .patterns import PII_PATTERNS, SECRET_KEYS, SECRET_VALUE_PATTERNS
from .core import (
    redact_pii,
    redact_secrets,
    redact_all,
    _looks_like_secret,
    _redact_pii_in_dict,
)
from .logging import (
    RedactingFormatter,
    RedactingFilter,
)
from .utils import (
    sanitize_for_logging,
    create_safe_error_context,
    mask_value,
)

__all__ = [
    # Patterns
    "PII_PATTERNS",
    "SECRET_KEYS",
    "SECRET_VALUE_PATTERNS",
    # Core functions
    "redact_pii",
    "redact_secrets",
    "redact_all",
    "_looks_like_secret",
    "_redact_pii_in_dict",
    # Logging
    "RedactingFormatter",
    "RedactingFilter",
    # Utilities
    "sanitize_for_logging",
    "create_safe_error_context",
    "mask_value",
]
