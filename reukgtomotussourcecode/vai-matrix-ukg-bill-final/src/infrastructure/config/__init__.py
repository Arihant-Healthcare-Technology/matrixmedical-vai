"""
Configuration management using Pydantic settings.

All configuration is loaded from environment variables with sensible defaults.
Secrets are handled securely using pydantic's SecretStr type.
"""

from src.infrastructure.config.settings import (
    Settings,
    UKGSettings,
    BillSettings,
    BillSpendExpenseSettings,
    BillAccountsPayableSettings,
    ScrapingSettings,
    LoggingSettings,
    get_settings,
)
from src.infrastructure.config.constants import (
    BILL_RATE_LIMIT,
    UKG_RATE_LIMIT,
    DEFAULT_TIMEOUT,
    BATCH_TIMEOUT,
    DEFAULT_PAGE_SIZE,
    MAX_RETRIES,
    VALID_BILL_ROLES,
    VALID_PAYMENT_METHODS,
    US_STATES,
)
from src.infrastructure.config.selectors import (
    SelectorConfig,
    TimeoutConfig,
    ViewportConfig,
    LoginSelectors,
    CompanySelectors,
    PopupSelectors,
    PeopleSelectors,
    ImportSelectors,
    UserDetailsSelectors,
    CommonSelectors,
    load_selectors,
    get_selectors,
    reload_selectors,
)

__all__ = [
    # Settings classes
    "Settings",
    "UKGSettings",
    "BillSettings",
    "BillSpendExpenseSettings",
    "BillAccountsPayableSettings",
    "ScrapingSettings",
    "LoggingSettings",
    "get_settings",
    # Constants
    "BILL_RATE_LIMIT",
    "UKG_RATE_LIMIT",
    "DEFAULT_TIMEOUT",
    "BATCH_TIMEOUT",
    "DEFAULT_PAGE_SIZE",
    "MAX_RETRIES",
    "VALID_BILL_ROLES",
    "VALID_PAYMENT_METHODS",
    "US_STATES",
    # Selectors
    "SelectorConfig",
    "TimeoutConfig",
    "ViewportConfig",
    "LoginSelectors",
    "CompanySelectors",
    "PopupSelectors",
    "PeopleSelectors",
    "ImportSelectors",
    "UserDetailsSelectors",
    "CommonSelectors",
    "load_selectors",
    "get_selectors",
    "reload_selectors",
]
