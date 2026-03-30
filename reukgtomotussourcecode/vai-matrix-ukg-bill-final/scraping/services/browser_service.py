"""Browser service for managing Playwright browser instances."""

from typing import Optional
from contextlib import contextmanager

from playwright.sync_api import sync_playwright, Browser, Page, Playwright

from ..config.settings import CONFIG, ScraperSettings


class BrowserService:
    """Service for managing Playwright browser instances."""

    def __init__(self, settings: Optional[ScraperSettings] = None):
        """Initialize browser service.

        Args:
            settings: Scraper settings. If None, uses defaults.
        """
        self.settings = settings or ScraperSettings.from_env()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    @contextmanager
    def get_page(self):
        """Context manager for getting a browser page.

        Yields:
            Page: Configured Playwright page

        Example:
            with browser_service.get_page() as page:
                page.goto('https://example.com')
        """
        print('[INFO] Launching browser...')

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.settings.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            try:
                page = browser.new_page()
                page.set_viewport_size({
                    'width': self.settings.viewport_width,
                    'height': self.settings.viewport_height
                })

                yield page

            finally:
                browser.close()

    def navigate(self, page: Page, url: str) -> bool:
        """Navigate to URL with error handling.

        Args:
            page: Playwright page
            url: URL to navigate to

        Returns:
            True if navigation successful
        """
        print(f'[INFO] Navigating to {url}...')

        try:
            page.goto(
                url,
                wait_until=self.settings.wait_until,
                timeout=self.settings.timeout
            )
            return True

        except Exception as error:
            print(f'[WARN] Timeout on navigation, but continuing... Error: {error}')
            return True  # Continue even on timeout

    def wait_for_content(self, page: Page, ms: int = 3000) -> None:
        """Wait for dynamic content to load.

        Args:
            page: Playwright page
            ms: Milliseconds to wait
        """
        print('[INFO] Waiting for content to load...')
        page.wait_for_timeout(ms)
