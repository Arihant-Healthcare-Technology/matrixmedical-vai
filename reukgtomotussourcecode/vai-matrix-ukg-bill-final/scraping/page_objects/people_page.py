"""People page object."""

from urllib.parse import urlparse

from playwright.sync_api import Page

from .base import BasePage
from .popup_handler import PopupHandler
from ..config.settings import CONFIG
from ..config.selectors import Selectors


class PeoplePage(BasePage):
    """Page object for BILL.com people page."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize people page."""
        super().__init__(page, debug)
        self.popup_handler = PopupHandler(page, debug)

    def navigate_to_people(self) -> bool:
        """Navigate to /people page from current URL.

        Returns:
            True if navigation successful
        """
        try:
            current_url = self.page.url
            self.log('INFO', f'Current URL: {current_url}')

            people_url = self._build_people_url(current_url)
            self.log('INFO', f'Navigating to people page: {people_url}')

            self.page.goto(
                people_url,
                wait_until=CONFIG['wait_until'],
                timeout=CONFIG['timeout']
            )

            # Close popup after navigation
            self.popup_handler.close_popup()

            self.wait(3000)
            self.log('INFO', 'Successfully navigated to people page')
            return True

        except Exception as error:
            self.log('ERROR', f'Error navigating to people page: {error}')
            return False

    def _build_people_url(self, current_url: str) -> str:
        """Build URL for people page."""
        parsed_url = urlparse(current_url)
        base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
        current_path = parsed_url.path

        if '/companies/' in current_path:
            parts = current_path.split('/companies/')
            if len(parts) > 1:
                company_id = parts[1].split('/')[0]
                return f'{base_url}/companies/{company_id}/people'
            else:
                if current_path.endswith('/'):
                    return f'{base_url}{current_path}people'
                return f'{base_url}{current_path}/people'

        return f'{base_url}/people'

    def click_import_people_button(self) -> bool:
        """Click on the 'Import People' button.

        Returns:
            True if button clicked successfully

        Raises:
            ValueError: If button not found
        """
        self.log('INFO', 'Looking for "Import People" button...')

        try:
            self.wait(2000)

            # Strategy 1: Find by data-testid
            if self._click_import_by_testid():
                return True

            # Strategy 2: Find by text content
            if self._click_import_by_text():
                return True

            # Strategy 3: Find via span text
            if self._click_import_by_span():
                return True

            # Strategy 4: Find by aria-label
            if self._click_import_by_aria():
                return True

            raise ValueError('Could not find "Import People" button')

        except Exception as error:
            self.log('ERROR', f'Error clicking Import People button: {error}')
            raise

    def _click_import_by_testid(self) -> bool:
        """Try to click import button by data-testid."""
        try:
            import_button = self.find_element(
                Selectors.Import.IMPORT_BUTTON_TESTID,
                timeout=10000
            )
            if import_button:
                self.log('INFO', 'Import People button found by data-testid')
                import_button.click()
                self.wait(2000)
                self.log('INFO', 'Clicked Import People button successfully')
                return True
        except Exception as error:
            self.log('DEBUG', f'Method 1 failed: {error}')
        return False

    def _click_import_by_text(self) -> bool:
        """Try to click import button by text."""
        try:
            buttons = self.find_elements('button')
            for button in buttons:
                text = button.inner_text().strip()
                if 'import people' in text.lower() or 'import' in text.lower():
                    if button.is_visible():
                        self.log('INFO', f'Import People button found by text: "{text}"')
                        button.click()
                        self.wait(2000)
                        self.log('INFO', 'Clicked Import People button successfully')
                        return True
        except Exception as error:
            self.log('DEBUG', f'Method 2 failed: {error}')
        return False

    def _click_import_by_span(self) -> bool:
        """Try to click import button via span text."""
        try:
            spans = self.find_elements('span')
            for span in spans:
                text = span.inner_text().strip()
                if 'import people' in text.lower():
                    try:
                        button = self.page.query_selector(f'button:has(span:has-text("{text}"))')
                        if button and button.is_visible():
                            self.log('INFO', 'Import People button found via span text')
                            button.click()
                            self.wait(2000)
                            self.log('INFO', 'Clicked Import People button successfully')
                            return True
                    except Exception:
                        pass
        except Exception as error:
            self.log('DEBUG', f'Method 3 failed: {error}')
        return False

    def _click_import_by_aria(self) -> bool:
        """Try to click import button by aria-label."""
        try:
            import_buttons = self.find_elements(Selectors.Import.IMPORT_BUTTON_ARIA)
            for btn in import_buttons:
                if btn.is_visible():
                    self.log('INFO', 'Import People button found by aria-label')
                    btn.click()
                    self.wait(2000)
                    self.log('INFO', 'Clicked Import People button successfully')
                    return True
        except Exception as error:
            self.log('DEBUG', f'Method 4 failed: {error}')
        return False
