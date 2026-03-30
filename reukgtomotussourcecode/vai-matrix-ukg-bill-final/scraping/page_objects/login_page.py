"""Login page object."""

from playwright.sync_api import Page

from .base import BasePage
from ..config.selectors import Selectors


class LoginPage(BasePage):
    """Page object for BILL.com login page."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize login page."""
        super().__init__(page, debug)

    def is_login_form_present(self, timeout: int = 3000) -> bool:
        """Check if login form is present."""
        try:
            self.page.wait_for_selector(Selectors.Login.EMAIL_INPUT, timeout=timeout)
            return True
        except Exception:
            return False

    def login(self, email: str, password: str) -> bool:
        """Perform login with credentials.

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login successful, False if no login form found

        Raises:
            ValueError: If credentials are invalid or login button not found
        """
        self.log('INFO', 'Checking for login form...')

        if not self.is_login_form_present():
            self.log('INFO', 'No login form detected, continuing...')
            return False

        self.log('INFO', 'Login form detected')

        # Validate credentials
        if not email or not password:
            raise ValueError(
                'Credentials not found. Configure BILL_LOGIN_EMAIL and '
                'BILL_LOGIN_PASSWORD in the .env file'
            )

        self.log('DEBUG', f'Email to use: {email[:3]}*** (hidden for security)')

        # Fill email
        self.log('INFO', 'Filling email field...')
        if not self.type_text(Selectors.Login.EMAIL_INPUT, email):
            raise ValueError('Could not find email input field')
        self.log('INFO', 'Email entered successfully')

        # Fill password
        self.log('INFO', 'Filling password field...')
        if not self.type_text(Selectors.Login.PASSWORD_INPUT, password):
            raise ValueError('Could not find password input field')
        self.log('INFO', 'Password entered successfully')

        self.wait(500)

        # Find and click login button
        self.log('INFO', 'Looking for login button...')
        login_button = self._find_login_button()

        if not login_button:
            raise ValueError('Could not find login button')

        self.log('INFO', 'Clicking login button...')
        login_button.click()

        # Wait for navigation
        self.log('INFO', 'Waiting for login to complete...')
        try:
            self.page.wait_for_load_state('networkidle', timeout=3000)
        except Exception:
            self.log('INFO', 'Waiting for content after login...')

        self.wait(2000)
        self.log('INFO', 'Login completed successfully')
        return True

    def _find_login_button(self):
        """Find the login button using multiple strategies."""
        # Strategy 1: Try specific selectors
        for selector in Selectors.Login.SUBMIT_BUTTON:
            try:
                button = self.page.query_selector(selector)
                if button:
                    self.log('INFO', f'Login button found with selector: {selector}')
                    return button
            except Exception:
                continue

        # Strategy 2: Search by text
        button = self.find_button_by_text(['log in', 'login', 'sign in'])
        if button:
            self.log('INFO', 'Login button found by text')
            return button

        return None
