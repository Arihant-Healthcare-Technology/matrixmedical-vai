"""
Page Object Model for BILL.com UI automation.

Provides structured, maintainable page objects for Playwright-based
browser automation.
"""

from src.infrastructure.adapters.scraping.page_objects.base_page import BasePage
from src.infrastructure.adapters.scraping.page_objects.login_page import LoginPage
from src.infrastructure.adapters.scraping.page_objects.company_page import CompanyPage
from src.infrastructure.adapters.scraping.page_objects.import_page import ImportPage

__all__ = [
    "BasePage",
    "LoginPage",
    "CompanyPage",
    "ImportPage",
]
