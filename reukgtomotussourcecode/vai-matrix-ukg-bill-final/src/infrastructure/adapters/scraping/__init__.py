"""
Scraping adapters for BILL.com UI automation.

This module provides Playwright-based page objects for automating
BILL.com UI workflows that cannot be accomplished via API.
"""

from src.infrastructure.adapters.scraping.page_objects import (
    BasePage,
    LoginPage,
    CompanyPage,
    ImportPage,
)

__all__ = [
    "BasePage",
    "LoginPage",
    "CompanyPage",
    "ImportPage",
]
