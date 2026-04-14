#!/usr/bin/env python3
"""
Build a single TravelPerk user payload from UKG.

Usage:
    python build-travelperk-user.py <employeeNumber> <companyID>

Environment (.env):
    UKG_BASE_URL=https://service4.ultipro.com
    UKG_USERNAME=your-username
    UKG_PASSWORD=your-password
    UKG_CUSTOMER_API_KEY=your-customer-api-key
    DEBUG=1  # optional
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
_env_file = os.getenv("ENV_FILE", ".env")
_env_path = Path(_env_file)
if _env_path.exists():
    load_dotenv(_env_path)
elif Path(".env").exists():
    load_dotenv(Path(".env"))

from src.presentation.cli.build_user import main

if __name__ == "__main__":
    main()
