"""
Import page object for BILL.com People CSV import.

Handles:
- Clicking "Import People" button
- CSV file upload
- Import confirmation
- Error/success detection
"""

import logging
from pathlib import Path
from typing import Optional, List, Any, TYPE_CHECKING
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


class ImportError(PageObjectError):
    """Raised when import operation fails."""

    pass


class FileUploadError(ImportError):
    """Raised when file upload fails."""

    pass


class ImportValidationError(ImportError):
    """Raised when import validation fails."""

    pass


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    imported_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class ImportPage(BasePage):
    """
    Page object for BILL.com People import functionality.

    Handles the workflow:
    1. Click "Import People" button on People page
    2. Upload CSV file
    3. Preview and confirm import
    4. Handle results (success/errors)
    """

    def __init__(
        self,
        page: Page,
        selectors: Optional[SelectorConfig] = None,
    ):
        """
        Initialize import page.

        Args:
            page: Playwright page instance.
            selectors: Optional selector configuration.
        """
        super().__init__(page, selectors)

    def click_import_people_button(self) -> bool:
        """
        Click the "Import People" button on the People page.

        Returns:
            True if button was clicked successfully.

        Raises:
            ImportError: If button cannot be found or clicked.
        """
        logger.info("Looking for 'Import People' button...")

        self.wait(2000)

        try:
            # Try configured selectors first
            self.click(
                self.selectors.people.import_button,
                timeout=self.timeouts.medium,
            )
            self.wait(2000)
            logger.info("Clicked 'Import People' button successfully")
            return True

        except ElementNotFoundError:
            logger.debug("Primary selectors failed, trying text search")

        # Fallback: search by button text
        try:
            buttons = self.page.locator("button").all()
            for button in buttons:
                try:
                    text = button.inner_text().strip().lower()
                    if "import" in text:
                        if button.is_visible():
                            logger.debug(f"Found import button by text: '{text}'")
                            button.click()
                            self.wait(2000)
                            logger.info("Clicked 'Import People' button via text search")
                            return True
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Text search failed: {e}")

        # Try finding span with text inside button
        try:
            locator = self.page.get_by_text("Import People", exact=False)
            if locator.count() > 0:
                locator.first.click()
                self.wait(2000)
                logger.info("Clicked 'Import People' via text locator")
                return True
        except Exception:
            pass

        self._capture_error_screenshot("import_button_not_found")
        raise ImportError("Could not find 'Import People' button")

    def upload_csv_file(self, file_path: Path) -> bool:
        """
        Upload a CSV file for import.

        Args:
            file_path: Path to the CSV file.

        Returns:
            True if file was uploaded successfully.

        Raises:
            FileUploadError: If file upload fails.
        """
        logger.info(f"Uploading CSV file: {file_path}")

        # Validate file
        if not file_path.exists():
            raise FileUploadError(f"CSV file not found: {file_path}")

        if not file_path.is_file():
            raise FileUploadError(f"Path is not a file: {file_path}")

        absolute_path = str(file_path.absolute())
        logger.debug(f"Absolute path: {absolute_path}")

        self.wait(2000)

        try:
            # Strategy 1: Find file input by ID
            if self._upload_via_input(absolute_path):
                return True

            # Strategy 2: Click label then find input
            if self._upload_via_label(absolute_path):
                return True

            # Strategy 3: Find any file input
            if self._upload_via_any_input(absolute_path):
                return True

            raise FileUploadError("Could not find file input element")

        except FileUploadError:
            raise
        except Exception as e:
            self._capture_error_screenshot("file_upload_failed")
            raise FileUploadError(f"File upload failed: {e}") from e

    def _upload_via_input(self, file_path: str) -> bool:
        """Try to upload via file input selector."""
        for selector in self.selectors.import_page.file_input:
            try:
                locator = self.page.locator(selector)
                if locator.count() > 0:
                    locator.set_input_files(file_path)
                    self.wait(2000)
                    logger.info("File uploaded via input selector")
                    return True
            except Exception as e:
                logger.debug(f"Input selector failed: {selector} - {e}")
                continue

        return False

    def _upload_via_label(self, file_path: str) -> bool:
        """Try to upload by clicking label first."""
        for selector in self.selectors.import_page.file_input_label:
            try:
                label = self.page.locator(selector)
                if label.count() > 0 and label.first.is_visible():
                    label.first.click()
                    self.wait(500)

                    # Now find any file input
                    input_locator = self.page.locator("input[type='file']")
                    if input_locator.count() > 0:
                        input_locator.set_input_files(file_path)
                        self.wait(2000)
                        logger.info("File uploaded via label click")
                        return True
            except Exception as e:
                logger.debug(f"Label method failed: {e}")
                continue

        return False

    def _upload_via_any_input(self, file_path: str) -> bool:
        """Try to upload via any file input on page."""
        try:
            inputs = self.page.locator("input[type='file']").all()
            if inputs:
                inputs[0].set_input_files(file_path)
                self.wait(2000)
                logger.info("File uploaded via generic file input")
                return True
        except Exception as e:
            logger.debug(f"Generic input method failed: {e}")

        return False

    def click_import_submit_button(self) -> bool:
        """
        Click the submit button to confirm the import.

        Returns:
            True if button was clicked successfully.

        Raises:
            ImportError: If button cannot be found or clicked.
        """
        logger.info("Looking for import submit button...")

        self.wait(2000)

        try:
            # Try configured selectors
            self.click(
                self.selectors.import_page.submit_button,
                timeout=self.timeouts.medium,
            )
            self.wait(2000)
            logger.info("Clicked import submit button successfully")
            return True

        except ElementNotFoundError:
            logger.debug("Primary selectors failed, trying text search")

        # Fallback: search by button text
        try:
            buttons = self.page.locator("button").all()
            for button in buttons:
                try:
                    text = button.inner_text().strip().lower()
                    if text == "import people" or text == "import":
                        if button.is_visible():
                            button.click()
                            self.wait(2000)
                            logger.info("Clicked import submit via text search")
                            return True
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Text search failed: {e}")

        self._capture_error_screenshot("import_submit_not_found")
        raise ImportError("Could not find import submit button")

    def wait_for_import_complete(self, timeout: Optional[int] = None) -> ImportResult:
        """
        Wait for import to complete and return results.

        Args:
            timeout: Timeout in milliseconds.

        Returns:
            ImportResult with success status and counts.
        """
        if timeout is None:
            timeout = self.timeouts.long

        logger.info("Waiting for import to complete...")
        self.wait(5000)

        # Check for success message
        success = self._has_success_message()

        # Count errors and warnings
        errors = self._get_error_messages()
        warnings = self._get_warning_messages()

        result = ImportResult(
            success=success and len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
        )

        if result.success:
            logger.info("Import completed successfully")
        else:
            logger.warning(f"Import completed with {len(errors)} errors")

        return result

    def _has_success_message(self) -> bool:
        """Check if success message is displayed."""
        return self.is_visible(
            self.selectors.import_page.success_message,
            timeout=self.timeouts.short,
        )

    def _get_error_messages(self) -> List[str]:
        """Get all error messages from the import preview/result."""
        errors = []

        for selector in self.selectors.import_page.error_row:
            try:
                locator = self.page.locator(selector)
                for i in range(locator.count()):
                    try:
                        text = locator.nth(i).inner_text().strip()
                        if text:
                            errors.append(text)
                    except Exception:
                        continue
            except Exception:
                continue

        return errors

    def _get_warning_messages(self) -> List[str]:
        """Get all warning messages from the import preview/result."""
        warnings = []

        for selector in self.selectors.import_page.warning_row:
            try:
                locator = self.page.locator(selector)
                for i in range(locator.count()):
                    try:
                        text = locator.nth(i).inner_text().strip()
                        if text:
                            warnings.append(text)
                    except Exception:
                        continue
            except Exception:
                continue

        return warnings

    def import_csv(self, file_path: Path) -> ImportResult:
        """
        Perform complete CSV import workflow.

        This is the main method that orchestrates:
        1. Click Import People button
        2. Upload CSV file
        3. Click submit button
        4. Wait for completion

        Args:
            file_path: Path to the CSV file.

        Returns:
            ImportResult with operation results.

        Raises:
            ImportError: If any step fails.
        """
        logger.info(f"Starting CSV import: {file_path}")

        try:
            # Step 1: Click Import People button
            self.click_import_people_button()

            # Step 2: Upload CSV file
            self.upload_csv_file(file_path)

            # Wait for preview to load
            self.wait(3000)
            logger.debug("File preview loaded")

            # Step 3: Click submit button
            self.click_import_submit_button()

            # Step 4: Wait for completion
            result = self.wait_for_import_complete()

            return result

        except ImportError:
            raise
        except Exception as e:
            self._capture_error_screenshot("import_workflow_failed")
            raise ImportError(f"Import workflow failed: {e}") from e

    def get_preview_row_count(self) -> int:
        """
        Get the number of rows in the import preview.

        Returns:
            Number of preview rows.
        """
        count = 0

        for selector in self.selectors.import_page.preview_table:
            try:
                locator = self.page.locator(f"{selector} tr")
                count = locator.count()
                if count > 0:
                    # Subtract header row
                    return max(0, count - 1)
            except Exception:
                continue

        return count

    def has_validation_errors(self) -> bool:
        """
        Check if the preview has validation errors.

        Returns:
            True if errors are present.
        """
        return len(self._get_error_messages()) > 0

    def cancel_import(self) -> bool:
        """
        Cancel the current import operation.

        Returns:
            True if cancelled successfully.
        """
        try:
            # Press ESC to close modal
            self.page.keyboard.press("Escape")
            self.wait(1000)
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel import: {e}")
            return False
