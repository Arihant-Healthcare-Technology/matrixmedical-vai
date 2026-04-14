#!/usr/bin/env python3
"""
Upsert TravelPerk users via SCIM API.

Usage:
    python upsert-travelperk-user.py <employeeNumber> [--dry-run]

Environment (.env):
    TRAVELPERK_API_BASE=https://app.sandbox-travelperk.com
    TRAVELPERK_API_KEY=your-api-key
    DEBUG=1  # optional
    MAX_RETRIES=2  # optional
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

from src.presentation.cli.upsert_user import main

if __name__ == "__main__":
    main()
