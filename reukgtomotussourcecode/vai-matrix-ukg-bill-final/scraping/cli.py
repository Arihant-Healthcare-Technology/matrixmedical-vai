#!/usr/bin/env python3
"""CLI entry point for BILL.com scraper."""

import sys
import traceback

from .config.settings import ScraperSettings
from .orchestrator import BillScraperOrchestrator


def main() -> None:
    """Main CLI entry point."""
    # URL is optional - if not provided, scraping will be skipped
    url = None
    csv_file_override = None

    if len(sys.argv) >= 2:
        url = sys.argv[1]

    # Get CSV file path from argument or environment
    if len(sys.argv) >= 3:
        csv_file_override = sys.argv[2]
        print(f'[INFO] CSV file path from argument: {csv_file_override}')

    if not url:
        print('[INFO] No URL provided - scraping functionality will be skipped')
        print('[INFO] Usage: python -m scraping.cli [URL] [CSV_FILE_PATH]')
        print('[INFO] For S&E API operations, use: python -m src.presentation.cli.main sync --all')
        sys.exit(0)

    try:
        # Load settings
        settings = ScraperSettings.from_env(csv_file_override=csv_file_override)

        if settings.csv_file_path:
            print(f'[INFO] CSV file path: {settings.csv_file_path}')

        # Run scraper
        orchestrator = BillScraperOrchestrator(settings)
        orchestrator.scrape(url)

        print('[INFO] Process completed successfully')
        sys.exit(0)

    except Exception as error:
        print(f'[ERROR] Process failed: {error}')
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
