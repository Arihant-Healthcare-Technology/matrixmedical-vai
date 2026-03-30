"""Scraper configuration settings."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Browser configuration
CONFIG = {
    'headless': False,  # Change to True for headless mode
    'timeout': 60000,  # 60 seconds (increased for slow pages)
    'wait_until': 'domcontentloaded',  # Less strict than 'networkidle'
    'viewport': {
        'width': 1920,
        'height': 1080
    }
}


@dataclass
class ScraperSettings:
    """Settings for BILL.com scraper."""

    # Credentials
    login_email: str
    login_password: str

    # Company
    company_name: str

    # File paths
    csv_file_path: Optional[str]
    output_dir: Path

    # Browser settings
    headless: bool
    timeout: int
    wait_until: str
    viewport_width: int
    viewport_height: int

    @classmethod
    def from_env(cls, csv_file_override: Optional[str] = None) -> "ScraperSettings":
        """Create settings from environment variables."""
        login_email = os.getenv('BILL_LOGIN_EMAIL') or os.getenv('BILL_EMAIL') or ''
        login_password = os.getenv('BILL_LOGIN_PASSWORD') or os.getenv('BILL_PASSWORD') or ''
        company_name = os.getenv('BILL_COMPANY_NAME', 'Vai Consulting')
        csv_file_path = csv_file_override or os.getenv('BILL_CSV_FILE_PATH', '')

        # Output directory relative to scraping folder
        output_dir = Path(__file__).parent.parent / 'output'
        output_dir.mkdir(exist_ok=True)

        return cls(
            login_email=login_email,
            login_password=login_password,
            company_name=company_name,
            csv_file_path=csv_file_path if csv_file_path else None,
            output_dir=output_dir,
            headless=CONFIG['headless'],
            timeout=CONFIG['timeout'],
            wait_until=CONFIG['wait_until'],
            viewport_width=CONFIG['viewport']['width'],
            viewport_height=CONFIG['viewport']['height'],
        )

    def validate_credentials(self) -> None:
        """Validate that credentials are set."""
        if not self.login_email or not self.login_password:
            raise ValueError(
                'Credentials not found. Configure BILL_LOGIN_EMAIL and '
                'BILL_LOGIN_PASSWORD in the .env file'
            )
