"""Import modal page object."""

from pathlib import Path

from playwright.sync_api import Page

from .base import BasePage
from ..config.selectors import Selectors


class ImportModal(BasePage):
    """Page object for BILL.com import modal."""

    def __init__(self, page: Page, debug: bool = True):
        """Initialize import modal."""
        super().__init__(page, debug)

    def upload_csv_file(self, csv_file_path: str) -> bool:
        """Upload a CSV file using file input.

        Args:
            csv_file_path: Path to CSV file

        Returns:
            True if upload successful

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file
        """
        self.log('INFO', f'Preparing to upload CSV file: {csv_file_path}')

        csv_path = Path(csv_file_path)
        if not csv_path.exists():
            raise FileNotFoundError(f'CSV file not found: {csv_file_path}')

        if not csv_path.is_file():
            raise ValueError(f'Path is not a file: {csv_file_path}')

        self.log('INFO', f'CSV file found: {csv_path.absolute()}')
        self.wait(2000)

        # Strategy 1: Find file input by ID
        if self._upload_via_input_id(csv_path):
            return True

        # Strategy 2: Find via label
        if self._upload_via_label(csv_path):
            return True

        # Strategy 3: Find any file input
        if self._upload_via_generic_input(csv_path):
            return True

        return False

    def _upload_via_input_id(self, csv_path: Path) -> bool:
        """Try to upload via input ID."""
        try:
            file_input = self.find_element(
                Selectors.FileUpload.FILE_INPUT_ID,
                timeout=10000
            )
            if file_input:
                self.log('INFO', 'File input found by ID')
                file_input.set_input_files(str(csv_path.absolute()))
                self.log('INFO', 'CSV file uploaded successfully')
                self.wait(2000)
                return True
        except Exception as error:
            self.log('DEBUG', f'Method 1 failed: {error}')
        return False

    def _upload_via_label(self, csv_path: Path) -> bool:
        """Try to upload via label click."""
        try:
            label = self.find_element(
                Selectors.FileUpload.FILE_INPUT_LABEL,
                timeout=10000
            )
            if label:
                self.log('INFO', 'Label found, clicking to trigger file input...')
                label.click()
                self.wait(1000)

                file_input = self.page.query_selector(Selectors.FileUpload.FILE_INPUT_GENERIC)
                if file_input:
                    file_input.set_input_files(str(csv_path.absolute()))
                    self.log('INFO', 'CSV file uploaded successfully via label click')
                    self.wait(2000)
                    return True
        except Exception as error:
            self.log('DEBUG', f'Method 2 failed: {error}')
        return False

    def _upload_via_generic_input(self, csv_path: Path) -> bool:
        """Try to upload via generic file input."""
        try:
            file_inputs = self.find_elements(Selectors.FileUpload.FILE_INPUT_GENERIC)
            if file_inputs:
                file_inputs[0].set_input_files(str(csv_path.absolute()))
                self.log('INFO', 'CSV file uploaded successfully via generic file input')
                self.wait(2000)
                return True
        except Exception as error:
            self.log('DEBUG', f'Method 3 failed: {error}')
        return False

    def click_import_submit(self) -> bool:
        """Click on the 'Import people' submit button.

        Returns:
            True if button clicked successfully

        Raises:
            ValueError: If button not found
        """
        self.log('INFO', 'Looking for "Import people" submit button...')

        try:
            self.wait(2000)

            # Strategy 1: Find by data-testid
            if self._click_submit_by_testid():
                return True

            # Strategy 2: Find by text
            if self._click_submit_by_text():
                return True

            # Strategy 3: Find via span
            if self._click_submit_by_span():
                return True

            # Strategy 4: Find by pattern
            if self._click_submit_by_pattern():
                return True

            raise ValueError('Could not find "Import people" submit button')

        except Exception as error:
            self.log('ERROR', f'Error clicking Import people submit button: {error}')
            raise

    def _click_submit_by_testid(self) -> bool:
        """Try to click submit button by data-testid."""
        try:
            import_button = self.find_element(
                Selectors.Import.SUBMIT_BUTTON_TESTID,
                timeout=10000
            )
            if import_button:
                self.log('INFO', 'Import people button found by data-testid')
                import_button.click()
                self.wait(2000)
                self.log('INFO', 'Clicked Import people button successfully')
                return True
        except Exception as error:
            self.log('DEBUG', f'Method 1 failed: {error}')
        return False

    def _click_submit_by_text(self) -> bool:
        """Try to click submit button by text."""
        try:
            buttons = self.find_elements('button')
            for button in buttons:
                text = button.inner_text().strip()
                if text.lower() == 'import people' or text.lower() == 'import':
                    if button.is_visible():
                        self.log('INFO', f'Import people button found by text: "{text}"')
                        button.click()
                        self.wait(2000)
                        self.log('INFO', 'Clicked Import people button successfully')
                        return True
        except Exception as error:
            self.log('DEBUG', f'Method 2 failed: {error}')
        return False

    def _click_submit_by_span(self) -> bool:
        """Try to click submit button via span."""
        try:
            spans = self.find_elements('span')
            for span in spans:
                text = span.inner_text().strip()
                if text.lower() == 'import people':
                    try:
                        button = self.page.query_selector('button:has(span:has-text("Import people"))')
                        if button and button.is_visible():
                            self.log('INFO', 'Import people button found via span text')
                            button.click()
                            self.wait(2000)
                            self.log('INFO', 'Clicked Import people button successfully')
                            return True
                    except Exception:
                        pass
        except Exception as error:
            self.log('DEBUG', f'Method 3 failed: {error}')
        return False

    def _click_submit_by_pattern(self) -> bool:
        """Try to click submit button by pattern."""
        try:
            import_buttons = self.find_elements(Selectors.Import.SUBMIT_BUTTON_PATTERN)
            for btn in import_buttons:
                if btn.is_visible():
                    self.log('INFO', 'Import people button found by data-testid pattern')
                    btn.click()
                    self.wait(2000)
                    self.log('INFO', 'Clicked Import people button successfully')
                    return True
        except Exception as error:
            self.log('DEBUG', f'Method 4 failed: {error}')
        return False
