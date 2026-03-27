"""
Application constants - Magic numbers and strings extracted from codebase.

All hardcoded values that were scattered across the codebase are now
centralized here for easy configuration and maintenance.
"""

from typing import FrozenSet

# ============================================================================
# Rate Limits (calls per minute)
# ============================================================================
BILL_RATE_LIMIT: int = 60  # BILL.com API rate limit
UKG_RATE_LIMIT: int = 100  # UKG Pro API rate limit (estimated)

# ============================================================================
# Timeouts (seconds)
# ============================================================================
DEFAULT_TIMEOUT: float = 45.0  # Default HTTP request timeout
BATCH_TIMEOUT: float = 60.0  # Timeout for batch operations
SCRAPING_TIMEOUT: float = 60000  # Playwright timeout in milliseconds
LOGIN_TIMEOUT: float = 30000  # Login page timeout in milliseconds

# ============================================================================
# Pagination
# ============================================================================
DEFAULT_PAGE_SIZE: int = 200  # Default page size for list operations
MAX_PAGE_SIZE: int = 500  # Maximum allowed page size

# ============================================================================
# Retry Configuration
# ============================================================================
MAX_RETRIES: int = 2  # Default number of retry attempts
BACKOFF_FACTOR: float = 2.0  # Exponential backoff multiplier
BACKOFF_MAX: float = 60.0  # Maximum backoff delay in seconds
JITTER_FACTOR: float = 0.1  # Random jitter factor (0.1 = 10%)

# ============================================================================
# BILL.com Roles (Spend & Expense)
# ============================================================================
VALID_BILL_ROLES: FrozenSet[str] = frozenset({
    "ADMIN",
    "AUDITOR",
    "BOOKKEEPER",
    "MEMBER",
    "NO_ACCESS",
})

DEFAULT_BILL_ROLE: str = "MEMBER"

# ============================================================================
# BILL.com Payment Methods (Accounts Payable)
# ============================================================================
VALID_PAYMENT_METHODS: FrozenSet[str] = frozenset({
    "CHECK",
    "ACH",
    "WIRE",
    "CARD_ACCOUNT",
})

DEFAULT_PAYMENT_METHOD: str = "ACH"
DEFAULT_PAYMENT_TERM_DAYS: int = 30

# ============================================================================
# Bill Status Values
# ============================================================================
BILL_STATUS_PAID: str = "paid"
BILL_STATUS_VOIDED: str = "voided"
BILL_STATUS_PARTIAL: str = "partial"
BILL_STATUS_OPEN: str = "open"
BILL_STATUS_APPROVED: str = "approved"

NON_UPDATABLE_BILL_STATUSES: FrozenSet[str] = frozenset({
    BILL_STATUS_PAID,
    BILL_STATUS_VOIDED,
    BILL_STATUS_PARTIAL,
})

# ============================================================================
# US States (for validation)
# ============================================================================
US_STATES: FrozenSet[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",  # Territories
})

# ============================================================================
# Country Codes (ISO 3166-1 alpha-2)
# ============================================================================
SUPPORTED_COUNTRIES: FrozenSet[str] = frozenset({
    "US", "CA", "MX", "GB", "DE", "FR", "AU", "NZ", "IN",
})

DEFAULT_COUNTRY: str = "US"

# ============================================================================
# UKG Employee Type Codes
# ============================================================================
ACTIVE_EMPLOYEE_TYPE_CODE: str = "A"
TERMINATED_EMPLOYEE_TYPE_CODE: str = "T"

ACTIVE_EMPLOYEE_TYPES: FrozenSet[str] = frozenset({
    ACTIVE_EMPLOYEE_TYPE_CODE,
})

# ============================================================================
# Batch Processing
# ============================================================================
DEFAULT_BATCH_WORKERS: int = 12
MAX_BATCH_WORKERS: int = 50
DEFAULT_BATCH_LIMIT: int = 0  # 0 = no limit

# ============================================================================
# CSV Export Headers (BILL.com People Import)
# ============================================================================
BILL_CSV_HEADERS: tuple = (
    "first name",
    "last name",
    "email address",
    "role",
    "manager",
)

# ============================================================================
# Date Formats
# ============================================================================
ISO_DATE_FORMAT: str = "%Y-%m-%d"
ISO_DATETIME_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
UKG_DATE_FORMAT: str = "%Y-%m-%d"
BILL_DATE_FORMAT: str = "%Y-%m-%d"

# ============================================================================
# HTTP Headers
# ============================================================================
CONTENT_TYPE_JSON: str = "application/json"
ACCEPT_JSON: str = "application/json"

# ============================================================================
# Report Generation
# ============================================================================
MAX_ERRORS_IN_REPORT: int = 50
REPORT_OUTPUT_DIR: str = "data/reports"
