"""Popup handler page object."""

from playwright.sync_api import Page

from .base import BasePage
from ..config.selectors import Selectors


class PopupHandler(BasePage):
    """Page object for handling popups and modals."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize popup handler."""
        super().__init__(page, debug)

    def close_popup(self, max_attempts: int = 3) -> bool:
        """Close any popup that might appear.

        Args:
            max_attempts: Maximum number of close attempts

        Returns:
            True if popup was closed, False if no popup found
        """
        self.log('INFO', 'Checking for popups to close...')

        try:
            self.wait(2000)

            for attempt in range(max_attempts):
                self.log('INFO', f'Attempt {attempt + 1} to close popup...')

                # Try each strategy
                if self._try_close_via_svg_testid():
                    return True

                if self._try_close_via_modal_class():
                    return True

                if self._try_close_via_svg_class():
                    return True

                if self._try_close_via_common_selectors():
                    return True

                # Try ESC key
                self._try_escape_key()

                if attempt < max_attempts - 1:
                    self.wait(1000)

            self.log('INFO', 'No popup found or already closed after all attempts')
            return False

        except Exception as error:
            self.log('WARN', f'Error checking for popup: {error}')
            return False

    def _try_close_via_svg_testid(self) -> bool:
        """Try to close via SVG data-testid."""
        try:
            close_svg = self.page.query_selector(Selectors.Popup.CLOSE_SVG)
            if close_svg:
                button = self.page.query_selector(Selectors.Popup.CLOSE_BUTTON_VIA_SVG)
                if button and button.is_visible():
                    self.log('INFO', 'Found close button via SVG data-testid')
                    button.click()
                    self.wait(1000)
                    self.log('INFO', 'Popup closed successfully')
                    return True

                try:
                    close_svg.evaluate('el => el.closest("button")?.click()')
                    self.wait(1000)
                    self.log('INFO', 'Clicked parent button via evaluate')
                    return True
                except Exception:
                    pass
        except Exception as error:
            self.log('DEBUG', f'SVG method failed: {error}')
        return False

    def _try_close_via_modal_class(self) -> bool:
        """Try to close via Modal-close class."""
        try:
            close_buttons = self.find_elements(Selectors.Popup.MODAL_CLOSE)
            for btn in close_buttons:
                if btn.is_visible():
                    self.log('INFO', 'Found close button via class selector')
                    btn.click()
                    self.wait(1000)
                    self.log('INFO', 'Popup closed successfully')
                    return True
        except Exception as error:
            self.log('DEBUG', f'Class selector method failed: {error}')
        return False

    def _try_close_via_svg_class(self) -> bool:
        """Try to close via SVG with Close class."""
        try:
            close_svgs = self.find_elements(Selectors.Popup.SVG_CLOSE_CLASS)
            for svg in close_svgs:
                if svg.is_visible():
                    try:
                        svg.evaluate('el => el.closest("button")?.click()')
                        self.wait(1000)
                        self.log('INFO', 'Found and clicked close button via SVG class')
                        return True
                    except Exception:
                        try:
                            svg.click()
                            self.wait(1000)
                            self.log('INFO', 'Clicked SVG directly')
                            return True
                        except Exception:
                            pass
        except Exception as error:
            self.log('DEBUG', f'SVG class method failed: {error}')
        return False

    def _try_close_via_common_selectors(self) -> bool:
        """Try common popup close selectors."""
        for selector in Selectors.Popup.COMMON_CLOSE:
            try:
                close_button = self.page.query_selector(selector)
                if close_button and close_button.is_visible():
                    self.log('INFO', f'Popup close button found with selector: {selector}')
                    close_button.click()
                    self.wait(1000)
                    self.log('INFO', 'Popup closed successfully')
                    return True
            except Exception:
                continue
        return False

    def _try_escape_key(self) -> None:
        """Try ESC key to close popup."""
        try:
            self.page.keyboard.press('Escape')
            self.wait(1000)
            self.log('INFO', 'Tried ESC key to close popup')
        except Exception:
            pass
