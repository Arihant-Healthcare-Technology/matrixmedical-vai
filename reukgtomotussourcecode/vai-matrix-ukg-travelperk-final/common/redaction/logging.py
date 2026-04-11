"""
Redaction-aware logging utilities.

Provides logging formatters and filters that automatically redact
PII and secrets from log messages.
"""

import copy
import logging
from typing import Optional

from .core import redact_pii, redact_secrets


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
        redact_secrets_flag: bool = True,
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
                record_copy.args = (
                    redact_secrets(record_copy.args)
                    if self.redact_secrets_flag
                    else record_copy.args
                )
            elif isinstance(record_copy.args, tuple):
                record_copy.args = tuple(
                    redact_pii(str(arg))
                    if isinstance(arg, str) and self.redact_pii_flag
                    else arg
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
        redact_secrets_flag: bool = True,
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
