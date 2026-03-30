"""Base page object with common functionality."""

from typing import Optional, List
from playwright.sync_api import Page, ElementHandle


class BasePage:
    """Base class for all page objects."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize base page.

        Args:
            page: Playwright page instance
            debug: Whether to print debug messages
        """
        self.page = page
        self.debug = debug

    def log(self, level: str, message: str) -> None:
        """Print log message."""
        if self.debug or level in ('INFO', 'ERROR', 'WARN'):
            print(f'[{level}] {message}')

    def wait(self, ms: int = 1000) -> None:
        """Wait for specified milliseconds."""
        self.page.wait_for_timeout(ms)

    def find_element(
        self,
        selector: str,
        timeout: int = 10000,
        state: str = 'visible'
    ) -> Optional[ElementHandle]:
        """Find element with error handling."""
        try:
            return self.page.wait_for_selector(selector, timeout=timeout, state=state)
        except Exception:
            return None

    def find_elements(self, selector: str) -> List[ElementHandle]:
        """Find all matching elements."""
        return self.page.query_selector_all(selector)

    def click_element(
        self,
        selector: str,
        timeout: int = 10000,
        wait_after: int = 500
    ) -> bool:
        """Click element by selector."""
        element = self.find_element(selector, timeout)
        if element:
            element.click()
            self.wait(wait_after)
            return True
        return False

    def type_text(
        self,
        selector: str,
        text: str,
        clear_first: bool = True,
        delay: int = 50
    ) -> bool:
        """Type text into element."""
        element = self.find_element(selector)
        if not element:
            return False

        element.click()
        self.wait(200)

        if clear_first:
            element.press('Control+a')
            self.wait(100)

        element.type(text, delay=delay)
        self.wait(300)
        return True

    def find_button_by_text(self, text_patterns: List[str]) -> Optional[ElementHandle]:
        """Find button containing any of the text patterns."""
        buttons = self.find_elements('button')
        for button in buttons:
            try:
                button_text = button.inner_text().strip().lower()
                for pattern in text_patterns:
                    if pattern.lower() in button_text:
                        return button
            except Exception:
                continue
        return None
