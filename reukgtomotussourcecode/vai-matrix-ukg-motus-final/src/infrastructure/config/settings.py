"""
Settings for Motus integration.

Provides environment-based configuration for UKG and Motus APIs.
"""

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

from .constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MOTUS_TIMEOUT,
    DEFAULT_UKG_TIMEOUT,
    DEFAULT_WORKERS,
)


@dataclass
class UKGSettings:
    """UKG API configuration."""

    base_url: str = "https://service4.ultipro.com"
    username: str = ""
    password: str = ""
    customer_api_key: str = ""
    basic_b64: str = ""  # Pre-encoded base64
    timeout: float = DEFAULT_UKG_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    @classmethod
    def from_env(cls) -> "UKGSettings":
        """Create settings from environment variables."""
        return cls(
            base_url=os.getenv("UKG_BASE_URL", cls.base_url),
            username=os.getenv("UKG_USERNAME", ""),
            password=os.getenv("UKG_PASSWORD", ""),
            customer_api_key=os.getenv("UKG_CUSTOMER_API_KEY", ""),
            basic_b64=os.getenv("UKG_BASIC_B64", ""),
            timeout=float(os.getenv("UKG_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("UKG_MAX_RETRIES", str(cls.max_retries))),
        )

    def get_auth_token(self) -> str:
        """Get base64-encoded auth token."""
        if self.basic_b64:
            return self.basic_b64.strip()
        if not self.username or not self.password:
            raise ValueError("Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64")
        return base64.b64encode(f"{self.username}:{self.password}".encode()).decode()

    def validate(self) -> None:
        """Validate settings."""
        if not self.customer_api_key:
            raise ValueError("Missing UKG_CUSTOMER_API_KEY")
        # Validate we can get auth token
        self.get_auth_token()

    def validate_or_exit(self) -> None:
        """
        Validate UKG settings and exit if credentials are missing or invalid.
        Logs an error message with instructions.
        """
        if not self.customer_api_key:
            logger.error("UKG_CUSTOMER_API_KEY is not set or is empty. Cannot connect to UKG API.")
            logger.error("Please set UKG_CUSTOMER_API_KEY in your .env file.")
            raise SystemExit(1)

        # Check for authentication credentials
        if not self.basic_b64 and (not self.username or not self.password):
            logger.error("UKG authentication credentials are missing.")
            logger.error("Please set either UKG_BASIC_B64 or both UKG_USERNAME and UKG_PASSWORD in your .env file.")
            raise SystemExit(1)


@dataclass
class MotusSettings:
    """Motus API configuration."""

    api_base: str = "https://api.motus.com/v1"
    jwt: str = ""
    default_program_id: int = 21233  # CPM
    timeout: float = DEFAULT_MOTUS_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    @classmethod
    def from_env(cls) -> "MotusSettings":
        """Create settings from environment variables."""
        return cls(
            api_base=os.getenv("MOTUS_API_BASE", cls.api_base),
            jwt=os.getenv("MOTUS_JWT", ""),
            default_program_id=int(os.getenv("MOTUS_PROGRAM_ID", str(cls.default_program_id))),
            timeout=float(os.getenv("MOTUS_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("MOTUS_MAX_RETRIES", str(cls.max_retries))),
        )

    def set_jwt(self, jwt: str) -> None:
        """
        Set JWT token programmatically (for in-memory token management).

        Args:
            jwt: The JWT token string
        """
        self.jwt = jwt

    def validate(self) -> None:
        """Validate settings."""
        if not self.jwt:
            raise ValueError("Missing MOTUS_JWT")

    def validate_or_exit(self) -> None:
        """
        Validate Motus settings and exit if JWT is missing or invalid.
        Logs an error message with instructions for generating a token.
        """
        if not self.jwt:
            logger.error("MOTUS_JWT is not set or is empty. Cannot connect to Motus API.")
            logger.error("Ensure MOTUS_LOGIN_ID and MOTUS_PASSWORD are set for automatic token generation.")
            raise SystemExit(1)

        # Validate JWT format (should have 3 parts separated by dots)
        if len(self.jwt.split(".")) != 3:
            logger.error("MOTUS_JWT appears to be invalid (not a valid JWT format).")
            logger.error("Check MOTUS_LOGIN_ID and MOTUS_PASSWORD credentials.")
            raise SystemExit(1)


@dataclass
class BatchSettings:
    """Batch processing configuration."""

    workers: int = DEFAULT_WORKERS
    company_id: str = ""
    states_filter: Optional[str] = None
    job_codes: str = ""
    dry_run: bool = False
    save_local: bool = False
    probe: bool = False
    out_dir: str = "data/batch"

    @classmethod
    def from_env(cls) -> "BatchSettings":
        """Create settings from environment variables."""
        return cls(
            workers=int(os.getenv("WORKERS", str(cls.workers))),
            company_id=os.getenv("COMPANY_ID", ""),
            states_filter=os.getenv("STATES", None),
            job_codes=os.getenv("JOB_IDS", ""),
            dry_run=os.getenv("DRY_RUN", "0") == "1",
            save_local=os.getenv("SAVE_LOCAL", "0") == "1",
            probe=os.getenv("PROBE", "0") == "1",
            out_dir=os.getenv("OUT_DIR", cls.out_dir),
        )

    def validate(self) -> None:
        """Validate settings."""
        if not self.company_id:
            raise ValueError("COMPANY_ID is required")
        if not self.job_codes:
            raise ValueError("JOB_IDS is required")
