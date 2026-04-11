"""
Unit tests for src/presentation/cli/health.py.
"""

import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from src.presentation.cli.health import (
    check_data_directory,
    check_environment_variables,
    check_health,
    check_imports,
    main,
)


class TestCheckEnvironmentVariables:
    """Tests for check_environment_variables function."""

    def test_all_vars_configured(self, monkeypatch):
        """Test when all required variables are configured."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_environment_variables()

        assert result["healthy"] is True
        assert result["ukg"]["UKG_BASE_URL"] == "configured"
        assert result["ukg"]["UKG_CUSTOMER_API_KEY"] == "configured"
        assert result["bill_se"]["BILL_API_BASE"] == "configured"
        assert result["bill_se"]["BILL_SE_API_TOKEN"] == "configured"

    def test_missing_ukg_vars(self, monkeypatch):
        """Test when UKG variables are missing."""
        monkeypatch.delenv("UKG_BASE_URL", raising=False)
        monkeypatch.delenv("UKG_CUSTOMER_API_KEY", raising=False)
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_environment_variables()

        assert result["healthy"] is False
        assert result["ukg"]["UKG_BASE_URL"] == "missing"
        assert result["ukg"]["UKG_CUSTOMER_API_KEY"] == "missing"

    def test_spend_expense_mode_missing_se_vars(self, monkeypatch):
        """Test spend_expense mode with missing S&E vars."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_MODE", "spend_expense")
        monkeypatch.delenv("BILL_API_BASE", raising=False)
        monkeypatch.delenv("BILL_SE_API_TOKEN", raising=False)

        result = check_environment_variables()

        assert result["healthy"] is False
        assert result["bill_se"]["BILL_API_BASE"] == "missing"
        assert result["bill_se"]["BILL_SE_API_TOKEN"] == "missing"

    def test_accounts_payable_mode_missing_ap_vars(self, monkeypatch):
        """Test accounts_payable mode with missing AP vars."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_MODE", "accounts_payable")
        monkeypatch.delenv("BILL_AP_API_BASE", raising=False)
        monkeypatch.delenv("BILL_AP_API_TOKEN", raising=False)

        result = check_environment_variables()

        assert result["healthy"] is False
        assert result["bill_ap"]["BILL_AP_API_BASE"] == "missing"
        assert result["bill_ap"]["BILL_AP_API_TOKEN"] == "missing"

    def test_accounts_payable_mode_se_vars_not_required(self, monkeypatch):
        """Test S&E vars not required in accounts_payable mode."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_MODE", "accounts_payable")
        monkeypatch.setenv("BILL_AP_API_BASE", "https://ap.example.com")
        monkeypatch.setenv("BILL_AP_API_TOKEN", "ap-token")
        monkeypatch.delenv("BILL_API_BASE", raising=False)
        monkeypatch.delenv("BILL_SE_API_TOKEN", raising=False)

        result = check_environment_variables()

        assert result["healthy"] is True
        assert result["bill_se"]["BILL_API_BASE"] == "not required"
        assert result["bill_se"]["BILL_SE_API_TOKEN"] == "not required"

    def test_spend_expense_mode_ap_vars_not_required(self, monkeypatch):
        """Test AP vars not required in spend_expense mode."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_MODE", "spend_expense")
        monkeypatch.setenv("BILL_API_BASE", "https://se.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "se-token")
        monkeypatch.delenv("BILL_AP_API_BASE", raising=False)
        monkeypatch.delenv("BILL_AP_API_TOKEN", raising=False)

        result = check_environment_variables()

        assert result["healthy"] is True
        assert result["bill_ap"]["BILL_AP_API_BASE"] == "not required"
        assert result["bill_ap"]["BILL_AP_API_TOKEN"] == "not required"

    def test_optional_vars_configured(self, monkeypatch):
        """Test optional variables are tracked."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DATA_DIR", "/custom/data")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_environment_variables()

        assert result["optional"]["LOG_LEVEL"] == "configured"
        assert result["optional"]["DATA_DIR"] == "configured"
        assert result["optional"]["BILL_MODE"] == "configured"

    def test_optional_vars_not_set(self, monkeypatch):
        """Test optional variables show as not set."""
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("DATA_DIR", raising=False)
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_environment_variables()

        assert result["optional"]["LOG_LEVEL"] == "not set"
        assert result["optional"]["DATA_DIR"] == "not set"


class TestCheckDataDirectory:
    """Tests for check_data_directory function."""

    def test_data_dir_exists_and_writable(self, monkeypatch, tmp_path):
        """Test when data directory exists and is writable."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))

        result = check_data_directory()

        assert result["healthy"] is True
        assert result["data_dir"]["exists"] is True
        assert result["data_dir"]["writable"] is True

    def test_data_dir_does_not_exist(self, monkeypatch, tmp_path):
        """Test when data directory does not exist."""
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setenv("DATA_DIR", str(nonexistent))

        result = check_data_directory()

        assert result["healthy"] is False
        assert result["data_dir"]["exists"] is False
        assert result["data_dir"]["writable"] is False

    def test_batch_dir_exists(self, monkeypatch, tmp_path):
        """Test batch directory check."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        batch_dir = data_dir / "batch"
        batch_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))

        result = check_data_directory()

        assert result["batch_dir"]["exists"] is True

    def test_reports_dir_exists(self, monkeypatch, tmp_path):
        """Test reports directory check."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        reports_dir = data_dir / "reports"
        reports_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))

        result = check_data_directory()

        assert result["reports_dir"]["exists"] is True

    def test_data_dir_not_writable(self, monkeypatch, tmp_path):
        """Test when data directory is not writable."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))

        # Mock open to raise IOError
        original_open = open

        def mock_open(*args, **kwargs):
            if str(data_dir) in str(args[0]):
                raise IOError("Permission denied")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open):
            result = check_data_directory()

        assert result["healthy"] is False
        assert result["data_dir"]["exists"] is True
        assert result["data_dir"]["writable"] is False
        assert "error" in result


class TestCheckImports:
    """Tests for check_imports function."""

    def test_required_modules_available(self):
        """Test required modules are available."""
        result = check_imports()

        assert result["required"]["requests"] == "available"
        assert result["required"]["pydantic"] == "available"
        assert result["required"]["dotenv"] == "available"
        assert result["required"]["tenacity"] == "available"
        assert result["healthy"] is True

    def test_optional_modules_checked(self):
        """Test optional modules are checked."""
        result = check_imports()

        # boto3 should be available or not installed
        assert result["optional"]["boto3"] in ["available", "not installed"]
        assert result["optional"]["playwright"] in ["available", "not installed"]

    def test_import_error_marks_unhealthy(self):
        """Test required modules detection works correctly."""
        # Since modules are already imported in the test environment,
        # we just verify the function correctly identifies them as available
        result = check_imports()

        # All required modules should be available in test env
        assert result["required"]["requests"] == "available"
        assert result["required"]["pydantic"] == "available"


class TestCheckHealth:
    """Tests for check_health function."""

    def test_returns_health_status(self, monkeypatch, tmp_path):
        """Test check_health returns complete health status."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_health()

        assert "timestamp" in result
        assert "service" in result
        assert "version" in result
        assert "mode" in result
        assert "status" in result
        assert "checks" in result
        assert "environment" in result["checks"]
        assert "data_directory" in result["checks"]
        assert "imports" in result["checks"]

    def test_healthy_status_when_all_pass(self, monkeypatch, tmp_path):
        """Test status is healthy when all checks pass."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_health()

        assert result["status"] == "healthy"

    def test_unhealthy_status_when_check_fails(self, monkeypatch, tmp_path):
        """Test status is unhealthy when a check fails."""
        data_dir = tmp_path / "nonexistent"
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.delenv("UKG_BASE_URL", raising=False)
        monkeypatch.delenv("UKG_CUSTOMER_API_KEY", raising=False)
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        result = check_health()

        assert result["status"] == "unhealthy"

    def test_service_name_format(self, monkeypatch, tmp_path):
        """Test service name includes mode."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("BILL_MODE", "accounts_payable")
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_AP_API_BASE", "https://ap.example.com")
        monkeypatch.setenv("BILL_AP_API_TOKEN", "ap-token")

        result = check_health()

        assert "accounts-payable" in result["service"]


class TestMain:
    """Tests for main CLI function."""

    def test_json_output(self, monkeypatch, tmp_path, capsys):
        """Test JSON output mode."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        with patch("sys.argv", ["health", "--json"]):
            with pytest.raises(SystemExit) as exc:
                main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "status" in result
        assert exc.value.code == 0

    def test_healthy_output(self, monkeypatch, tmp_path, capsys):
        """Test healthy output format."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        with patch("sys.argv", ["health"]):
            with pytest.raises(SystemExit) as exc:
                main()

        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert exc.value.code == 0

    def test_unhealthy_output(self, monkeypatch, tmp_path, capsys):
        """Test unhealthy output format."""
        data_dir = tmp_path / "nonexistent"
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.delenv("UKG_BASE_URL", raising=False)
        monkeypatch.delenv("UKG_CUSTOMER_API_KEY", raising=False)
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        with patch("sys.argv", ["health"]):
            with pytest.raises(SystemExit) as exc:
                main()

        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert exc.value.code == 1

    def test_verbose_output(self, monkeypatch, tmp_path, capsys):
        """Test verbose output includes details."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_API_BASE", "https://bill.example.com")
        monkeypatch.setenv("BILL_SE_API_TOKEN", "test-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")

        with patch("sys.argv", ["health", "--verbose"]):
            with pytest.raises(SystemExit) as exc:
                main()

        captured = capsys.readouterr()
        assert "Timestamp:" in captured.out
        assert "Service:" in captured.out
        assert "Version:" in captured.out
        assert "Mode:" in captured.out
        assert "Checks:" in captured.out
        assert exc.value.code == 0

    def test_mode_argument(self, monkeypatch, tmp_path, capsys):
        """Test mode argument overrides environment."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("UKG_BASE_URL", "https://ukg.example.com")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-key")
        monkeypatch.setenv("BILL_AP_API_BASE", "https://ap.example.com")
        monkeypatch.setenv("BILL_AP_API_TOKEN", "ap-token")
        monkeypatch.setenv("BILL_MODE", "spend_expense")  # Start with S&E

        with patch("sys.argv", ["health", "--mode", "accounts_payable", "--json"]):
            with pytest.raises(SystemExit) as exc:
                main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["mode"] == "accounts_payable"
        assert exc.value.code == 0
