"""Tests for configuration settings."""

import pytest
from unittest.mock import patch, MagicMock

from src.infrastructure.config.settings import (
    UKGSettings,
    TravelPerkSettings,
    BatchSettings,
)


class TestUKGSettings:
    """Test cases for UKGSettings."""

    def test_create_with_values(self):
        """Test creating settings with values."""
        settings = UKGSettings(
            base_url="https://custom.ultipro.com",
            username="user",
            password="pass",
            basic_b64="",
            customer_api_key="api-key",
            timeout=60.0,
        )

        assert settings.base_url == "https://custom.ultipro.com"
        assert settings.username == "user"
        assert settings.password == "pass"
        assert settings.customer_api_key == "api-key"
        assert settings.timeout == 60.0

    def test_from_env(self, monkeypatch):
        """Test creating settings from environment."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret.side_effect = lambda key: {
            "UKG_BASE_URL": "https://env.ultipro.com",
            "UKG_USERNAME": "env_user",
            "UKG_PASSWORD": "env_pass",
            "UKG_BASIC_B64": "",
            "UKG_CUSTOMER_API_KEY": "env-api-key",
            "UKG_TIMEOUT": "90",
        }.get(key)

        with patch("src.infrastructure.config.settings.get_secrets_manager") as mock_get:
            mock_get.return_value = mock_secrets
            settings = UKGSettings.from_env()

            assert settings.base_url == "https://env.ultipro.com"
            assert settings.username == "env_user"
            assert settings.customer_api_key == "env-api-key"
            assert settings.timeout == 90.0

    def test_from_env_defaults(self):
        """Test from_env uses defaults when vars not set."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret.return_value = None

        with patch("src.infrastructure.config.settings.get_secrets_manager") as mock_get:
            mock_get.return_value = mock_secrets
            settings = UKGSettings.from_env()

            assert settings.base_url == "https://service4.ultipro.com"
            assert settings.timeout == 45.0

    def test_validate_success(self):
        """Test validate passes with valid settings."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="user",
            password="pass",
            basic_b64="",
            customer_api_key="api-key",
        )

        settings.validate()  # Should not raise

    def test_validate_success_with_b64(self):
        """Test validate passes with base64 token."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="",
            password="",
            basic_b64="dGVzdDp0ZXN0",
            customer_api_key="api-key",
        )

        settings.validate()  # Should not raise

    def test_validate_missing_api_key(self):
        """Test validate raises error when API key missing."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="user",
            password="pass",
            basic_b64="",
            customer_api_key="",
        )

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "Missing UKG_CUSTOMER_API_KEY" in str(exc_info.value)

    def test_validate_missing_auth(self):
        """Test validate raises error when auth missing."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="",
            password="",
            basic_b64="",
            customer_api_key="api-key",
        )

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "Missing UKG_USERNAME/UKG_PASSWORD" in str(exc_info.value)


class TestTravelPerkSettings:
    """Test cases for TravelPerkSettings."""

    def test_default_values(self):
        """Test default values are set."""
        settings = TravelPerkSettings(
            api_base="https://app.sandbox-travelperk.com",
            api_key="test-key",
        )

        assert settings.timeout == 60.0
        assert settings.max_retries == 2

    def test_custom_values(self):
        """Test custom values are set."""
        settings = TravelPerkSettings(
            api_base="https://custom.travelperk.com",
            api_key="custom-key",
            timeout=90.0,
            max_retries=5,
        )

        assert settings.api_base == "https://custom.travelperk.com"
        assert settings.api_key == "custom-key"
        assert settings.timeout == 90.0
        assert settings.max_retries == 5

    def test_from_env(self):
        """Test creating settings from environment."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret.side_effect = lambda key: {
            "TRAVELPERK_API_BASE": "https://env.travelperk.com",
            "TRAVELPERK_API_KEY": "env-key",
            "TRAVELPERK_TIMEOUT": "120",
            "MAX_RETRIES": "3",
        }.get(key)

        with patch("src.infrastructure.config.settings.get_secrets_manager") as mock_get:
            mock_get.return_value = mock_secrets
            settings = TravelPerkSettings.from_env()

            assert settings.api_base == "https://env.travelperk.com"
            assert settings.api_key == "env-key"
            assert settings.timeout == 120.0
            assert settings.max_retries == 3

    def test_from_env_defaults(self):
        """Test from_env uses defaults when vars not set."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret.return_value = None

        with patch("src.infrastructure.config.settings.get_secrets_manager") as mock_get:
            mock_get.return_value = mock_secrets
            settings = TravelPerkSettings.from_env()

            assert settings.api_base == "https://app.sandbox-travelperk.com"
            assert settings.timeout == 60.0
            assert settings.max_retries == 2

    def test_validate_success(self):
        """Test validate passes with valid settings."""
        settings = TravelPerkSettings(
            api_base="https://app.travelperk.com",
            api_key="valid-key",
        )

        settings.validate()  # Should not raise

    def test_validate_missing_api_key(self):
        """Test validate raises error when API key missing."""
        settings = TravelPerkSettings(
            api_base="https://app.travelperk.com",
            api_key="",
        )

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "Missing TRAVELPERK_API_KEY" in str(exc_info.value)


class TestBatchSettings:
    """Test cases for BatchSettings."""

    def test_default_values(self):
        """Test default values are set."""
        settings = BatchSettings()

        assert settings.company_id == ""
        assert settings.states_filter is None
        assert settings.employee_type_codes is None
        assert settings.workers == 12
        assert settings.dry_run is False
        assert settings.save_local is False
        assert settings.limit == 0
        assert settings.out_dir == "data/batch"

    def test_custom_values(self):
        """Test custom values are set."""
        settings = BatchSettings(
            company_id="J9A6Y",
            states_filter="FL,TX",
            employee_type_codes=["FTC", "PTC"],
            workers=8,
            dry_run=True,
            save_local=True,
            limit=100,
            out_dir="/custom/dir",
        )

        assert settings.company_id == "J9A6Y"
        assert settings.states_filter == "FL,TX"
        assert settings.employee_type_codes == ["FTC", "PTC"]
        assert settings.workers == 8
        assert settings.dry_run is True
        assert settings.save_local is True
        assert settings.limit == 100
        assert settings.out_dir == "/custom/dir"

    def test_from_env(self, monkeypatch):
        """Test creating settings from environment."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("STATES", "FL,TX")
        monkeypatch.setenv("EMPLOYEE_TYPE_CODES", "FTC,PTC")
        monkeypatch.setenv("WORKERS", "8")
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("SAVE_LOCAL", "1")
        monkeypatch.setenv("LIMIT", "100")
        monkeypatch.setenv("OUT_DIR", "/env/dir")

        settings = BatchSettings.from_env()

        assert settings.company_id == "J9A6Y"
        assert settings.states_filter == "FL,TX"
        assert settings.employee_type_codes == ["FTC", "PTC"]
        assert settings.workers == 8
        assert settings.dry_run is True
        assert settings.save_local is True
        assert settings.limit == 100
        assert settings.out_dir == "/env/dir"

    def test_from_env_defaults(self, monkeypatch):
        """Test from_env uses defaults when vars not set."""
        for var in ["COMPANY_ID", "STATES", "EMPLOYEE_TYPE_CODES", "WORKERS",
                    "DRY_RUN", "SAVE_LOCAL", "LIMIT", "OUT_DIR"]:
            monkeypatch.delenv(var, raising=False)

        settings = BatchSettings.from_env()

        assert settings.company_id == ""
        assert settings.states_filter is None
        assert settings.employee_type_codes is None
        assert settings.workers == 12
        assert settings.dry_run is False

    def test_from_env_empty_states(self, monkeypatch):
        """Test STATES empty string becomes None."""
        monkeypatch.setenv("STATES", "")

        settings = BatchSettings.from_env()
        assert settings.states_filter is None

    def test_from_env_dry_run_zero(self, monkeypatch):
        """Test DRY_RUN=0 is False."""
        monkeypatch.setenv("DRY_RUN", "0")

        settings = BatchSettings.from_env()
        assert settings.dry_run is False

    def test_from_env_employee_type_codes_whitespace(self, monkeypatch):
        """Test employee type codes strips whitespace."""
        monkeypatch.setenv("EMPLOYEE_TYPE_CODES", " FTC , PTC , ")

        settings = BatchSettings.from_env()
        assert settings.employee_type_codes == ["FTC", "PTC"]
