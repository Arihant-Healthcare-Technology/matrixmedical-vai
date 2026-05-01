"""
Pydantic settings classes for configuration management.

All configuration is loaded from environment variables with type validation.
Secrets use SecretStr to prevent accidental exposure in logs.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.infrastructure.config.constants import (
    BILL_RATE_LIMIT,
    DEFAULT_BATCH_WORKERS,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)


class UKGSettings(BaseSettings):
    """UKG Pro API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="UKG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API endpoints
    base_url: str = Field(
        default="https://service4.ultipro.com",
        description="UKG Pro API base URL",
    )

    # Authentication
    username: str = Field(default="", description="UKG API username")
    password: SecretStr = Field(default=SecretStr(""), description="UKG API password")
    customer_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="UKG Customer API key",
        alias="UKG_CUSTOMER_API_KEY",
    )
    basic_auth_token: Optional[str] = Field(
        default=None,
        description="Pre-encoded Basic auth token (optional)",
        alias="UKG_BASIC_B64",
    )

    # Company configuration
    company_id: str = Field(default="", description="UKG company identifier")

    # Employee change filtering
    days_to_process: Optional[int] = Field(
        default=None,
        description="Only process employees changed within this many days. None = no filter.",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL doesn't have trailing slash."""
        return v.rstrip("/")


class BillSpendExpenseSettings(BaseSettings):
    """BILL.com Spend & Expense API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BILL_SE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base: str = Field(
        default="https://gateway.stage.bill.com/connect/v3/spend",
        description="BILL S&E API base URL",
    )
    api_token: SecretStr = Field(
        default=SecretStr(""),
        description="BILL API token",
    )
    default_role: str = Field(default="MEMBER", description="Default role for new users")


class BillAccountsPayableSettings(BaseSettings):
    """BILL.com Accounts Payable API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BILL_AP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base: str = Field(
        default="https://gateway.stage.bill.com/connect/v3",
        description="BILL AP API base URL",
    )
    api_token: SecretStr = Field(
        default=SecretStr(""),
        description="BILL API token",
    )


class BillSettings(BaseSettings):
    """Combined BILL.com configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BILL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Shared settings
    api_token: SecretStr = Field(
        default=SecretStr(""),
        description="BILL API token (shared across S&E and AP)",
    )

    # API bases (with fallback to shared token)
    se_api_base: str = Field(
        default="https://gateway.stage.bill.com/connect/v3/spend",
        description="BILL Spend & Expense API base URL",
        alias="BILL_API_BASE",
    )
    ap_api_base: str = Field(
        default="https://gateway.stage.bill.com/connect/v3",
        description="BILL Accounts Payable API base URL",
        alias="BILL_AP_API_BASE",
    )
    v2_api_base: str = Field(
        default="https://api-stage.bill.com/api/v2",
        description="BILL v2 API base URL for department lookup",
        alias="BILL_V2_API_BASE",
    )

    # Defaults
    default_role: str = Field(default="MEMBER", description="Default role for new users")
    rate_limit: int = Field(default=BILL_RATE_LIMIT, description="API rate limit (calls/min)")
    max_retries: int = Field(default=MAX_RETRIES, description="Max retry attempts")
    timeout: float = Field(default=DEFAULT_TIMEOUT, description="Request timeout in seconds")
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, description="Default pagination size")

    # Environment detection
    is_production: bool = Field(
        default=False,
        description="Whether running in production",
        alias="BILL_PRODUCTION",
    )

    @field_validator("se_api_base", "ap_api_base")
    @classmethod
    def validate_api_base(cls, v: str) -> str:
        """Ensure API base URL doesn't have trailing slash."""
        return v.rstrip("/")


class ScrapingSettings(BaseSettings):
    """Playwright browser automation configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SCRAPING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Browser settings
    headless: bool = Field(default=False, description="Run browser in headless mode")
    timeout: int = Field(default=60000, description="Default page timeout (ms)")
    slow_mo: int = Field(default=0, description="Slow down operations (ms)")

    # Viewport
    viewport_width: int = Field(default=1920, description="Browser viewport width")
    viewport_height: int = Field(default=1080, description="Browser viewport height")

    # Credentials
    login_email: str = Field(default="", description="BILL.com login email")
    login_password: SecretStr = Field(default=SecretStr(""), description="BILL.com login password")
    company_name: str = Field(default="", description="BILL.com company name to select")

    # Output
    output_dir: str = Field(default="output", description="Screenshot/output directory")
    csv_file_path: Optional[str] = Field(default=None, description="CSV file to import")


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json/text)")
    include_correlation_id: bool = Field(default=True, description="Include correlation ID")
    redact_pii: bool = Field(default=True, description="Redact PII from logs")


class NotificationSettings(BaseSettings):
    """Email notification configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NOTIFY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=False, description="Enable email notifications")
    provider: str = Field(default="smtp", description="Email provider (smtp/ses/sendgrid)")

    # SMTP settings
    smtp_host: str = Field(default="", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: SecretStr = Field(default=SecretStr(""), description="SMTP password")

    # AWS SES settings
    ses_region: str = Field(default="us-east-1", description="AWS SES region")

    # Recipients
    recipients: str = Field(default="", description="Comma-separated email recipients")
    sender_email: str = Field(default="noreply@integration.local", description="Sender email")
    sender_name: str = Field(default="UKG Integration Suite", description="Sender name")


class Settings(BaseSettings):
    """Root settings class that combines all configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    debug: bool = Field(default=False, description="Enable debug mode", alias="DEBUG")
    environment: str = Field(default="development", description="Environment name")

    # Batch processing
    batch_workers: int = Field(
        default=DEFAULT_BATCH_WORKERS,
        description="Number of parallel workers",
    )
    batch_limit: int = Field(default=0, description="Limit records to process (0=all)")

    # Sub-settings (loaded lazily)
    @property
    def ukg(self) -> UKGSettings:
        """Get UKG settings."""
        return UKGSettings()

    @property
    def bill(self) -> BillSettings:
        """Get BILL settings."""
        return BillSettings()

    @property
    def scraping(self) -> ScrapingSettings:
        """Get scraping settings."""
        return ScrapingSettings()

    @property
    def logging(self) -> LoggingSettings:
        """Get logging settings."""
        return LoggingSettings()

    @property
    def notifications(self) -> NotificationSettings:
        """Get notification settings."""
        return NotificationSettings()

    # =========================================================================
    # Backward-compatible flat property accessors
    # =========================================================================

    @property
    def ukg_api_base(self) -> str:
        """UKG API base URL (backward compatible)."""
        return self.ukg.base_url

    @property
    def ukg_username(self) -> str:
        """UKG username (backward compatible)."""
        return self.ukg.username

    @property
    def ukg_password(self) -> str:
        """UKG password (backward compatible)."""
        return self.ukg.password.get_secret_value()

    @property
    def ukg_api_key(self) -> str:
        """UKG Customer API key (backward compatible)."""
        return self.ukg.customer_api_key.get_secret_value()

    @property
    def ukg_basic_b64(self) -> Optional[str]:
        """UKG Basic auth token (backward compatible)."""
        return self.ukg.basic_auth_token

    @property
    def ukg_company_id(self) -> str:
        """UKG company ID (backward compatible)."""
        return self.ukg.company_id

    @property
    def bill_api_base(self) -> str:
        """BILL API base URL (backward compatible)."""
        return self.bill.se_api_base

    @property
    def bill_api_token(self) -> str:
        """BILL API token (backward compatible)."""
        return self.bill.api_token.get_secret_value()

    @property
    def bill_org_id(self) -> str:
        """BILL org ID (backward compatible)."""
        import os
        return os.getenv("BILL_ORG_ID", "")

    @property
    def bill_v2_api_base(self) -> str:
        """BILL v2 API base URL (backward compatible)."""
        return self.bill.v2_api_base

    @property
    def bill_default_funding_account(self) -> Optional[str]:
        """BILL default funding account (backward compatible)."""
        import os
        return os.getenv("BILL_DEFAULT_FUNDING_ACCOUNT")

    @property
    def rate_limit_calls_per_minute(self) -> int:
        """Rate limit (backward compatible)."""
        return self.bill.rate_limit


def _mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value, showing only last few characters."""
    if not value:
        return "(not set)"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def validate_and_log_settings(settings: Settings) -> dict:
    """
    Validate settings and log configuration status.

    Returns a dict with validation results.
    """
    import logging
    logger = logging.getLogger(__name__)

    results = {
        "ukg_configured": False,
        "bill_configured": False,
        "errors": [],
        "warnings": [],
    }

    # Check UKG settings
    logger.info("=" * 60)
    logger.info("Configuration Validation")
    logger.info("=" * 60)

    logger.info("UKG Pro API Configuration:")
    logger.info(f"  Base URL: {settings.ukg_api_base}")
    logger.info(f"  Username: {settings.ukg_username or '(not set)'}")
    logger.info(f"  Password: {_mask_secret(settings.ukg_password)}")
    logger.info(f"  API Key: {_mask_secret(settings.ukg_api_key)}")
    logger.info(f"  Basic B64: {_mask_secret(settings.ukg_basic_b64 or '')}")
    logger.info(f"  Company ID: {settings.ukg_company_id or '(not set)'}")

    if not settings.ukg_username and not settings.ukg_basic_b64:
        results["errors"].append("UKG: Missing username or basic_b64 token")
    elif not settings.ukg_password and not settings.ukg_basic_b64:
        results["errors"].append("UKG: Missing password or basic_b64 token")
    elif not settings.ukg_api_key:
        results["errors"].append("UKG: Missing customer_api_key")
    else:
        results["ukg_configured"] = True
        logger.info("  Status: CONFIGURED")

    if not results["ukg_configured"]:
        logger.warning("  Status: NOT CONFIGURED - Missing required credentials")

    # Check BILL settings
    logger.info("")
    logger.info("BILL.com API Configuration:")
    logger.info(f"  S&E API Base: {settings.bill_api_base}")
    logger.info(f"  API Token: {_mask_secret(settings.bill_api_token)}")
    logger.info(f"  Org ID: {settings.bill_org_id or '(not set)'}")
    logger.info(f"  Rate Limit: {settings.rate_limit_calls_per_minute} calls/min")

    if not settings.bill_api_token:
        results["errors"].append("BILL: Missing api_token")
    else:
        results["bill_configured"] = True
        logger.info("  Status: CONFIGURED")

    if not results["bill_configured"]:
        logger.warning("  Status: NOT CONFIGURED - Missing required credentials")

    # Summary
    logger.info("")
    logger.info("Configuration Summary:")
    logger.info(f"  Environment: {settings.environment}")
    logger.info(f"  Debug Mode: {settings.debug}")
    logger.info(f"  Batch Workers: {settings.batch_workers}")

    if results["errors"]:
        logger.error("Configuration Errors:")
        for error in results["errors"]:
            logger.error(f"  - {error}")

    if results["warnings"]:
        logger.warning("Configuration Warnings:")
        for warning in results["warnings"]:
            logger.warning(f"  - {warning}")

    logger.info("=" * 60)

    return results


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses LRU cache to ensure settings are loaded only once.
    Call `get_settings.cache_clear()` to reload settings.
    """
    return Settings()
