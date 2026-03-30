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

from src.presentation.cli.upsert_user import main

if __name__ == "__main__":
    main()
