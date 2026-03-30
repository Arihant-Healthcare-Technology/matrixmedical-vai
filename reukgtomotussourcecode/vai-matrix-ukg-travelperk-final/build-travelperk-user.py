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

from src.presentation.cli.build_user import main

if __name__ == "__main__":
    main()
