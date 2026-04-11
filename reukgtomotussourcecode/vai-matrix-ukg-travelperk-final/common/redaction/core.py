"""
Core redaction functions.

Provides functions for redacting PII and secrets from text and dictionaries.
"""

from typing import Any, Dict, List, Optional, Pattern, Tuple

from .patterns import PII_PATTERNS, SECRET_KEYS, SECRET_VALUE_PATTERNS


def redact_pii(
    text: str,
    patterns: Optional[List[Tuple[Pattern, str]]] = None,
) -> str:
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


def _looks_like_secret(value: str) -> bool:
    """Check if a string value looks like a secret."""
    if not value or len(value) < 20:
        return False

    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.match(value):
            return True

    return False


def redact_secrets(
    data: Dict[str, Any],
    secret_keys: Optional[List[str]] = None,
    deep: bool = True,
    redaction_string: str = "[REDACTED]",
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
                if isinstance(item, dict)
                else item
                for item in value
            ]
        elif isinstance(value, str) and _looks_like_secret(value):
            result[key] = redaction_string
        else:
            result[key] = value

    return result


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
                _redact_pii_in_dict(item)
                if isinstance(item, dict)
                else redact_pii(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def redact_all(
    text_or_dict,
    redact_pii_flag: bool = True,
    redact_secrets_flag: bool = True,
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
