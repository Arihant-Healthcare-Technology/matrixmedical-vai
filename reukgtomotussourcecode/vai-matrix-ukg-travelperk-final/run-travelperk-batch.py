#!/usr/bin/env python3
"""
Run TravelPerk batch synchronization.

Usage:
    python run-travelperk-batch.py --company-id J9A6Y [options]

Options:
    --company-id ID          UKG company ID (required)
    --states FL,MS,NJ        Comma-separated US states to filter
    --workers N              Thread pool size (default: 12)
    --dry-run                Validate but do not POST/PUT to TravelPerk
    --save-local             Write JSON files to data/batch
    --limit N                Limit number of users (for testing)
    --insert-supervisor IDs  Pre-insert supervisors (comma-separated)
    --employee-type-codes    Filter by employeeTypeCode (comma-separated)

Environment (.env):
    COMPANY_ID=J9A6Y
    STATES=FL,MS,NJ
    WORKERS=12
    DRY_RUN=1
    SAVE_LOCAL=1
    TRAVELPERK_API_KEY=your-api-key
    DEBUG=1
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
# This ensures all settings modules can access the env vars
_env_file = os.getenv("ENV_FILE", ".env")
_env_path = Path(_env_file)
if _env_path.exists():
    load_dotenv(_env_path)
elif Path(".env").exists():
    load_dotenv(Path(".env"))

from src.presentation.cli.batch_runner import main

if __name__ == "__main__":
    main()
