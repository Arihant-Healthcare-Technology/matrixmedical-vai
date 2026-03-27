"""
Redaction Module - SOW Requirements 7.4, 7.5, 9.4

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
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Pattern
from functools import lru_cache
import copy

logger = logging.getLogger(__name__)


# PII patterns with their replacements
PII_PATTERNS: List[Tuple[Pattern, str]] = [
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),

    # Phone numbers (various formats)
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE]'),
    (re.compile(r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b'), '[PHONE]'),
    (re.compile(r'\b\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE]'),

    # SSN
    (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), '[SSN]'),

    # ZIP codes (5 or 9 digit)
    (re.compile(r'\b\d{5}(-\d{4})?\b'), '[ZIP]'),

    # Credit card numbers (basic patterns)
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '[CARD]'),

    # Date of birth patterns
    (re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b'), '[DATE]'),

    # IP addresses
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP]'),

    # Street addresses (basic pattern)
    (re.compile(r'\b\d+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', re.IGNORECASE), '[ADDRESS]'),
]

# Keys that indicate sensitive data
SECRET_KEYS: List[str] = [
    'password',
    'passwd',
    'pwd',
    'secret',
    'token',
    'api_key',
    'apikey',
    'api-key',
    'auth',
    'authorization',
    'bearer',
    'credential',
    'private_key',
    'privatekey',
    'access_key',
    'accesskey',
    'session',
    'cookie',
    'jwt',
    'ssn',
    'social_security',
    'credit_card',
    'card_number',
    'cvv',
    'pin',
]

# Patterns that look like secrets in values
SECRET_VALUE_PATTERNS: List[Pattern] = [
    # JWT tokens
    re.compile(r'^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$'),
    # API keys (long alphanumeric strings)
    re.compile(r'^[A-Za-z0-9]{32,}$'),
    # Base64 encoded data that's long
    re.compile(r'^[A-Za-z0-9+/]{40,}={0,2}$'),
    # Bearer tokens
    re.compile(r'^Bearer\s+.+$', re.IGNORECASE),
    # AWS access keys
    re.compile(r'^AKIA[0-9A-Z]{16}$'),
    # AWS secret keys
    re.compile(r'^[A-Za-z0-9/+=]{40}$'),
]


def redact_pii(text: str, patterns: Optional[List[Tuple[Pattern, str]]] = None) -> str:
    """
    Redact PII from text.

    Args:
        text: Text to redact
        patterns: Optional custom patterns (uses defaults if not provided)

    Returns:
        Text with PII replaced by placeholders
    """
    if not text:
        return text

    patterns = patterns or PII_PATTERNS

    result = text
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)

    return result


def redact_secrets(
    data: Dict[str, Any],
    secret_keys: Optional[List[str]] = None,
    deep: bool = True,
    redaction_string: str = "[REDACTED]"
) -> Dict[str, Any]:
    """
    Redact secrets from a dictionary.

    Args:
        data: Dictionary to redact
        secret_keys: Optional custom list of secret key names
        deep: Whether to recursively process nested dicts
        redaction_string: String to use for redacted values

    Returns:
        New dictionary with secrets redacted
    """
    if not data:
        return data

    secret_keys = secret_keys or SECRET_KEYS
    secret_keys_lower = [k.lower() for k in secret_keys]

    result = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if key indicates a secret
        is_secret_key = any(s in key_lower for s in secret_keys_lower)

        if is_secret_key:
            result[key] = redaction_string
        elif isinstance(value, dict) and deep:
            result[key] = redact_secrets(value, secret_keys, deep, redaction_string)
        elif isinstance(value, list) and deep:
            result[key] = [
                redact_secrets(item, secret_keys, deep, redaction_string)
                if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str) and _looks_like_secret(value):
            result[key] = redaction_string
        else:
            result[key] = value

    return result


def _looks_like_secret(value: str) -> bool:
    """Check if a string value looks like a secret."""
    if not value or len(value) < 20:
        return False

    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.match(value):
            return True

    return False


def redact_all(
    text_or_dict,
    redact_pii_flag: bool = True,
    redact_secrets_flag: bool = True
):
    """
    Redact both PII and secrets from text or dictionary.

    Args:
        text_or_dict: String or dictionary to redact
        redact_pii_flag: Whether to redact PII
        redact_secrets_flag: Whether to redact secrets

    Returns:
        Redacted string or dictionary
    """
    if isinstance(text_or_dict, str):
        result = text_or_dict
        if redact_pii_flag:
            result = redact_pii(result)
        return result
    elif isinstance(text_or_dict, dict):
        result = text_or_dict
        if redact_secrets_flag:
            result = redact_secrets(result)
        if redact_pii_flag:
            result = _redact_pii_in_dict(result)
        return result
    else:
        return text_or_dict


def _redact_pii_in_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII from all string values in a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = redact_pii(value)
        elif isinstance(value, dict):
            result[key] = _redact_pii_in_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _redact_pii_in_dict(item) if isinstance(item, dict)
                else redact_pii(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


class RedactingFormatter(logging.Formatter):
    """
    Logging formatter that redacts PII and secrets from log messages.

    Usage:
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter())
        logger.addHandler(handler)
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        redact_pii_flag: bool = True,
        redact_secrets_flag: bool = True
    ):
        """
        Initialize formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
            redact_pii_flag: Whether to redact PII
            redact_secrets_flag: Whether to redact secrets
        """
        if fmt is None:
            fmt = "[%(levelname)s] [%(asctime)s] [%(name)s] %(message)s"
        super().__init__(fmt, datefmt)
        self.redact_pii_flag = redact_pii_flag
        self.redact_secrets_flag = redact_secrets_flag

    def format(self, record: logging.LogRecord) -> str:
        """Format and redact the log record."""
        # Make a copy to avoid modifying the original
        record_copy = copy.copy(record)

        # Redact the message
        if self.redact_pii_flag:
            record_copy.msg = redact_pii(str(record_copy.msg))

        # Redact args if they're strings
        if record_copy.args:
            if isinstance(record_copy.args, dict):
                record_copy.args = redact_secrets(record_copy.args) if self.redact_secrets_flag else record_copy.args
            elif isinstance(record_copy.args, tuple):
                record_copy.args = tuple(
                    redact_pii(str(arg)) if isinstance(arg, str) and self.redact_pii_flag else arg
                    for arg in record_copy.args
                )

        return super().format(record_copy)


class RedactingFilter(logging.Filter):
    """
    Logging filter that redacts PII and secrets.

    Can be added to any handler without changing formatter.
    """

    def __init__(
        self,
        name: str = "",
        redact_pii_flag: bool = True,
        redact_secrets_flag: bool = True
    ):
        super().__init__(name)
        self.redact_pii_flag = redact_pii_flag
        self.redact_secrets_flag = redact_secrets_flag

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact the log record."""
        if self.redact_pii_flag:
            record.msg = redact_pii(str(record.msg))

        if record.args:
            if isinstance(record.args, dict) and self.redact_secrets_flag:
                record.args = redact_secrets(record.args)
            elif isinstance(record.args, tuple) and self.redact_pii_flag:
                record.args = tuple(
                    redact_pii(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True


def sanitize_for_logging(data: Any, max_length: int = 500) -> str:
    """
    Sanitize data for safe logging.

    Redacts sensitive data and truncates long values.

    Args:
        data: Data to sanitize
        max_length: Maximum length for string output

    Returns:
        Safe string representation for logging
    """
    if data is None:
        return "None"

    if isinstance(data, str):
        result = redact_pii(data)
        if len(result) > max_length:
            result = result[:max_length] + "...[TRUNCATED]"
        return result

    if isinstance(data, dict):
        safe_dict = redact_secrets(data)
        safe_dict = _redact_pii_in_dict(safe_dict)
        result = str(safe_dict)
        if len(result) > max_length:
            result = result[:max_length] + "...[TRUNCATED]"
        return result

    if isinstance(data, (list, tuple)):
        result = str(data)
        result = redact_pii(result)
        if len(result) > max_length:
            result = result[:max_length] + "...[TRUNCATED]"
        return result

    return str(data)[:max_length]


def create_safe_error_context(
    exception: Exception,
    additional_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a safe error context for logging/reporting.

    Includes exception info with PII/secrets redacted.

    Args:
        exception: The exception that occurred
        additional_context: Additional context to include

    Returns:
        Safe dictionary for logging
    """
    context = {
        "error_type": type(exception).__name__,
        "error_message": redact_pii(str(exception)),
    }

    if additional_context:
        safe_context = redact_all(additional_context)
        context["context"] = safe_context

    return context
