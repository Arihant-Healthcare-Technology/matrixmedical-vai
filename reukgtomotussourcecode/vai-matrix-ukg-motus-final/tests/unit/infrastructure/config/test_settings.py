"""Tests for settings configuration."""

import pytest
import os
from unittest.mock import patch

from src.infrastructure.config.settings import (
    UKGSettings,
    MotusSettings,
    BatchSettings,
)


class TestUKGSettings:
    """Test cases for UKGSettings."""

    def test_default_values(self):
        """Test default values are set."""
        settings = UKGSettings()

        assert settings.base_url == "https://service4.ultipro.com"
        assert settings.username == ""
        assert settings.password == ""
        assert settings.customer_api_key == ""
        assert settings.basic_b64 == ""
        assert settings.timeout == 45.0
        assert settings.max_retries == 3

    def test_custom_values(self):
        """Test custom values are set."""
        settings = UKGSettings(
            base_url="https://custom.ultipro.com",
            username="user",
            password="pass",
            customer_api_key="api-key",
            timeout=60.0,
            max_retries=5,
        )

        assert settings.base_url == "https://custom.ultipro.com"
        assert settings.username == "user"
        assert settings.password == "pass"
        assert settings.customer_api_key == "api-key"
        assert settings.timeout == 60.0
        assert settings.max_retries == 5

    def test_from_env(self, monkeypatch):
        """Test creating settings from environment variables."""
        monkeypatch.setenv("UKG_BASE_URL", "https://env.ultipro.com")
        monkeypatch.setenv("UKG_USERNAME", "env_user")
        monkeypatch.setenv("UKG_PASSWORD", "env_pass")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "env-api-key")
        monkeypatch.setenv("UKG_TIMEOUT", "90")
        monkeypatch.setenv("UKG_MAX_RETRIES", "5")

        settings = UKGSettings.from_env()

        assert settings.base_url == "https://env.ultipro.com"
        assert settings.username == "env_user"
        assert settings.password == "env_pass"
        assert settings.customer_api_key == "env-api-key"
        assert settings.timeout == 90.0
        assert settings.max_retries == 5

    def test_from_env_defaults(self, monkeypatch):
        """Test from_env uses defaults when vars not set."""
        # Clear environment variables
        for var in ["UKG_BASE_URL", "UKG_USERNAME", "UKG_PASSWORD",
                    "UKG_CUSTOMER_API_KEY", "UKG_TIMEOUT", "UKG_MAX_RETRIES",
                    "UKG_BASIC_B64"]:
            monkeypatch.delenv(var, raising=False)

        settings = UKGSettings.from_env()

        assert settings.base_url == "https://service4.ultipro.com"
        assert settings.timeout == 45.0

    def test_get_auth_token_from_basic_b64(self):
        """Test get_auth_token returns pre-encoded token."""
        settings = UKGSettings(basic_b64="pre-encoded-token")

        token = settings.get_auth_token()
        assert token == "pre-encoded-token"

    def test_get_auth_token_from_basic_b64_strips_whitespace(self):
        """Test get_auth_token strips whitespace from pre-encoded token."""
        settings = UKGSettings(basic_b64="  pre-encoded-token  \n")

        token = settings.get_auth_token()
        assert token == "pre-encoded-token"

    def test_get_auth_token_from_credentials(self):
        """Test get_auth_token encodes username:password."""
        import base64

        settings = UKGSettings(username="testuser", password="testpass")

        token = settings.get_auth_token()
        expected = base64.b64encode(b"testuser:testpass").decode()
        assert token == expected

    def test_get_auth_token_missing_credentials(self):
        """Test get_auth_token raises error when credentials missing."""
        settings = UKGSettings()

        with pytest.raises(ValueError) as exc_info:
            settings.get_auth_token()

        assert "Missing UKG_USERNAME/UKG_PASSWORD" in str(exc_info.value)

    def test_get_auth_token_missing_username(self):
        """Test get_auth_token raises error when username missing."""
        settings = UKGSettings(password="testpass")

        with pytest.raises(ValueError):
            settings.get_auth_token()

    def test_get_auth_token_missing_password(self):
        """Test get_auth_token raises error when password missing."""
        settings = UKGSettings(username="testuser")

        with pytest.raises(ValueError):
            settings.get_auth_token()

    def test_validate_success(self):
        """Test validate passes with valid settings."""
        settings = UKGSettings(
            customer_api_key="api-key",
            basic_b64="auth-token",
        )

        # Should not raise
        settings.validate()

    def test_validate_missing_api_key(self):
        """Test validate raises error when API key missing."""
        settings = UKGSettings(basic_b64="auth-token")

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "Missing UKG_CUSTOMER_API_KEY" in str(exc_info.value)

    def test_validate_missing_auth(self):
        """Test validate raises error when auth missing."""
        settings = UKGSettings(customer_api_key="api-key")

        with pytest.raises(ValueError):
            settings.validate()


class TestMotusSettings:
    """Test cases for MotusSettings."""

    def test_default_values(self):
        """Test default values are set."""
        settings = MotusSettings()

        assert settings.api_base == "https://api.motus.com/v1"
        assert settings.jwt == ""
        assert settings.default_program_id == 21233
        assert settings.timeout == 45.0
        assert settings.max_retries == 3

    def test_custom_values(self):
        """Test custom values are set."""
        settings = MotusSettings(
            api_base="https://custom.motus.com/v1",
            jwt="custom-jwt",
            default_program_id=21232,
            timeout=60.0,
            max_retries=5,
        )

        assert settings.api_base == "https://custom.motus.com/v1"
        assert settings.jwt == "custom-jwt"
        assert settings.default_program_id == 21232
        assert settings.timeout == 60.0
        assert settings.max_retries == 5

    def test_from_env(self, monkeypatch):
        """Test creating settings from environment variables."""
        monkeypatch.setenv("MOTUS_API_BASE", "https://env.motus.com/v1")
        monkeypatch.setenv("MOTUS_JWT", "env-jwt-token")
        monkeypatch.setenv("MOTUS_PROGRAM_ID", "21232")
        monkeypatch.setenv("MOTUS_TIMEOUT", "90")
        monkeypatch.setenv("MOTUS_MAX_RETRIES", "5")

        settings = MotusSettings.from_env()

        assert settings.api_base == "https://env.motus.com/v1"
        assert settings.jwt == "env-jwt-token"
        assert settings.default_program_id == 21232
        assert settings.timeout == 90.0
        assert settings.max_retries == 5

    def test_from_env_defaults(self, monkeypatch):
        """Test from_env uses defaults when vars not set."""
        for var in ["MOTUS_API_BASE", "MOTUS_JWT", "MOTUS_PROGRAM_ID",
                    "MOTUS_TIMEOUT", "MOTUS_MAX_RETRIES"]:
            monkeypatch.delenv(var, raising=False)

        settings = MotusSettings.from_env()

        assert settings.api_base == "https://api.motus.com/v1"
        assert settings.default_program_id == 21233

    def test_validate_success(self):
        """Test validate passes with valid settings."""
        settings = MotusSettings(jwt="valid-jwt")

        # Should not raise
        settings.validate()

    def test_validate_missing_jwt(self):
        """Test validate raises error when JWT missing."""
        settings = MotusSettings()

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "Missing MOTUS_JWT" in str(exc_info.value)


class TestBatchSettings:
    """Test cases for BatchSettings."""

    def test_default_values(self):
        """Test default values are set."""
        settings = BatchSettings()

        assert settings.workers == 12
        assert settings.company_id == ""
        assert settings.states_filter is None
        assert settings.job_codes == ""
        assert settings.dry_run is False
        assert settings.save_local is False
        assert settings.probe is False
        assert settings.out_dir == "data/batch"
        assert settings.batch_run_days == 1  # Default is 1 day

    def test_custom_values(self):
        """Test custom values are set."""
        settings = BatchSettings(
            workers=8,
            company_id="J9A6Y",
            states_filter="FL,TX",
            job_codes="4154,4152",
            dry_run=True,
            save_local=True,
            probe=True,
            out_dir="/custom/dir",
            batch_run_days=7,
        )

        assert settings.workers == 8
        assert settings.company_id == "J9A6Y"
        assert settings.states_filter == "FL,TX"
        assert settings.job_codes == "4154,4152"
        assert settings.dry_run is True
        assert settings.save_local is True
        assert settings.probe is True
        assert settings.out_dir == "/custom/dir"
        assert settings.batch_run_days == 7

    def test_from_env(self, monkeypatch):
        """Test creating settings from environment variables."""
        monkeypatch.setenv("WORKERS", "8")
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("STATES", "FL,TX")
        monkeypatch.setenv("JOB_IDS", "4154,4152")
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("SAVE_LOCAL", "1")
        monkeypatch.setenv("PROBE", "1")
        monkeypatch.setenv("OUT_DIR", "/env/dir")
        monkeypatch.setenv("BATCH_RUN_DAYS", "7")

        settings = BatchSettings.from_env()

        assert settings.workers == 8
        assert settings.company_id == "J9A6Y"
        assert settings.states_filter == "FL,TX"
        assert settings.job_codes == "4154,4152"
        assert settings.dry_run is True
        assert settings.save_local is True
        assert settings.probe is True
        assert settings.out_dir == "/env/dir"
        assert settings.batch_run_days == 7

    def test_from_env_defaults(self, monkeypatch):
        """Test from_env uses defaults when vars not set."""
        for var in ["WORKERS", "COMPANY_ID", "STATES", "JOB_IDS",
                    "DRY_RUN", "SAVE_LOCAL", "PROBE", "OUT_DIR", "BATCH_RUN_DAYS"]:
            monkeypatch.delenv(var, raising=False)

        settings = BatchSettings.from_env()

        assert settings.workers == 12
        assert settings.dry_run is False
        assert settings.batch_run_days == 1  # Default is 1 day

    def test_from_env_dry_run_zero(self, monkeypatch):
        """Test DRY_RUN=0 is False."""
        monkeypatch.setenv("DRY_RUN", "0")

        settings = BatchSettings.from_env()
        assert settings.dry_run is False

    def test_from_env_dry_run_other(self, monkeypatch):
        """Test DRY_RUN with non-1 value is False."""
        monkeypatch.setenv("DRY_RUN", "yes")

        settings = BatchSettings.from_env()
        assert settings.dry_run is False

    def test_from_env_batch_run_days_1(self, monkeypatch):
        """Test BATCH_RUN_DAYS=1."""
        monkeypatch.setenv("BATCH_RUN_DAYS", "1")

        settings = BatchSettings.from_env()
        assert settings.batch_run_days == 1

    def test_from_env_batch_run_days_2(self, monkeypatch):
        """Test BATCH_RUN_DAYS=2."""
        monkeypatch.setenv("BATCH_RUN_DAYS", "2")

        settings = BatchSettings.from_env()
        assert settings.batch_run_days == 2

    def test_from_env_batch_run_days_7(self, monkeypatch):
        """Test BATCH_RUN_DAYS=7."""
        monkeypatch.setenv("BATCH_RUN_DAYS", "7")

        settings = BatchSettings.from_env()
        assert settings.batch_run_days == 7

    def test_validate_success(self):
        """Test validate passes with valid settings."""
        settings = BatchSettings(
            company_id="J9A6Y",
            job_codes="4154",
        )

        # Should not raise
        settings.validate()

    def test_validate_missing_company_id(self):
        """Test validate raises error when company_id missing."""
        settings = BatchSettings(job_codes="4154")

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "COMPANY_ID is required" in str(exc_info.value)

    def test_validate_missing_job_codes(self):
        """Test validate raises error when job_codes missing."""
        settings = BatchSettings(company_id="J9A6Y")

        with pytest.raises(ValueError) as exc_info:
            settings.validate()

        assert "JOB_IDS is required" in str(exc_info.value)


# ============ validate_or_exit Tests ============

class TestUKGSettingsValidateOrExit:
    """Tests for UKGSettings.validate_or_exit method."""

    def test_validate_or_exit_missing_api_key(self, monkeypatch):
        """Test validate_or_exit exits when API key missing."""
        settings = UKGSettings(basic_b64="token")

        with pytest.raises(SystemExit) as exc_info:
            settings.validate_or_exit()

        assert exc_info.value.code == 1

    def test_validate_or_exit_missing_auth(self, monkeypatch):
        """Test validate_or_exit exits when auth missing."""
        settings = UKGSettings(customer_api_key="api-key")

        with pytest.raises(SystemExit) as exc_info:
            settings.validate_or_exit()

        assert exc_info.value.code == 1

    def test_validate_or_exit_success(self):
        """Test validate_or_exit passes with valid settings."""
        settings = UKGSettings(
            customer_api_key="api-key",
            basic_b64="auth-token",
        )

        # Should not raise
        settings.validate_or_exit()


class TestMotusSettingsValidateOrExit:
    """Tests for MotusSettings.validate_or_exit method."""

    def test_validate_or_exit_missing_jwt(self):
        """Test validate_or_exit exits when JWT missing."""
        settings = MotusSettings()

        with pytest.raises(SystemExit) as exc_info:
            settings.validate_or_exit()

        assert exc_info.value.code == 1

    def test_validate_or_exit_invalid_jwt_format(self):
        """Test validate_or_exit exits when JWT has invalid format."""
        settings = MotusSettings(jwt="invalid-jwt-without-dots")

        with pytest.raises(SystemExit) as exc_info:
            settings.validate_or_exit()

        assert exc_info.value.code == 1

    def test_validate_or_exit_success(self):
        """Test validate_or_exit passes with valid JWT format."""
        settings = MotusSettings(jwt="header.payload.signature")

        # Should not raise
        settings.validate_or_exit()
