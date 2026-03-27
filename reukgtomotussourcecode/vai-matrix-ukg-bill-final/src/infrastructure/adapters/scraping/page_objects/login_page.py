"""
Login page object for BILL.com authentication.

Handles:
- Email/password login
- Login form detection
- Authentication error handling
"""

import logging
from typing import Optional, Any, TYPE_CHECKING
from dataclasses import dataclass

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


class LoginError(PageObjectError):
    """Raised when login fails."""

    pass


class CredentialsMissingError(LoginError):
    """Raised when login credentials are not provided."""

    pass


@dataclass
class LoginCredentials:
    """Login credentials container."""

    email: str
    password: str

    def validate(self) -> None:
        """Validate that credentials are present."""
        if not self.email:
            raise CredentialsMissingError("Email is required for login")
        if not self.password:
            raise CredentialsMissingError("Password is required for login")


class LoginPage(BasePage):
    """
    Page object for BILL.com login page.

    Usage:
        login_page = LoginPage(page)
        if login_page.is_login_required():
            login_page.login(credentials)
    """

    def __init__(
        self,
        page: Page,
        selectors: Optional[SelectorConfig] = None,
    ):
        """
        Initialize login page.

        Args:
            page: Playwright page instance.
            selectors: Optional selector configuration.
        """
        super().__init__(page, selectors)

    def is_login_required(self, timeout: Optional[int] = None) -> bool:
        """
        Check if we're on a login page.

        Args:
            timeout: Timeout to wait for login form.

        Returns:
            True if login form is present, False otherwise.
        """
        if timeout is None:
            timeout = self.timeouts.short

        logger.info("Checking if login is required...")

        try:
            self.find_element(
                self.selectors.login.email_input,
                timeout=timeout,
            )
            logger.info("Login form detected")
            return True
        except ElementNotFoundError:
            logger.info("No login form detected")
            return False

    def login(
        self,
        credentials: LoginCredentials,
        typing_delay: int = 50,
    ) -> bool:
        """
        Perform login with provided credentials.

        Args:
            credentials: Login credentials.
            typing_delay: Delay between keystrokes in milliseconds.

        Returns:
            True if login was successful.

        Raises:
            LoginError: If login fails.
            CredentialsMissingError: If credentials are missing.
        """
        credentials.validate()

        logger.info(f"Logging in as: {credentials.email[:3]}***")

        try:
            # Enter email
            self._enter_email(credentials.email, typing_delay)

            # Enter password
            self._enter_password(credentials.password, typing_delay)

            # Click login button
            self._click_login_button()

            # Wait for navigation
            self.wait_for_navigation(timeout=self.timeouts.long)
            self.wait(2000)

            # Check for login errors
            if self._has_login_error():
                error_msg = self._get_error_message()
                raise LoginError(f"Login failed: {error_msg}")

            logger.info("Login completed successfully")
            return True

        except CredentialsMissingError:
            raise
        except LoginError:
            raise
        except Exception as e:
            self._capture_error_screenshot("login_failed")
            raise LoginError(f"Login failed: {e}") from e

    def _enter_email(self, email: str, typing_delay: int) -> None:
        """Enter email into login form."""
        logger.debug("Entering email...")

        self.type_text(
            self.selectors.login.email_input,
            email,
            clear_first=True,
            typing_delay=typing_delay,
        )

        logger.debug("Email entered successfully")

    def _enter_password(self, password: str, typing_delay: int) -> None:
        """Enter password into login form."""
        logger.debug("Entering password...")

        self.type_text(
            self.selectors.login.password_input,
            password,
            clear_first=True,
            typing_delay=typing_delay,
        )

        logger.debug("Password entered successfully")

    def _click_login_button(self) -> None:
        """Find and click the login button."""
        logger.debug("Looking for login button...")

        # First try configured selectors
        try:
            self.click(
                self.selectors.login.submit_button,
                timeout=self.timeouts.medium,
                delay=500,
            )
            return
        except ElementNotFoundError:
            logger.debug("Primary selectors failed, trying text-based search")

        # Fallback: search by button text
        login_texts = ["log in", "login", "sign in", "submit"]
        buttons = self.page.locator("button").all()

        for button in buttons:
            try:
                text = button.inner_text().strip().lower()
                if any(login_text in text for login_text in login_texts):
                    logger.debug(f"Found login button by text: '{text}'")
                    button.click()
                    self.wait(500)
                    return
            except Exception:
                continue

        raise ElementNotFoundError("Could not find login button")

    def _has_login_error(self) -> bool:
        """Check if there's a login error displayed."""
        return self.is_visible(
            self.selectors.login.error_message,
            timeout=self.timeouts.short,
        )

    def _get_error_message(self) -> str:
        """Get the login error message if present."""
        try:
            return self.get_text(
                self.selectors.login.error_message,
                timeout=self.timeouts.short,
            )
        except ElementNotFoundError:
            return "Unknown login error"

    def wait_for_login_complete(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for login to complete by checking URL change.

        Args:
            timeout: Timeout in milliseconds.

        Returns:
            True if login completed (no longer on login page).
        """
        if timeout is None:
            timeout = self.timeouts.long

        # Wait for URL to not contain "login"
        start_url = self.url

        try:
            # Wait for URL to change
            self.page.wait_for_function(
                f"() => window.location.href !== '{start_url}'",
                timeout=timeout,
            )

            # Check we're not on an error page
            if "error" in self.url.lower():
                return False

            return True
        except Exception:
            return False

    def logout(self) -> bool:
        """
        Attempt to logout if logged in.

        Returns:
            True if logout was successful or not logged in.
        """
        # This is a placeholder - implement based on BILL.com logout flow
        logger.info("Logout not implemented - navigate to login page directly")
        return True
