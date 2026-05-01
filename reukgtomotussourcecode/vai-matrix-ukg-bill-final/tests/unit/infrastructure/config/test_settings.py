"""
Unit tests for settings configuration.
"""

import os
import pytest
from unittest.mock import patch


class TestUKGSettingsDaysToProcess:
    """Tests for UKG days_to_process setting."""

    def test_days_to_process_defaults_to_none(self):
        """Should default days_to_process to None when not set."""
        from src.infrastructure.config.settings import UKGSettings

        with patch.dict(os.environ, {}, clear=True):
            settings = UKGSettings()

            assert settings.days_to_process is None

    def test_days_to_process_reads_from_env(self):
        """Should read days_to_process from UKG_DAYS_TO_PROCESS env var."""
        from src.infrastructure.config.settings import UKGSettings

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "7"}, clear=True):
            settings = UKGSettings()

            assert settings.days_to_process == 7

    def test_days_to_process_accepts_zero(self):
        """Should accept days_to_process=0 for today only."""
        from src.infrastructure.config.settings import UKGSettings

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "0"}, clear=True):
            settings = UKGSettings()

            assert settings.days_to_process == 0

    def test_days_to_process_accepts_large_value(self):
        """Should accept large days_to_process values."""
        from src.infrastructure.config.settings import UKGSettings

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "365"}, clear=True):
            settings = UKGSettings()

            assert settings.days_to_process == 365

    def test_days_to_process_type_validation(self):
        """Should validate days_to_process is an integer."""
        from src.infrastructure.config.settings import UKGSettings
        from pydantic import ValidationError

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "not_a_number"}, clear=True):
            with pytest.raises(ValidationError):
                UKGSettings()

    def test_days_to_process_with_other_settings(self):
        """Should work with other UKG settings."""
        from src.infrastructure.config.settings import UKGSettings

        with patch.dict(os.environ, {
            "UKG_BASE_URL": "https://ukg.example.com",
            "UKG_USERNAME": "testuser",
            "UKG_PASSWORD": "testpass",
            "UKG_CUSTOMER_API_KEY": "api_key_123",
            "UKG_DAYS_TO_PROCESS": "5",
        }, clear=True):
            settings = UKGSettings()

            assert settings.base_url == "https://ukg.example.com"
            assert settings.username == "testuser"
            assert settings.days_to_process == 5


class TestSettingsDaysToProcessAccess:
    """Tests for accessing days_to_process via root Settings."""

    def test_access_via_ukg_property(self):
        """Should access days_to_process via settings.ukg.days_to_process."""
        from src.infrastructure.config.settings import Settings

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "3"}, clear=True):
            settings = Settings()

            assert settings.ukg.days_to_process == 3

    def test_ukg_property_returns_ukg_settings_instance(self):
        """Should return UKGSettings instance from ukg property."""
        from src.infrastructure.config.settings import Settings, UKGSettings

        settings = Settings()

        assert isinstance(settings.ukg, UKGSettings)

    def test_days_to_process_none_when_not_set(self):
        """Should return None when UKG_DAYS_TO_PROCESS not set."""
        from src.infrastructure.config.settings import Settings

        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.ukg.days_to_process is None


class TestGetSettingsCachingWithDaysToProcess:
    """Tests for get_settings caching behavior with days_to_process."""

    def test_get_settings_caches_days_to_process(self):
        """Should cache settings including days_to_process."""
        from src.infrastructure.config.settings import get_settings

        # Clear cache
        get_settings.cache_clear()

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "10"}, clear=True):
            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2
            assert settings1.ukg.days_to_process == 10

    def test_cache_clear_reloads_days_to_process(self):
        """Should reload settings after cache_clear."""
        from src.infrastructure.config.settings import get_settings

        # Clear cache and set initial value
        get_settings.cache_clear()

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "5"}, clear=True):
            settings1 = get_settings()
            assert settings1.ukg.days_to_process == 5

        # Clear cache again
        get_settings.cache_clear()

        # Change env var - note: in reality this would require process restart
        # but we're testing the caching mechanism
        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "15"}, clear=True):
            settings2 = get_settings()
            assert settings2.ukg.days_to_process == 15


class TestDaysToProcessIntegration:
    """Integration tests for days_to_process setting end-to-end."""

    def test_setting_flows_to_sync_service(self):
        """Should flow from env var through settings to SyncService."""
        from unittest.mock import MagicMock
        from src.infrastructure.config.settings import UKGSettings
        from src.application.services.sync_service import SyncService

        with patch.dict(os.environ, {"UKG_DAYS_TO_PROCESS": "7"}, clear=True):
            ukg_settings = UKGSettings()
            days = ukg_settings.days_to_process

            # Create sync service with this value
            service = SyncService(
                employee_repository=MagicMock(),
                bill_user_repository=MagicMock(),
                days_to_process=days,
            )

            assert service.days_to_process == 7

    def test_none_setting_flows_to_sync_service(self):
        """Should flow None from settings to SyncService when not set."""
        from unittest.mock import MagicMock
        from src.infrastructure.config.settings import UKGSettings
        from src.application.services.sync_service import SyncService

        with patch.dict(os.environ, {}, clear=True):
            ukg_settings = UKGSettings()
            days = ukg_settings.days_to_process

            service = SyncService(
                employee_repository=MagicMock(),
                bill_user_repository=MagicMock(),
                days_to_process=days,
            )

            assert service.days_to_process is None
