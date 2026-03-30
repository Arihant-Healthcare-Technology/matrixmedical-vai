"""
Unit tests for page objects.

These tests use mocked Playwright objects to test page object logic
without requiring a real browser.
"""

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import tempfile

import pytest

# Check if playwright is available
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Create a mock TimeoutError for tests
    class PlaywrightTimeout(Exception):
        pass

from src.infrastructure.config.selectors import SelectorConfig, get_selectors
from src.infrastructure.adapters.scraping.page_objects.base_page import (
    BasePage,
    ElementNotFoundError,
    ActionError,
)
from src.infrastructure.adapters.scraping.page_objects.login_page import (
    LoginPage,
    LoginCredentials,
    LoginError,
    CredentialsMissingError,
)
from src.infrastructure.adapters.scraping.page_objects.company_page import (
    CompanyPage,
    CompanyNotFoundError,
    CompanySelectionError,
)
from src.infrastructure.adapters.scraping.page_objects.import_page import (
    ImportPage,
    ImportResult,
    ImportError,
    FileUploadError,
)


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = MagicMock()
    page.url = "https://app.bill.com/test"
    page.locator.return_value = MagicMock()
    return page


@pytest.fixture
def mock_locator():
    """Create a mock Playwright locator."""
    locator = MagicMock()
    locator.count.return_value = 1
    locator.is_visible.return_value = True
    locator.inner_text.return_value = "Test text"
    return locator


@pytest.fixture
def temp_screenshot_dir():
    """Create temporary screenshot directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestBasePage:
    """Tests for BasePage class."""

    def test_initialization(self, mock_page, temp_screenshot_dir):
        """Should initialize with page and selectors."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        assert page_obj.page == mock_page
        assert page_obj.selectors is not None

    def test_url_property(self, mock_page, temp_screenshot_dir):
        """Should return current page URL."""
        mock_page.url = "https://example.com/test"
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        assert page_obj.url == "https://example.com/test"

    def test_wait_calls_page_timeout(self, mock_page, temp_screenshot_dir):
        """Wait should call page.wait_for_timeout."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        page_obj.wait(1000)
        mock_page.wait_for_timeout.assert_called_with(1000)

    def test_find_element_success(self, mock_page, mock_locator, temp_screenshot_dir):
        """Should find element with first matching selector."""
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.find_element(["selector1", "selector2"])

        mock_page.locator.assert_called()
        assert result == mock_locator

    def test_find_element_fallback(self, mock_page, temp_screenshot_dir):
        """Should try next selector when first fails."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")

        success_locator = MagicMock()
        success_locator.wait_for.return_value = None

        mock_page.locator.side_effect = [failed_locator, success_locator]
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.find_element(["bad_selector", "good_selector"])

        assert mock_page.locator.call_count == 2
        assert result == success_locator

    def test_find_element_optional_returns_none(self, mock_page, temp_screenshot_dir):
        """find_element_optional should return None if not found."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.find_element_optional(["bad_selector"])
        assert result is None

    def test_click_calls_element_click(self, mock_page, mock_locator, temp_screenshot_dir):
        """Click should find element and click it."""
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        page_obj.click(["button"])

        mock_locator.scroll_into_view_if_needed.assert_called_once()
        mock_locator.click.assert_called_once()

    def test_type_text_clears_and_types(self, mock_page, mock_locator, temp_screenshot_dir):
        """type_text should clear field and type text."""
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        page_obj.type_text(["input"], "test text", clear_first=True)

        mock_locator.click.assert_called()
        mock_locator.press.assert_called_with("Control+a")
        mock_locator.type.assert_called()

    def test_get_text_returns_inner_text(self, mock_page, mock_locator, temp_screenshot_dir):
        """get_text should return element's inner text."""
        mock_locator.inner_text.return_value = "  Test Content  "
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.get_text(["element"])
        assert result == "Test Content"

    def test_is_visible_returns_true(self, mock_page, mock_locator, temp_screenshot_dir):
        """is_visible should return True when element is visible."""
        mock_locator.is_visible.return_value = True
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.is_visible(["element"])
        assert result is True

    def test_screenshot_saves_file(self, mock_page, temp_screenshot_dir):
        """screenshot should save to file."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.screenshot("test")

        mock_page.screenshot.assert_called_once()
        assert "test" in str(result)

    def test_retry_succeeds_first_try(self, mock_page, temp_screenshot_dir):
        """retry should return result on first successful try."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        action = Mock(return_value="success")
        result = page_obj.retry(action, max_attempts=3)

        assert result == "success"
        assert action.call_count == 1

    def test_retry_succeeds_after_failures(self, mock_page, temp_screenshot_dir):
        """retry should succeed after initial failures."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        action = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        result = page_obj.retry(action, max_attempts=3, delay=10)

        assert result == "success"
        assert action.call_count == 3

    def test_retry_raises_after_max_attempts(self, mock_page, temp_screenshot_dir):
        """retry should raise after max attempts exhausted."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        action = Mock(side_effect=Exception("always fails"))

        with pytest.raises(Exception, match="always fails"):
            page_obj.retry(action, max_attempts=2, delay=10)

        assert action.call_count == 2


class TestLoginCredentials:
    """Tests for LoginCredentials dataclass."""

    def test_validate_success(self):
        """Should not raise for valid credentials."""
        creds = LoginCredentials(email="test@example.com", password="secret")
        creds.validate()  # Should not raise

    def test_validate_missing_email(self):
        """Should raise for missing email."""
        creds = LoginCredentials(email="", password="secret")
        with pytest.raises(CredentialsMissingError, match="Email"):
            creds.validate()

    def test_validate_missing_password(self):
        """Should raise for missing password."""
        creds = LoginCredentials(email="test@example.com", password="")
        with pytest.raises(CredentialsMissingError, match="Password"):
            creds.validate()


class TestLoginPage:
    """Tests for LoginPage class."""

    def test_is_login_required_true(self, mock_page, mock_locator, temp_screenshot_dir):
        """Should return True when login form is present."""
        mock_page.locator.return_value = mock_locator
        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.is_login_required()
        assert result is True

    def test_is_login_required_false(self, mock_page, temp_screenshot_dir):
        """Should return False when login form is not present."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.is_login_required()
        assert result is False

    def test_login_validates_credentials(self, mock_page, temp_screenshot_dir):
        """Login should validate credentials first."""
        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        creds = LoginCredentials(email="", password="secret")

        with pytest.raises(CredentialsMissingError):
            login_page.login(creds)


class TestCompanyPage:
    """Tests for CompanyPage class."""

    def test_current_company_id_from_url(self, mock_page, temp_screenshot_dir):
        """Should extract company ID from URL."""
        mock_page.url = "https://app.bill.com/companies/ABC123/dashboard"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        assert company_page.current_company_id == "ABC123"

    def test_current_company_id_none_when_not_on_company(
        self, mock_page, temp_screenshot_dir
    ):
        """Should return None when not on company page."""
        mock_page.url = "https://app.bill.com/login"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        assert company_page.current_company_id is None

    def test_get_available_companies(self, mock_page, temp_screenshot_dir):
        """Should return list of company names."""
        cell1 = MagicMock()
        cell1.inner_text.return_value = "Company A"

        cell2 = MagicMock()
        cell2.inner_text.return_value = "Company B"

        mock_locator = MagicMock()
        mock_locator.all.return_value = [cell1, cell2]
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        companies = company_page.get_available_companies()

        assert "Company A" in companies
        assert "Company B" in companies


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_success_result(self):
        """Should create successful result."""
        result = ImportResult(
            success=True,
            imported_count=10,
            error_count=0,
        )
        assert result.success is True
        assert result.imported_count == 10
        assert result.errors == []

    def test_failure_result(self):
        """Should create failure result with errors."""
        result = ImportResult(
            success=False,
            error_count=2,
            errors=["Error 1", "Error 2"],
        )
        assert result.success is False
        assert len(result.errors) == 2

    def test_default_lists(self):
        """Should initialize empty lists by default."""
        result = ImportResult(success=True)
        assert result.errors == []
        assert result.warnings == []


class TestImportPage:
    """Tests for ImportPage class."""

    def test_upload_csv_file_not_found(self, mock_page, temp_screenshot_dir):
        """Should raise FileUploadError for missing file."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with pytest.raises(FileUploadError, match="not found"):
            import_page.upload_csv_file(Path("/nonexistent/file.csv"))

    def test_upload_csv_file_not_file(self, mock_page, temp_screenshot_dir):
        """Should raise FileUploadError for directory."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileUploadError, match="not a file"):
                import_page.upload_csv_file(Path(tmpdir))

    def test_get_preview_row_count(self, mock_page, temp_screenshot_dir):
        """Should count rows in preview table."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 5  # 4 data rows + 1 header
        mock_page.locator.return_value = mock_locator

        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        count = import_page.get_preview_row_count()
        assert count == 4  # Should subtract header row

    def test_cancel_import_presses_escape(self, mock_page, temp_screenshot_dir):
        """cancel_import should press ESC key."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        result = import_page.cancel_import()

        mock_page.keyboard.press.assert_called_with("Escape")
        assert result is True


class TestPageObjectIntegration:
    """Integration tests for page object workflow."""

    def test_page_objects_use_same_selectors(self, mock_page, temp_screenshot_dir):
        """All page objects should use the same selector config."""
        selectors = get_selectors()

        login_page = LoginPage(mock_page, selectors)
        company_page = CompanyPage(mock_page, selectors)
        import_page = ImportPage(mock_page, selectors)

        assert login_page.selectors is selectors
        assert company_page.selectors is selectors
        assert import_page.selectors is selectors

    def test_page_objects_share_base_methods(self, mock_page, temp_screenshot_dir):
        """All page objects should have base methods."""
        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        # Base methods should be available
        assert hasattr(login_page, "find_element")
        assert hasattr(login_page, "click")
        assert hasattr(login_page, "type_text")
        assert hasattr(login_page, "wait")
        assert hasattr(login_page, "close_popup")
        assert hasattr(login_page, "screenshot")


class TestBasePageAdditional:
    """Additional tests for BasePage class."""

    def test_query_element_returns_locator(self, mock_page, mock_locator, temp_screenshot_dir):
        """query_element should return locator when element exists."""
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        result = page_obj.query_element("selector")

        assert result == mock_locator

    def test_query_element_returns_none(self, mock_page, temp_screenshot_dir):
        """query_element should return None when element doesn't exist."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        result = page_obj.query_element("selector")

        assert result is None

    def test_is_visible_returns_false_not_found(self, mock_page, temp_screenshot_dir):
        """is_visible should return False when element not found."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        result = page_obj.is_visible(["missing"])

        assert result is False

    def test_goto_navigates_to_url(self, mock_page, temp_screenshot_dir):
        """goto should navigate to the specified URL."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        page_obj.goto("https://example.com")

        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args
        assert call_args[0][0] == "https://example.com"

    def test_wait_for_url_contains_success(self, mock_page, temp_screenshot_dir):
        """wait_for_url_contains should return True when URL matches."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        result = page_obj.wait_for_url_contains("dashboard")

        assert result is True
        mock_page.wait_for_url.assert_called_once()

    def test_wait_for_url_contains_timeout(self, mock_page, temp_screenshot_dir):
        """wait_for_url_contains should return False on timeout."""
        mock_page.wait_for_url.side_effect = PlaywrightTimeout("timeout")

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)
        result = page_obj.wait_for_url_contains("never-found")

        assert result is False

    def test_type_text_without_clear(self, mock_page, mock_locator, temp_screenshot_dir):
        """type_text should skip clear when clear_first is False."""
        mock_page.locator.return_value = mock_locator
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        page_obj.type_text(["input"], "text", clear_first=False)

        mock_locator.press.assert_not_called()
        mock_locator.type.assert_called()

    def test_click_raises_action_error_on_failure(self, mock_page, temp_screenshot_dir):
        """click should raise ActionError on failure."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        with pytest.raises(ActionError):
            page_obj.click(["bad_selector"])

    def test_type_text_raises_action_error_on_failure(self, mock_page, temp_screenshot_dir):
        """type_text should raise ActionError on failure."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        with pytest.raises(ActionError):
            page_obj.type_text(["bad_selector"], "text")

    def test_retry_with_on_failure_callback(self, mock_page, temp_screenshot_dir):
        """retry should call on_failure callback on each failure."""
        page_obj = BasePage(mock_page, screenshot_dir=temp_screenshot_dir)

        callback = Mock()
        action = Mock(side_effect=[Exception("fail"), "success"])

        result = page_obj.retry(action, max_attempts=2, delay=10, on_failure=callback)

        assert result == "success"
        callback.assert_called_once()


class TestLoginPageAdditional:
    """Additional tests for LoginPage class."""

    def test_login_success_flow(self, mock_page, mock_locator, temp_screenshot_dir):
        """login should complete successfully when credentials are valid."""
        mock_page.locator.return_value = mock_locator
        mock_locator.all.return_value = []

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        # Mock is_visible to return False (no error)
        with patch.object(login_page, "_has_login_error", return_value=False):
            creds = LoginCredentials(email="test@example.com", password="secret")
            result = login_page.login(creds)

        assert result is True

    def test_login_fails_with_error_message(self, mock_page, mock_locator, temp_screenshot_dir):
        """login should raise LoginError when error message is shown."""
        mock_page.locator.return_value = mock_locator
        mock_locator.all.return_value = []
        mock_locator.inner_text.return_value = "Invalid credentials"

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        with patch.object(login_page, "_has_login_error", return_value=True):
            with patch.object(login_page, "_get_error_message", return_value="Invalid credentials"):
                creds = LoginCredentials(email="test@example.com", password="wrong")

                with pytest.raises(LoginError, match="Invalid credentials"):
                    login_page.login(creds)

    def test_wait_for_login_complete_success(self, mock_page, temp_screenshot_dir):
        """wait_for_login_complete should return True when URL changes."""
        mock_page.url = "https://app.bill.com/dashboard"

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.wait_for_login_complete()

        mock_page.wait_for_function.assert_called_once()
        assert result is True

    def test_wait_for_login_complete_error_page(self, mock_page, temp_screenshot_dir):
        """wait_for_login_complete should return False on error page."""
        mock_page.url = "https://app.bill.com/error"

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.wait_for_login_complete()

        assert result is False

    def test_wait_for_login_complete_timeout(self, mock_page, temp_screenshot_dir):
        """wait_for_login_complete should return False on timeout."""
        mock_page.wait_for_function.side_effect = Exception("timeout")

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.wait_for_login_complete()

        assert result is False

    def test_logout_returns_true(self, mock_page, temp_screenshot_dir):
        """logout should return True (placeholder implementation)."""
        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page.logout()

        assert result is True

    def test_get_error_message_returns_unknown(self, mock_page, temp_screenshot_dir):
        """_get_error_message should return 'Unknown' when element not found."""
        failed_locator = MagicMock()
        failed_locator.wait_for.side_effect = PlaywrightTimeout("timeout")
        mock_page.locator.return_value = failed_locator

        login_page = LoginPage(mock_page)
        login_page.screenshot_dir = temp_screenshot_dir

        result = login_page._get_error_message()

        assert result == "Unknown login error"


class TestImportPageAdditional:
    """Additional tests for ImportPage class."""

    def test_click_import_people_button_via_get_by_text(self, mock_page, temp_screenshot_dir):
        """click_import_people_button should find button via get_by_text fallback."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        # Mock click method to simulate primary selectors failing
        # then get_by_text succeeding
        with patch.object(import_page, "click") as mock_click:
            mock_click.side_effect = ElementNotFoundError("not found")

            # Mock button text search
            mock_page.locator.return_value.all.return_value = []

            # Mock get_by_text to succeed
            text_loc = MagicMock()
            text_loc.count.return_value = 1
            mock_page.get_by_text.return_value = text_loc

            result = import_page.click_import_people_button()

            assert result is True
            mock_page.get_by_text.assert_called_with("Import People", exact=False)

    def test_upload_csv_file_via_input(self, mock_page, temp_screenshot_dir):
        """upload_csv_file should upload via input selector."""
        import tempfile
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n")
            temp_file = Path(f.name)

        try:
            locator_mock = MagicMock()
            locator_mock.count.return_value = 1
            mock_page.locator.return_value = locator_mock

            result = import_page.upload_csv_file(temp_file)

            locator_mock.set_input_files.assert_called_once()
            assert result is True
        finally:
            temp_file.unlink()

    def test_click_import_submit_button_success(self, mock_page, mock_locator, temp_screenshot_dir):
        """click_import_submit_button should click submit button."""
        mock_page.locator.return_value = mock_locator

        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        result = import_page.click_import_submit_button()

        assert result is True

    def test_wait_for_import_complete_with_errors(self, mock_page, temp_screenshot_dir):
        """wait_for_import_complete should report errors."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "_has_success_message", return_value=True):
            with patch.object(import_page, "_get_error_messages", return_value=["Error 1"]):
                with patch.object(import_page, "_get_warning_messages", return_value=[]):
                    result = import_page.wait_for_import_complete()

                    assert result.success is False
                    assert result.error_count == 1

    def test_has_validation_errors_true(self, mock_page, temp_screenshot_dir):
        """has_validation_errors should return True when errors exist."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "_get_error_messages", return_value=["Error"]):
            result = import_page.has_validation_errors()

        assert result is True

    def test_has_validation_errors_false(self, mock_page, temp_screenshot_dir):
        """has_validation_errors should return False when no errors."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "_get_error_messages", return_value=[]):
            result = import_page.has_validation_errors()

        assert result is False

    def test_import_csv_full_workflow(self, mock_page, temp_screenshot_dir):
        """import_csv should orchestrate full workflow."""
        import tempfile
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n")
            temp_file = Path(f.name)

        try:
            with patch.object(import_page, "click_import_people_button", return_value=True):
                with patch.object(import_page, "upload_csv_file", return_value=True):
                    with patch.object(import_page, "click_import_submit_button", return_value=True):
                        with patch.object(import_page, "wait_for_import_complete") as mock_wait:
                            mock_wait.return_value = ImportResult(success=True, imported_count=5)

                            result = import_page.import_csv(temp_file)

                            assert result.success is True
                            assert result.imported_count == 5
        finally:
            temp_file.unlink()

    def test_cancel_import_fails_gracefully(self, mock_page, temp_screenshot_dir):
        """cancel_import should return False on failure."""
        mock_page.keyboard.press.side_effect = Exception("keyboard error")

        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        result = import_page.cancel_import()

        assert result is False


class TestCompanyPageAdditional:
    """Additional tests for CompanyPage class."""

    def test_current_company_id_with_subpath(self, mock_page, temp_screenshot_dir):
        """Should extract company ID from URL with subpath."""
        mock_page.url = "https://app.bill.com/companies/XYZ789/settings/users"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        assert company_page.current_company_id == "XYZ789"

    def test_get_available_companies_empty(self, mock_page, temp_screenshot_dir):
        """Should return empty list when no companies found."""
        mock_locator = MagicMock()
        mock_locator.all.return_value = []
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        companies = company_page.get_available_companies()

        assert companies == []

    def test_select_company_via_xpath(self, mock_page, temp_screenshot_dir):
        """Should select company via XPath."""
        mock_locator = MagicMock()
        mock_locator.wait_for.return_value = None
        mock_locator.scroll_into_view_if_needed.return_value = None
        mock_locator.click.return_value = None
        mock_page.locator.return_value = mock_locator
        mock_page.wait_for_load_state.return_value = None

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir
        company_page._current_company_id = "ABC123"

        result = company_page._select_by_xpath("Test Company")

        assert result is True
        mock_locator.click.assert_called_once()

    def test_select_company_via_xpath_fails(self, mock_page, temp_screenshot_dir):
        """Should return False when XPath selection fails."""
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Timeout")
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page._select_by_xpath("Test Company")

        assert result is False

    def test_select_company_from_cells(self, mock_page, temp_screenshot_dir):
        """Should select company from table cells."""
        cell1 = MagicMock()
        cell1.inner_text.return_value = "Test Company"
        cell1.scroll_into_view_if_needed.return_value = None
        cell1.click.return_value = None

        mock_locator = MagicMock()
        mock_locator.all.return_value = [cell1]
        mock_page.locator.return_value = mock_locator
        mock_page.wait_for_load_state.return_value = None

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir
        company_page._current_company_id = "ABC123"

        result = company_page._select_from_cells("Test Company")

        assert result is True
        cell1.click.assert_called_once()

    def test_select_company_from_cells_not_found(self, mock_page, temp_screenshot_dir):
        """Should return False when company not found in cells."""
        cell1 = MagicMock()
        cell1.inner_text.return_value = "Other Company"

        mock_locator = MagicMock()
        mock_locator.all.return_value = [cell1]
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page._select_from_cells("Test Company")

        assert result is False

    def test_select_by_text_search(self, mock_page, temp_screenshot_dir):
        """Should select company by text search."""
        element = MagicMock()
        element.is_visible.return_value = True
        element.scroll_into_view_if_needed.return_value = None
        element.click.return_value = None

        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_locator.nth.return_value = element
        mock_page.get_by_text.return_value = mock_locator
        mock_page.wait_for_load_state.return_value = None

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir
        company_page._current_company_id = "ABC123"

        result = company_page._select_by_text_search("Test Company")

        assert result is True

    def test_select_by_text_search_no_matches(self, mock_page, temp_screenshot_dir):
        """Should return False when no text matches found."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.get_by_text.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page._select_by_text_search("Test Company")

        assert result is False

    def test_select_company_success(self, mock_page, temp_screenshot_dir):
        """Should select company successfully."""
        mock_locator = MagicMock()
        mock_locator.wait_for.return_value = None
        mock_locator.scroll_into_view_if_needed.return_value = None
        mock_locator.click.return_value = None
        mock_page.locator.return_value = mock_locator
        mock_page.wait_for_load_state.return_value = None

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir
        company_page._current_company_id = "ABC123"

        result = company_page.select_company("Test Company")

        assert result is True

    def test_select_company_not_found(self, mock_page, temp_screenshot_dir):
        """Should raise CompanyNotFoundError when company not found."""
        from src.infrastructure.adapters.scraping.page_objects.company_page import CompanyNotFoundError

        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Timeout")
        mock_locator.all.return_value = []
        mock_page.locator.return_value = mock_locator

        mock_text_locator = MagicMock()
        mock_text_locator.count.return_value = 0
        mock_page.get_by_text.return_value = mock_text_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        with pytest.raises(CompanyNotFoundError, match="not found"):
            company_page.select_company("Missing Company")

    def test_is_on_company_list_true(self, mock_page, temp_screenshot_dir):
        """Should return True when company list is visible."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_locator.first.is_visible.return_value = True
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page.is_on_company_list()

        assert result is True

    def test_is_on_company_list_false(self, mock_page, temp_screenshot_dir):
        """Should return False when company list is not visible."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page.is_on_company_list()

        assert result is False

    def test_is_on_company_dashboard_true(self, mock_page, temp_screenshot_dir):
        """Should return True when on company dashboard."""
        mock_page.url = "https://app.bill.com/companies/ABC123/dashboard"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page.is_on_company_dashboard()

        assert result is True

    def test_is_on_company_dashboard_false(self, mock_page, temp_screenshot_dir):
        """Should return False when not on company dashboard."""
        mock_page.url = "https://app.bill.com/login"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page.is_on_company_dashboard()

        assert result is False

    def test_navigate_to_people_success(self, mock_page, temp_screenshot_dir):
        """Should navigate to People page successfully."""
        mock_page.url = "https://app.bill.com/companies/ABC123/dashboard"
        mock_page.goto.return_value = None
        mock_page.wait_for_load_state.return_value = None

        # Mock for close_popup
        mock_popup_locator = MagicMock()
        mock_popup_locator.count.return_value = 0
        mock_page.locator.return_value = mock_popup_locator

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        result = company_page.navigate_to_people()

        assert result is True
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args[0][0]
        assert "/people" in call_args

    def test_navigate_to_people_no_company(self, mock_page, temp_screenshot_dir):
        """Should raise error when no company selected."""
        from src.infrastructure.adapters.scraping.page_objects.company_page import CompanySelectionError

        mock_page.url = "https://app.bill.com/login"

        company_page = CompanyPage(mock_page)
        company_page.screenshot_dir = temp_screenshot_dir

        with pytest.raises(CompanySelectionError, match="No company selected"):
            company_page.navigate_to_people()


class TestImportPageMoreScenarios:
    """Additional tests for ImportPage to improve coverage."""

    def test_click_import_people_button_via_button_text_search(self, mock_page, temp_screenshot_dir):
        """click_import_people_button should find button via button text search."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        # Mock click to fail for primary selectors
        with patch.object(import_page, "click") as mock_click:
            mock_click.side_effect = ElementNotFoundError("not found")

            # Mock button iteration to find import button
            button = MagicMock()
            button.inner_text.return_value = "Import Employees"
            button.is_visible.return_value = True
            mock_page.locator.return_value.all.return_value = [button]

            # Mock get_by_text to fail
            mock_page.get_by_text.return_value.count.return_value = 0

            result = import_page.click_import_people_button()

            assert result is True
            button.click.assert_called_once()

    def test_click_import_people_button_raises_import_error(self, mock_page, temp_screenshot_dir):
        """click_import_people_button should raise ImportError when all methods fail."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "click") as mock_click:
            mock_click.side_effect = ElementNotFoundError("not found")

            # All methods fail
            mock_page.locator.return_value.all.return_value = []
            mock_page.get_by_text.return_value.count.return_value = 0

            with pytest.raises(ImportError, match="Import People"):
                import_page.click_import_people_button()

    def test_upload_via_label(self, mock_page, temp_screenshot_dir):
        """_upload_via_label should upload via label click."""
        import tempfile
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n")
            temp_file = Path(f.name)

        try:
            # Mock input selector to fail
            input_locator = MagicMock()
            input_locator.count.return_value = 0

            # Mock label selector to succeed
            label_locator = MagicMock()
            label_locator.count.return_value = 1
            label_locator.first.is_visible.return_value = True

            file_input_locator = MagicMock()
            file_input_locator.count.return_value = 1

            mock_page.locator.side_effect = [
                input_locator,  # First input selector fails
                label_locator,  # Label selector succeeds
                file_input_locator,  # File input after label click
            ]

            result = import_page._upload_via_label(str(temp_file.absolute()))

            assert result is True
        finally:
            temp_file.unlink()

    def test_upload_via_any_input(self, mock_page, temp_screenshot_dir):
        """_upload_via_any_input should upload via any file input."""
        import tempfile
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n")
            temp_file = Path(f.name)

        try:
            input_element = MagicMock()
            mock_page.locator.return_value.all.return_value = [input_element]

            result = import_page._upload_via_any_input(str(temp_file.absolute()))

            assert result is True
            input_element.set_input_files.assert_called_once()
        finally:
            temp_file.unlink()

    def test_upload_via_any_input_no_inputs(self, mock_page, temp_screenshot_dir):
        """_upload_via_any_input should return False when no inputs found."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        mock_page.locator.return_value.all.return_value = []

        result = import_page._upload_via_any_input("/path/to/file.csv")

        assert result is False

    def test_wait_for_import_complete_success(self, mock_page, temp_screenshot_dir):
        """wait_for_import_complete should return success result."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "is_visible", return_value=True):
            with patch.object(import_page, "_get_error_messages", return_value=[]):
                with patch.object(import_page, "_get_warning_messages", return_value=[]):
                    result = import_page.wait_for_import_complete()

                    assert result.success is True

    def test_wait_for_import_complete_with_errors(self, mock_page, temp_screenshot_dir):
        """wait_for_import_complete should detect errors."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "is_visible", return_value=True):
            with patch.object(import_page, "_get_error_messages", return_value=["Error 1"]):
                with patch.object(import_page, "_get_warning_messages", return_value=[]):
                    result = import_page.wait_for_import_complete()

                    assert result.success is False
                    assert result.error_count == 1

    def test_get_error_messages_from_selectors(self, mock_page, temp_screenshot_dir):
        """_get_error_messages should iterate through selectors."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        # Mock locator with errors
        error_element = MagicMock()
        error_element.inner_text.return_value = "Error message"

        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_locator.nth.return_value = error_element
        mock_page.locator.return_value = mock_locator

        messages = import_page._get_error_messages()

        # Should return list (possibly with errors)
        assert isinstance(messages, list)

    def test_get_warning_messages_from_selectors(self, mock_page, temp_screenshot_dir):
        """_get_warning_messages should iterate through selectors."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        # Mock locator with warnings
        warning_element = MagicMock()
        warning_element.inner_text.return_value = "Warning message"

        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_locator.nth.return_value = warning_element
        mock_page.locator.return_value = mock_locator

        messages = import_page._get_warning_messages()

        assert isinstance(messages, list)

    def test_has_success_message_true(self, mock_page, temp_screenshot_dir):
        """_has_success_message should return True when success message found."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "is_visible", return_value=True):
            result = import_page._has_success_message()

        assert result is True

    def test_has_success_message_false(self, mock_page, temp_screenshot_dir):
        """_has_success_message should return False when no success message."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "is_visible", return_value=False):
            result = import_page._has_success_message()

        assert result is False

    def test_click_import_submit_button_fallback_text(self, mock_page, temp_screenshot_dir):
        """click_import_submit_button should try text search fallback."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        # First try (primary selectors) fails
        with patch.object(import_page, "click") as mock_click:
            mock_click.side_effect = ElementNotFoundError("not found")

            # Mock button text search to find import button
            button = MagicMock()
            button.inner_text.return_value = "Import"
            button.is_visible.return_value = True
            mock_page.locator.return_value.all.return_value = [button]

            result = import_page.click_import_submit_button()

            assert result is True
            button.click.assert_called_once()

    def test_click_import_submit_button_raises_on_failure(self, mock_page, temp_screenshot_dir):
        """click_import_submit_button should raise ImportError on failure."""
        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        with patch.object(import_page, "click") as mock_click:
            mock_click.side_effect = ElementNotFoundError("not found")

            # All fallbacks fail
            mock_page.locator.return_value.all.return_value = []

            with pytest.raises(ImportError, match="import submit"):
                import_page.click_import_submit_button()

    def test_get_preview_row_count_no_rows(self, mock_page, temp_screenshot_dir):
        """get_preview_row_count should return 0 when no rows found."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        import_page = ImportPage(mock_page)
        import_page.screenshot_dir = temp_screenshot_dir

        count = import_page.get_preview_row_count()
        assert count == 0
