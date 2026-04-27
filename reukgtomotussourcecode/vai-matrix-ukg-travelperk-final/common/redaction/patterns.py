"""
Redaction patterns.

Defines regex patterns for identifying PII and secrets.
"""

import re
from typing import List, Pattern, Tuple


# PII patterns with their replacements
PII_PATTERNS: List[Tuple[Pattern, str]] = [
    # Email addresses - disabled to show actual emails in logs
    # (
    #     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    #     "[EMAIL]",
    # ),
    # Phone numbers (various formats)
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    # SSN
    (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "[SSN]"),
    # ZIP codes - DISABLED: was incorrectly matching org-level codes like 53203
    # (re.compile(r"\b\d{5}(-\d{4})?\b"), "[ZIP]"),
    # Credit card numbers (basic patterns)
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CARD]"),
    # Date of birth patterns
    (re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"), "[DATE]"),
    # IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP]"),
    # Street addresses (basic pattern)
    (
        re.compile(
            r"\b\d+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
            re.IGNORECASE,
        ),
        "[ADDRESS]",
    ),
]

# Keys that indicate sensitive data
SECRET_KEYS: List[str] = [
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "auth",
    "authorization",
    "bearer",
    "credential",
    "private_key",
    "privatekey",
    "access_key",
    "accesskey",
    "session",
    "cookie",
    "jwt",
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
]

# Patterns that look like secrets in values
SECRET_VALUE_PATTERNS: List[Pattern] = [
    # JWT tokens
    re.compile(r"^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"),
    # API keys (long alphanumeric strings)
    re.compile(r"^[A-Za-z0-9]{32,}$"),
    # Base64 encoded data that's long
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
    # Bearer tokens
    re.compile(r"^Bearer\s+.+$", re.IGNORECASE),
    # AWS access keys
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    # AWS secret keys
    re.compile(r"^[A-Za-z0-9/+=]{40}$"),
]
