"""
Company selection page object for BILL.com.

Handles:
- Company list navigation
- Company selection by name
- Post-login company selection flow
"""

import logging
from typing import Optional, List, Any, TYPE_CHECKING
from urllib.parse import urlparse

# Conditional import for playwright
try:
    from playwright.sync_api import Page
except ImportError:
    if TYPE_CHECKING:
        from playwright.sync_api import Page
    else:
        Page = Any

from src.infrastructure.adapters.scraping.page_objects.base_page import (
    BasePage,
    PageObjectError,
    ElementNotFoundError,
)
from src.infrastructure.config.selectors import SelectorConfig


logger = logging.getLogger(__name__)


class CompanySelectionError(PageObjectError):
    """Raised when company selection fails."""

    pass


class CompanyNotFoundError(CompanySelectionError):
    """Raised when the requested company is not found in the list."""

    pass


class CompanyPage(BasePage):
    """
    Page object for BILL.com company selection and navigation.

    Used after login when user has access to multiple companies.
    """

    def __init__(
        self,
        page: Page,
        selectors: Optional[SelectorConfig] = None,
    ):
        """
        Initialize company page.

        Args:
            page: Playwright page instance.
            selectors: Optional selector configuration.
        """
        super().__init__(page, selectors)
        self._current_company_id: Optional[str] = None

    @property
    def current_company_id(self) -> Optional[str]:
        """Get the current company ID from URL."""
        parsed = urlparse(self.url)
        path = parsed.path

        if "/companies/" in path:
            parts = path.split("/companies/")
            if len(parts) > 1:
                company_id = parts[1].split("/")[0]
                return company_id

        return self._current_company_id

    def select_company(self, company_name: str) -> bool:
        """
        Select a company from the company list.

        Args:
            company_name: Name of the company to select.

        Returns:
            True if company was selected successfully.

        Raises:
            CompanyNotFoundError: If company is not found in the list.
            CompanySelectionError: If selection fails.
        """
        logger.info(f"Selecting company: {company_name}")

        # Wait for company list to load
        self.wait(2000)

        try:
            # Strategy 1: XPath with company name
            if self._select_by_xpath(company_name):
                return True

            # Strategy 2: Search in table cells
            if self._select_from_cells(company_name):
                return True

            # Strategy 3: Search all divs containing the text
            if self._select_by_text_search(company_name):
                return True

            raise CompanyNotFoundError(f"Company '{company_name}' not found in list")

        except CompanyNotFoundError:
            raise
        except Exception as e:
            self._capture_error_screenshot("company_selection_failed")
            raise CompanySelectionError(f"Failed to select company: {e}") from e

    def _select_by_xpath(self, company_name: str) -> bool:
        """Try to select company using XPath."""
        xpath_template = self.selectors.company_selection.company_by_name_xpath
        xpath = f"xpath={xpath_template.format(company_name=company_name)}"

        try:
            locator = self.page.locator(xpath)
            locator.wait_for(state="visible", timeout=self.timeouts.medium)

            locator.scroll_into_view_if_needed()
            self.wait(300)
            locator.click()

            self._wait_for_company_load()
            logger.info(f"Selected company '{company_name}' via XPath")
            return True

        except Exception as e:
            logger.debug(f"XPath selection failed: {e}")
            return False

    def _select_from_cells(self, company_name: str) -> bool:
        """Try to select company from table cells."""
        for selector in self.selectors.company_selection.company_cell:
            try:
                cells = self.page.locator(selector).all()

                for cell in cells:
                    try:
                        text = cell.inner_text().strip()
                        if company_name.lower() in text.lower():
                            cell.scroll_into_view_if_needed()
                            self.wait(300)
                            cell.click()

                            self._wait_for_company_load()
                            logger.info(f"Selected company '{company_name}' from cell")
                            return True
                    except Exception:
                        continue

            except Exception as e:
                logger.debug(f"Cell search failed with {selector}: {e}")
                continue

        return False

    def _select_by_text_search(self, company_name: str) -> bool:
        """Try to select company by searching all text content."""
        try:
            # Find all elements that might contain the company name
            locator = self.page.get_by_text(company_name, exact=False)

            if locator.count() > 0:
                # Click the first visible match
                for i in range(locator.count()):
                    element = locator.nth(i)
                    try:
                        if element.is_visible():
                            element.scroll_into_view_if_needed()
                            self.wait(300)
                            element.click()

                            self._wait_for_company_load()
                            logger.info(f"Selected company '{company_name}' via text search")
                            return True
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"Text search failed: {e}")

        return False

    def _wait_for_company_load(self) -> None:
        """Wait for company dashboard to load after selection."""
        self.wait(2000)
        self.wait_for_navigation(timeout=self.timeouts.default)
        self.wait(2000)

        # Update current company ID
        self._current_company_id = self.current_company_id

    def get_available_companies(self) -> List[str]:
        """
        Get list of available company names.

        Returns:
            List of company names found in the selection list.
        """
        companies = []

        for selector in self.selectors.company_selection.company_cell:
            try:
                cells = self.page.locator(selector).all()

                for cell in cells:
                    try:
                        text = cell.inner_text().strip()
                        if text and text not in companies:
                            companies.append(text)
                    except Exception:
                        continue

            except Exception:
                continue

        return companies

    def navigate_to_people(self) -> bool:
        """
        Navigate to the People page for the current company.

        Returns:
            True if navigation was successful.

        Raises:
            CompanySelectionError: If navigation fails.
        """
        logger.info("Navigating to People page...")

        try:
            company_id = self.current_company_id
            if not company_id:
                raise CompanySelectionError("No company selected - cannot navigate to People page")

            # Build people URL
            parsed = urlparse(self.url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            people_url = f"{base_url}/companies/{company_id}/people"

            logger.info(f"Navigating to: {people_url}")
            self.goto(people_url)

            # Close any popup that appears
            self.close_popup()

            # Wait for page to load
            self.wait(3000)
            self.wait_for_loading_complete()

            logger.info("Successfully navigated to People page")
            return True

        except Exception as e:
            self._capture_error_screenshot("people_navigation_failed")
            raise CompanySelectionError(f"Failed to navigate to People page: {e}") from e

    def is_on_company_list(self) -> bool:
        """
        Check if we're on the company selection page.

        Returns:
            True if company list is visible.
        """
        try:
            for selector in self.selectors.company_selection.company_list:
                locator = self.page.locator(selector)
                if locator.count() > 0 and locator.first.is_visible():
                    return True
        except Exception:
            pass

        # Also check if we have company cells visible
        try:
            for selector in self.selectors.company_selection.company_cell:
                locator = self.page.locator(selector)
                if locator.count() > 0:
                    return True
        except Exception:
            pass

        return False

    def is_on_company_dashboard(self) -> bool:
        """
        Check if we're on a company dashboard (successfully selected company).

        Returns:
            True if on company dashboard.
        """
        return self.current_company_id is not None
