"""Configuration settings dataclasses."""

import os
from dataclasses import dataclass, field
from typing import Optional, List

from common import get_secrets_manager


@dataclass
class UKGSettings:
    """UKG API configuration."""

    base_url: str
    username: str
    password: str
    basic_b64: str
    customer_api_key: str
    timeout: float = 45.0

    @classmethod
    def from_env(cls) -> "UKGSettings":
        """Create settings from environment variables."""
        secrets = get_secrets_manager()
        return cls(
            base_url=secrets.get_secret("UKG_BASE_URL") or "https://service4.ultipro.com",
            username=secrets.get_secret("UKG_USERNAME") or "",
            password=secrets.get_secret("UKG_PASSWORD") or "",
            basic_b64=secrets.get_secret("UKG_BASIC_B64") or "",
            customer_api_key=secrets.get_secret("UKG_CUSTOMER_API_KEY") or "",
            timeout=float(secrets.get_secret("UKG_TIMEOUT") or "45"),
        )

    def validate(self) -> None:
        """Validate required settings."""
        if not self.customer_api_key:
            raise ValueError("Missing UKG_CUSTOMER_API_KEY")
        if not self.basic_b64 and (not self.username or not self.password):
            raise ValueError("Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64")


@dataclass
class TravelPerkSettings:
    """TravelPerk API configuration."""

    api_base: str
    api_key: str
    timeout: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "TravelPerkSettings":
        """Create settings from environment variables."""
        secrets = get_secrets_manager()
        return cls(
            api_base=secrets.get_secret("TRAVELPERK_API_BASE") or "https://app.sandbox-travelperk.com",
            api_key=secrets.get_secret("TRAVELPERK_API_KEY") or "",
            timeout=float(secrets.get_secret("TRAVELPERK_TIMEOUT") or "60"),
            max_retries=int(secrets.get_secret("MAX_RETRIES") or "2"),
        )

    def validate(self) -> None:
        """Validate required settings."""
        if not self.api_key:
            raise ValueError("Missing TRAVELPERK_API_KEY")


@dataclass
class BatchSettings:
    """Batch processing configuration."""

    company_id: str = ""
    states_filter: Optional[str] = None
    employee_type_codes: Optional[List[str]] = None
    workers: int = 12
    dry_run: bool = False
    save_local: bool = False
    limit: int = 0
    out_dir: str = "data/batch"
    insert_supervisors: Optional[List[str]] = None

    @classmethod
    def from_env(cls) -> "BatchSettings":
        """Create settings from environment variables."""
        employee_type_codes = None
        type_codes_env = os.getenv("EMPLOYEE_TYPE_CODES", "")
        if type_codes_env:
            employee_type_codes = [
                code.strip() for code in type_codes_env.split(",") if code.strip()
            ]

        return cls(
            company_id=os.getenv("COMPANY_ID", ""),
            states_filter=os.getenv("STATES", "") or None,
            employee_type_codes=employee_type_codes,
            workers=int(os.getenv("WORKERS", "12")),
            dry_run=os.getenv("DRY_RUN", "0") == "1",
            save_local=os.getenv("SAVE_LOCAL", "0") == "1",
            limit=int(os.getenv("LIMIT", "0")),
            out_dir=os.getenv("OUT_DIR", "data/batch"),
        )
