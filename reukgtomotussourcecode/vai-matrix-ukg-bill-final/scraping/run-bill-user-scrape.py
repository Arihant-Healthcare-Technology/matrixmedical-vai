#!/usr/bin/env python3
"""
BILL.com User Import Scraper

Automates user import via BILL.com web interface using Playwright.

Usage:
    python run-bill-user-scrape.py <URL> [CSV_FILE_PATH]

Example:
    python run-bill-user-scrape.py https://app.bill.com/users
    python run-bill-user-scrape.py https://app.bill.com/users /path/to/users.csv

Environment Variables:
    BILL_LOGIN_EMAIL    - Login email
    BILL_LOGIN_PASSWORD - Login password
    BILL_COMPANY_NAME   - Company to select (default: 'Vai Consulting')
    BILL_CSV_FILE_PATH  - CSV file to import (optional)

Requirements:
    pip install playwright python-dotenv
    playwright install chromium
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping.cli import main

if __name__ == '__main__':
    main()
