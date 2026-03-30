"""Company selector page object."""

from playwright.sync_api import Page

from .base import BasePage
from ..config.selectors import Selectors


class CompanySelector(BasePage):
    """Page object for selecting company after login."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize company selector."""
        super().__init__(page, debug)

    def select_company(self, company_name: str) -> bool:
        """Select a company from the list.

        Args:
            company_name: Name of company to select

        Returns:
            True if company selected, False if not found
        """
        self.log('INFO', f'Looking for company: {company_name}...')

        try:
            self.log('INFO', 'Waiting for companies list to load...')
            self.wait(2000)

            # Try XPath strategy first
            if self._select_by_xpath(company_name):
                return True

            # Try cell selector strategy
            if self._select_by_cell(company_name):
                return True

            raise ValueError(f'Company "{company_name}" not found in list')

        except Exception as error:
            error_msg = str(error)
            if 'timeout' in error_msg.lower() or 'waiting for selector' in error_msg.lower():
                self.log('WARN', f'Could not find company "{company_name}", continuing...')
                return False
            self.log('ERROR', f'Error selecting company: {error}')
            raise

    def _select_by_xpath(self, company_name: str) -> bool:
        """Try to select company using XPath."""
        xpath = Selectors.Company.COMPANY_XPATH_TEMPLATE.format(company_name=company_name)

        try:
            company_element = self.page.wait_for_selector(
                f'xpath={xpath}',
                timeout=10000,
                state='visible'
            )
            self.log('INFO', f'Company "{company_name}" found')

            company_element.scroll_into_view_if_needed()
            self.wait(500)

            self.log('INFO', f'Clicking on company "{company_name}"...')
            company_element.click()
            self.wait(2000)

            self.log('INFO', f'Company "{company_name}" selected successfully')
            self.wait(2000)
            return True

        except Exception as error:
            self.log('WARN', 'Not found with XPath, trying another strategy...')
            return False

    def _select_by_cell(self, company_name: str) -> bool:
        """Try to select company using cell selectors."""
        try:
            cells = self.find_elements(Selectors.Company.COMPANY_CELL)

            for cell in cells:
                text = cell.inner_text().strip()
                if company_name.lower() in text.lower():
                    self.log('INFO', f'Company "{company_name}" found in cell')

                    cell.scroll_into_view_if_needed()
                    self.wait(500)

                    cell.click()
                    self.wait(2000)

                    self.log('INFO', f'Company "{company_name}" selected successfully')
                    return True

            return False

        except Exception as error:
            self.log('ERROR', f'Error searching for company: {error}')
            return False
