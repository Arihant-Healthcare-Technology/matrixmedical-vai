"""
Redaction utilities.

Helper functions for safely handling sensitive data in logs and error contexts.
"""

from typing import Any, Dict, Optional

from .core import redact_pii, redact_secrets, redact_all, _redact_pii_in_dict


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
    additional_context: Optional[Dict[str, Any]] = None,
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


def mask_value(value: str, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    Mask a sensitive value showing only first/last few characters.

    Args:
        value: Value to mask
        visible_chars: Number of characters to show at start/end
        mask_char: Character to use for masking

    Returns:
        Masked value
    """
    if not value or len(value) <= visible_chars * 2:
        return mask_char * len(value) if value else ""

    start = value[:visible_chars]
    end = value[-visible_chars:]
    middle_len = len(value) - (visible_chars * 2)

    return f"{start}{mask_char * min(middle_len, 10)}{end}"
