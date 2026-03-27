"""
Base page object with common functionality for all page objects.

Provides:
- Selector resolution with fallback support
- Wait helpers with retry logic
- Screenshot capture for debugging
- Common UI interactions (click, type, etc.)
"""

import logging
from pathlib import Path
from typing import List, Optional, Any, Callable, TypeVar, TYPE_CHECKING
from datetime import datetime

# Conditional import for playwright - allows module to be imported without playwright installed
try:
    from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Type stubs for when playwright is not available
    if TYPE_CHECKING:
        from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeout
    else:
        Page = Any
        Locator = Any
        PlaywrightTimeout = Exception

from src.infrastructure.config.selectors import SelectorConfig, get_selectors


logger = logging.getLogger(__name__)

T = TypeVar("T")


class PageObjectError(Exception):
    """Base exception for page object errors."""

    pass


class ElementNotFoundError(PageObjectError):
    """Raised when an element cannot be found with any selector."""

    pass


class ActionError(PageObjectError):
    """Raised when a page action fails."""

    pass


class BasePage:
    """
    Base page object providing common functionality for all pages.

    Features:
    - Multi-selector support with automatic fallback
    - Configurable timeouts from selectors.yaml
    - Automatic screenshot capture on errors
    - Logging integration
    """

    def __init__(
        self,
        page: Page,
        selectors: Optional[SelectorConfig] = None,
        screenshot_dir: Optional[Path] = None,
    ):
        """
        Initialize base page.

        Args:
            page: Playwright page instance.
            selectors: Optional selector configuration. Uses global if not provided.
            screenshot_dir: Directory for error screenshots.
        """
        self.page = page
        self.selectors = selectors or get_selectors()
        self.screenshot_dir = screenshot_dir or Path("output/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    @property
    def timeouts(self):
        """Get timeout configuration."""
        return self.selectors.timeouts

    @property
    def url(self) -> str:
        """Get current page URL."""
        return self.page.url

    def wait(self, milliseconds: int) -> None:
        """
        Wait for a specified time.

        Args:
            milliseconds: Time to wait in milliseconds.
        """
        self.page.wait_for_timeout(milliseconds)

    def find_element(
        self,
        selectors: List[str],
        timeout: Optional[int] = None,
        state: str = "visible",
    ) -> Locator:
        """
        Find an element using multiple selectors with fallback.

        Tries each selector in order until one succeeds.

        Args:
            selectors: List of CSS/XPath selectors to try.
            timeout: Timeout in milliseconds. Uses default if not specified.
            state: Element state to wait for ('visible', 'attached', 'hidden').

        Returns:
            Playwright Locator for the found element.

        Raises:
            ElementNotFoundError: If no selector finds the element.
        """
        if timeout is None:
            timeout = self.timeouts.medium

        last_error = None

        for selector in selectors:
            try:
                locator = self.page.locator(selector)
                locator.wait_for(state=state, timeout=timeout)
                logger.debug(f"Found element with selector: {selector}")
                return locator
            except PlaywrightTimeout as e:
                logger.debug(f"Selector failed: {selector}")
                last_error = e
                continue
            except Exception as e:
                logger.debug(f"Selector error: {selector} - {e}")
                last_error = e
                continue

        # Capture screenshot on failure
        self._capture_error_screenshot("element_not_found")

        raise ElementNotFoundError(
            f"Could not find element with any of {len(selectors)} selectors. "
            f"Tried: {selectors[:3]}{'...' if len(selectors) > 3 else ''}"
        ) from last_error

    def find_element_optional(
        self,
        selectors: List[str],
        timeout: Optional[int] = None,
    ) -> Optional[Locator]:
        """
        Find an element optionally (returns None if not found).

        Args:
            selectors: List of CSS/XPath selectors to try.
            timeout: Timeout in milliseconds.

        Returns:
            Locator if found, None otherwise.
        """
        if timeout is None:
            timeout = self.timeouts.short

        try:
            return self.find_element(selectors, timeout=timeout)
        except ElementNotFoundError:
            return None

    def query_element(self, selector: str) -> Optional[Locator]:
        """
        Query for an element without waiting.

        Args:
            selector: CSS selector.

        Returns:
            Locator if element exists, None otherwise.
        """
        locator = self.page.locator(selector)
        if locator.count() > 0:
            return locator
        return None

    def click(
        self,
        selectors: List[str],
        timeout: Optional[int] = None,
        delay: int = 200,
    ) -> None:
        """
        Click on an element found by selectors.

        Args:
            selectors: List of selectors to try.
            timeout: Timeout in milliseconds.
            delay: Delay after click in milliseconds.
        """
        try:
            element = self.find_element(selectors, timeout=timeout)
            element.scroll_into_view_if_needed()
            self.wait(100)
            element.click()
            self.wait(delay)
            logger.debug(f"Clicked element")
        except Exception as e:
            self._capture_error_screenshot("click_failed")
            raise ActionError(f"Failed to click element: {e}") from e

    def type_text(
        self,
        selectors: List[str],
        text: str,
        clear_first: bool = True,
        timeout: Optional[int] = None,
        typing_delay: int = 50,
    ) -> None:
        """
        Type text into an input field.

        Args:
            selectors: List of selectors for the input field.
            text: Text to type.
            clear_first: Whether to clear existing text first.
            timeout: Timeout in milliseconds.
            typing_delay: Delay between keystrokes in milliseconds.
        """
        try:
            element = self.find_element(selectors, timeout=timeout)
            element.click()
            self.wait(100)

            if clear_first:
                element.press("Control+a")
                self.wait(50)

            element.type(text, delay=typing_delay)
            self.wait(200)
            logger.debug(f"Typed {len(text)} characters into input")
        except Exception as e:
            self._capture_error_screenshot("type_failed")
            raise ActionError(f"Failed to type text: {e}") from e

    def get_text(
        self,
        selectors: List[str],
        timeout: Optional[int] = None,
    ) -> str:
        """
        Get text content of an element.

        Args:
            selectors: List of selectors to try.
            timeout: Timeout in milliseconds.

        Returns:
            Text content of the element.
        """
        element = self.find_element(selectors, timeout=timeout)
        return element.inner_text().strip()

    def is_visible(
        self,
        selectors: List[str],
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Check if an element is visible.

        Args:
            selectors: List of selectors to try.
            timeout: Timeout in milliseconds.

        Returns:
            True if element is visible, False otherwise.
        """
        if timeout is None:
            timeout = self.timeouts.short

        try:
            element = self.find_element(selectors, timeout=timeout)
            return element.is_visible()
        except ElementNotFoundError:
            return False

    def wait_for_navigation(self, timeout: Optional[int] = None) -> None:
        """
        Wait for navigation to complete.

        Args:
            timeout: Timeout in milliseconds.
        """
        if timeout is None:
            timeout = self.timeouts.default

        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeout:
            logger.warning("Navigation timeout - continuing anyway")
            self.wait(self.timeouts.page_load)

    def wait_for_url_contains(
        self,
        substring: str,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Wait for URL to contain a substring.

        Args:
            substring: Expected substring in URL.
            timeout: Timeout in milliseconds.

        Returns:
            True if URL contains substring, False on timeout.
        """
        if timeout is None:
            timeout = self.timeouts.default

        try:
            self.page.wait_for_url(f"**/*{substring}*", timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def close_popup(self, max_attempts: int = 3) -> bool:
        """
        Attempt to close any popup/modal.

        Uses selectors from popup configuration.

        Args:
            max_attempts: Maximum number of close attempts.

        Returns:
            True if popup was closed, False otherwise.
        """
        self.wait(1000)  # Wait for popup to appear

        for attempt in range(max_attempts):
            logger.debug(f"Close popup attempt {attempt + 1}/{max_attempts}")

            # Try each close button selector
            for selector in self.selectors.popup.close_button:
                try:
                    locator = self.page.locator(selector)
                    if locator.count() > 0 and locator.first.is_visible():
                        locator.first.click()
                        self.wait(500)
                        logger.info("Popup closed successfully")
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # Try ESC key as fallback
            try:
                self.page.keyboard.press("Escape")
                self.wait(500)

                # Check if modal is gone
                modal_gone = True
                for modal_selector in self.selectors.popup.modal_container:
                    locator = self.page.locator(modal_selector)
                    if locator.count() > 0 and locator.first.is_visible():
                        modal_gone = False
                        break

                if modal_gone:
                    logger.info("Popup closed via ESC key")
                    return True
            except Exception:
                pass

            self.wait(500)

        logger.debug("No popup found or failed to close")
        return False

    def wait_for_loading_complete(self, timeout: Optional[int] = None) -> None:
        """
        Wait for loading indicators to disappear.

        Args:
            timeout: Timeout in milliseconds.
        """
        if timeout is None:
            timeout = self.timeouts.long

        for selector in self.selectors.common.loading:
            try:
                locator = self.page.locator(selector)
                if locator.count() > 0:
                    locator.wait_for(state="hidden", timeout=timeout)
            except PlaywrightTimeout:
                logger.debug(f"Loading indicator timeout: {selector}")
            except Exception:
                pass

    def screenshot(self, name: str = "screenshot") -> Path:
        """
        Capture a screenshot.

        Args:
            name: Base name for the screenshot file.

        Returns:
            Path to the saved screenshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename

        self.page.screenshot(path=str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        return filepath

    def _capture_error_screenshot(self, error_type: str) -> None:
        """Capture screenshot for error debugging."""
        try:
            self.screenshot(f"error_{error_type}")
        except Exception as e:
            logger.warning(f"Failed to capture error screenshot: {e}")

    def retry(
        self,
        action: Callable[[], T],
        max_attempts: int = 3,
        delay: int = 1000,
        on_failure: Optional[Callable[[Exception], None]] = None,
    ) -> T:
        """
        Retry an action with exponential backoff.

        Args:
            action: Callable to retry.
            max_attempts: Maximum number of attempts.
            delay: Initial delay between attempts in milliseconds.
            on_failure: Optional callback on each failure.

        Returns:
            Result of the successful action.

        Raises:
            The last exception if all attempts fail.
        """
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                return action()
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")

                if on_failure:
                    on_failure(e)

                if attempt < max_attempts:
                    wait_time = delay * (2 ** (attempt - 1))
                    self.wait(wait_time)

        raise last_error

    def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: Optional[int] = None,
    ) -> None:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to.
            wait_until: Load state to wait for.
            timeout: Timeout in milliseconds.
        """
        if timeout is None:
            timeout = self.timeouts.default

        try:
            self.page.goto(url, wait_until=wait_until, timeout=timeout)
            logger.info(f"Navigated to: {url}")
        except PlaywrightTimeout:
            logger.warning(f"Navigation timeout for: {url}")
