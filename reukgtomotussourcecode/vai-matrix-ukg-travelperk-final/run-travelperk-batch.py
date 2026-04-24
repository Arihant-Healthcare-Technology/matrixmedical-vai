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
    DEBUG=1                  # Enables DEBUG log level (same as LOG_LEVEL=DEBUG)
    LOG_LEVEL=DEBUG          # Explicit log level (DEBUG, INFO, WARNING, ERROR)
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# =============================================================================
# STARTUP BANNER - Print immediately for container log visibility
# =============================================================================
def print_startup_banner():
    """Print application startup banner with timestamp."""
    print("=" * 80, flush=True)
    print("UKG-TRAVELPERK INTEGRATION - APPLICATION STARTING", flush=True)
    print("=" * 80, flush=True)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z", flush=True)
    print(f"Python Version: {sys.version.split()[0]}", flush=True)
    print(f"Working Directory: {os.getcwd()}", flush=True)
    print("-" * 80, flush=True)

def print_env_config():
    """Print environment configuration (with sensitive values masked)."""
    print("ENVIRONMENT CONFIGURATION:", flush=True)

    # UKG Settings
    print("  [UKG API]", flush=True)
    print(f"    UKG_BASE_URL: {os.getenv('UKG_BASE_URL', 'NOT SET')}", flush=True)
    ukg_key = os.getenv('UKG_CUSTOMER_API_KEY', '')
    print(f"    UKG_CUSTOMER_API_KEY: {ukg_key[:4] + '****' if ukg_key else 'NOT SET'}", flush=True)
    print(f"    UKG_USERNAME: {'SET' if os.getenv('UKG_USERNAME') else 'NOT SET'}", flush=True)
    print(f"    UKG_PASSWORD: {'SET' if os.getenv('UKG_PASSWORD') else 'NOT SET'}", flush=True)
    print(f"    UKG_BASIC_B64: {'SET' if os.getenv('UKG_BASIC_B64') else 'NOT SET'}", flush=True)
    print(f"    UKG_TIMEOUT: {os.getenv('UKG_TIMEOUT', '45 (default)')}", flush=True)

    # TravelPerk Settings
    print("  [TravelPerk API]", flush=True)
    print(f"    TRAVELPERK_API_BASE: {os.getenv('TRAVELPERK_API_BASE', 'NOT SET')}", flush=True)
    tp_key = os.getenv('TRAVELPERK_API_KEY', '')
    print(f"    TRAVELPERK_API_KEY: {tp_key[:8] + '****' if tp_key else 'NOT SET'}", flush=True)
    print(f"    TRAVELPERK_TIMEOUT: {os.getenv('TRAVELPERK_TIMEOUT', '60 (default)')}", flush=True)

    # Batch Settings
    print("  [Batch Processing]", flush=True)
    print(f"    COMPANY_ID: {os.getenv('COMPANY_ID', 'NOT SET')}", flush=True)
    print(f"    STATES: {os.getenv('STATES', 'ALL')}", flush=True)
    print(f"    EMPLOYEE_TYPE_CODES: {os.getenv('EMPLOYEE_TYPE_CODES', 'ALL')}", flush=True)
    print(f"    WORKERS: {os.getenv('WORKERS', '12 (default)')}", flush=True)
    print(f"    DRY_RUN: {os.getenv('DRY_RUN', '0 (default)')}", flush=True)
    print(f"    SAVE_LOCAL: {os.getenv('SAVE_LOCAL', '0 (default)')}", flush=True)
    print(f"    LIMIT: {os.getenv('LIMIT', 'None')}", flush=True)
    print(f"    OUT_DIR: {os.getenv('OUT_DIR', 'data/batch (default)')}", flush=True)

    # Logging Settings
    print("  [Logging]", flush=True)
    log_level_env = os.getenv('LOG_LEVEL', '')
    debug_env = os.getenv('DEBUG', '0')
    # Calculate effective log level (same logic as configure_logging)
    if log_level_env:
        effective_level = log_level_env.upper()
    elif debug_env == '1':
        effective_level = 'DEBUG (via DEBUG=1)'
    else:
        effective_level = 'INFO (default)'
    print(f"    LOG_LEVEL: {os.getenv('LOG_LEVEL', 'not set')}", flush=True)
    print(f"    DEBUG: {debug_env}", flush=True)
    print(f"    EFFECTIVE LOG LEVEL: {effective_level}", flush=True)
    print(f"    REDACT_PII: {os.getenv('REDACT_PII', '1 (default)')}", flush=True)

    # Runtime Settings
    print("  [Runtime]", flush=True)
    print(f"    PYTHONUNBUFFERED: {os.getenv('PYTHONUNBUFFERED', 'NOT SET')}", flush=True)
    print(f"    PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}", flush=True)
    print(f"    DATA_DIR: {os.getenv('DATA_DIR', 'NOT SET')}", flush=True)
    print(f"    ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT SET')}", flush=True)

    print("-" * 80, flush=True)

# Print startup banner immediately
print_startup_banner()

# =============================================================================
# Load environment variables from .env file before any other imports
# This ensures all settings modules can access the env vars
# =============================================================================
_script_dir = Path(__file__).parent.resolve()
_env_file = os.getenv("ENV_FILE")

print("LOADING ENVIRONMENT:", flush=True)
if _env_file:
    # Use explicitly provided ENV_FILE
    _env_path = Path(_env_file)
    if _env_path.exists():
        load_dotenv(_env_path)
        print(f"  Loaded env from: {_env_path}", flush=True)
    else:
        print(f"  WARNING: ENV_FILE specified but not found: {_env_path}", flush=True)
else:
    # Look for .env relative to script location
    _env_path = _script_dir / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
        print(f"  Loaded env from: {_env_path}", flush=True)
    elif Path(".env").exists():
        load_dotenv(Path(".env"))
        print(f"  Loaded env from: .env (current directory)", flush=True)
    else:
        print("  No .env file found, using environment variables only", flush=True)

print("-" * 80, flush=True)

# Print environment configuration after loading .env
print_env_config()

print("INITIALIZING APPLICATION...", flush=True)
print("=" * 80, flush=True)

from src.presentation.cli.batch_runner import main

if __name__ == "__main__":
    main()
