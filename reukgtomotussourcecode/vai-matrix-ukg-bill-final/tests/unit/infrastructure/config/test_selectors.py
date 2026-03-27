"""
Unit tests for selector configuration loader.
"""

from pathlib import Path
import tempfile

import pytest
import yaml

from src.infrastructure.config.selectors import (
    SelectorConfig,
    TimeoutConfig,
    ViewportConfig,
    LoginSelectors,
    CompanySelectors,
    PopupSelectors,
    PeopleSelectors,
    ImportSelectors,
    UserDetailsSelectors,
    CommonSelectors,
    load_selectors,
    get_selectors,
    reload_selectors,
)


class TestTimeoutConfig:
    """Tests for TimeoutConfig dataclass."""

    def test_default_values(self):
        """Should have sensible default timeout values."""
        config = TimeoutConfig()
        assert config.default == 60000
        assert config.short == 3000
        assert config.medium == 10000
        assert config.long == 30000
        assert config.page_load == 5000

    def test_custom_values(self):
        """Should accept custom timeout values."""
        config = TimeoutConfig(
            default=120000,
            short=1000,
            medium=5000,
            long=60000,
            page_load=10000,
        )
        assert config.default == 120000
        assert config.short == 1000


class TestViewportConfig:
    """Tests for ViewportConfig dataclass."""

    def test_default_values(self):
        """Should have 1920x1080 as default."""
        config = ViewportConfig()
        assert config.width == 1920
        assert config.height == 1080

    def test_custom_values(self):
        """Should accept custom viewport values."""
        config = ViewportConfig(width=1280, height=720)
        assert config.width == 1280
        assert config.height == 720


class TestLoginSelectors:
    """Tests for LoginSelectors dataclass."""

    def test_has_email_selectors(self):
        """Should have email input selectors."""
        selectors = LoginSelectors()
        assert len(selectors.email_input) > 0
        assert any("email" in s for s in selectors.email_input)

    def test_has_password_selectors(self):
        """Should have password input selectors."""
        selectors = LoginSelectors()
        assert len(selectors.password_input) > 0
        assert any("password" in s for s in selectors.password_input)

    def test_has_submit_selectors(self):
        """Should have submit button selectors."""
        selectors = LoginSelectors()
        assert len(selectors.submit_button) > 0


class TestCompanySelectors:
    """Tests for CompanySelectors dataclass."""

    def test_has_xpath_template(self):
        """Should have XPath template with placeholder."""
        selectors = CompanySelectors()
        assert "{company_name}" in selectors.company_by_name_xpath

    def test_xpath_template_format(self):
        """XPath template should be formattable."""
        selectors = CompanySelectors()
        xpath = selectors.company_by_name_xpath.format(company_name="Test Company")
        assert "Test Company" in xpath


class TestPopupSelectors:
    """Tests for PopupSelectors dataclass."""

    def test_has_close_button_selectors(self):
        """Should have close button selectors."""
        selectors = PopupSelectors()
        assert len(selectors.close_button) > 0


class TestPeopleSelectors:
    """Tests for PeopleSelectors dataclass."""

    def test_has_url_pattern(self):
        """Should have URL pattern with company_id placeholder."""
        selectors = PeopleSelectors()
        assert "{company_id}" in selectors.page_url_pattern

    def test_has_import_button_selectors(self):
        """Should have import button selectors."""
        selectors = PeopleSelectors()
        assert len(selectors.import_button) > 0


class TestImportSelectors:
    """Tests for ImportSelectors dataclass."""

    def test_has_file_input_selectors(self):
        """Should have file input selectors."""
        selectors = ImportSelectors()
        assert len(selectors.file_input) > 0
        assert any("file" in s for s in selectors.file_input)

    def test_has_submit_button_selectors(self):
        """Should have submit button selectors."""
        selectors = ImportSelectors()
        assert len(selectors.submit_button) > 0


class TestSelectorConfig:
    """Tests for SelectorConfig composite dataclass."""

    def test_default_initialization(self):
        """Should initialize with all default components."""
        config = SelectorConfig()
        assert config.timeouts is not None
        assert config.viewport is not None
        assert config.login is not None
        assert config.company_selection is not None
        assert config.popup is not None
        assert config.people is not None
        assert config.import_page is not None
        assert config.user_details is not None
        assert config.common is not None


class TestLoadSelectors:
    """Tests for load_selectors function."""

    def test_load_from_default_path(self):
        """Should load selectors from default path."""
        config = load_selectors()
        assert isinstance(config, SelectorConfig)
        # Verify some content was loaded
        assert config.timeouts.default > 0

    def test_load_from_custom_path(self):
        """Should load selectors from custom path."""
        # Create temporary YAML file
        yaml_content = {
            "timeouts": {"default": 99999, "short": 1111},
            "viewport": {"width": 800, "height": 600},
            "login": {
                "email_input": ["input.custom-email"],
                "password_input": ["input.custom-password"],
                "submit_button": ["button.custom-submit"],
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(yaml_content, f)
            temp_path = Path(f.name)

        try:
            config = load_selectors(temp_path)
            assert config.timeouts.default == 99999
            assert config.timeouts.short == 1111
            assert config.viewport.width == 800
            assert "input.custom-email" in config.login.email_input
        finally:
            temp_path.unlink()

    def test_load_missing_file_returns_defaults(self):
        """Should return defaults if file doesn't exist."""
        config = load_selectors(Path("/nonexistent/path/selectors.yaml"))
        assert isinstance(config, SelectorConfig)
        assert config.timeouts.default == 60000  # Default value

    def test_load_empty_file_returns_defaults(self):
        """Should return defaults for empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")  # Empty file
            temp_path = Path(f.name)

        try:
            config = load_selectors(temp_path)
            assert isinstance(config, SelectorConfig)
        finally:
            temp_path.unlink()

    def test_partial_config_fills_defaults(self):
        """Should fill missing sections with defaults."""
        yaml_content = {
            "timeouts": {"default": 50000},
            # Missing other sections
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(yaml_content, f)
            temp_path = Path(f.name)

        try:
            config = load_selectors(temp_path)
            assert config.timeouts.default == 50000
            # Other sections should have defaults
            assert config.login is not None
            assert config.viewport is not None
        finally:
            temp_path.unlink()


class TestGetSelectors:
    """Tests for get_selectors singleton function."""

    def test_returns_selector_config(self):
        """Should return SelectorConfig instance."""
        config = get_selectors()
        assert isinstance(config, SelectorConfig)

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        config1 = get_selectors()
        config2 = get_selectors()
        # Note: Due to singleton pattern, these should be the same
        assert config1 is config2


class TestReloadSelectors:
    """Tests for reload_selectors function."""

    def test_reload_returns_new_config(self):
        """Should reload and return new config."""
        config = reload_selectors()
        assert isinstance(config, SelectorConfig)

    def test_reload_updates_global(self):
        """Should update the global singleton."""
        reload_selectors()
        config = get_selectors()
        assert isinstance(config, SelectorConfig)
