"""Tests for TravelPerk batch runner CLI."""

import os
import pytest
import sys
from unittest.mock import MagicMock, patch

from src.presentation.cli.batch_runner import (
    parse_args,
    parse_states,
    parse_list,
    main,
)


class TestParseArgs:
    """Test cases for parse_args function."""

    def test_default_args(self):
        """Test parsing with no arguments."""
        with patch.object(sys, "argv", ["batch_runner.py"]):
            args = parse_args()

        assert args.company_id is None
        assert args.states is None
        assert args.workers is None
        assert args.dry_run is False
        assert args.save_local is False
        assert args.limit is None
        assert args.insert_supervisor is None
        assert args.employee_type_codes is None

    def test_company_id(self):
        """Test parsing company-id argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--company-id", "J9A6Y"]):
            args = parse_args()

        assert args.company_id == "J9A6Y"

    def test_states(self):
        """Test parsing states argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--states", "FL,TX,CA"]):
            args = parse_args()

        assert args.states == "FL,TX,CA"

    def test_workers(self):
        """Test parsing workers argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--workers", "8"]):
            args = parse_args()

        assert args.workers == 8

    def test_dry_run_flag(self):
        """Test parsing dry-run flag."""
        with patch.object(sys, "argv", ["batch_runner.py", "--dry-run"]):
            args = parse_args()

        assert args.dry_run is True

    def test_save_local_flag(self):
        """Test parsing save-local flag."""
        with patch.object(sys, "argv", ["batch_runner.py", "--save-local"]):
            args = parse_args()

        assert args.save_local is True

    def test_limit(self):
        """Test parsing limit argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--limit", "10"]):
            args = parse_args()

        assert args.limit == 10

    def test_insert_supervisor(self):
        """Test parsing insert-supervisor argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--insert-supervisor", "99999,99998"]):
            args = parse_args()

        assert args.insert_supervisor == "99999,99998"

    def test_employee_type_codes(self):
        """Test parsing employee-type-codes argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--employee-type-codes", "FTC,HRC"]):
            args = parse_args()

        assert args.employee_type_codes == "FTC,HRC"

    def test_all_args(self):
        """Test parsing all arguments."""
        with patch.object(
            sys,
            "argv",
            [
                "batch_runner.py",
                "--company-id", "J9A6Y",
                "--states", "FL,TX",
                "--workers", "12",
                "--dry-run",
                "--save-local",
                "--limit", "100",
                "--insert-supervisor", "99999",
                "--employee-type-codes", "FTC",
            ],
        ):
            args = parse_args()

        assert args.company_id == "J9A6Y"
        assert args.states == "FL,TX"
        assert args.workers == 12
        assert args.dry_run is True
        assert args.save_local is True
        assert args.limit == 100
        assert args.insert_supervisor == "99999"
        assert args.employee_type_codes == "FTC"


class TestParseStates:
    """Test cases for parse_states function."""

    def test_parse_single_state(self):
        """Test parsing single state."""
        result = parse_states("FL")
        assert result == {"FL"}

    def test_parse_multiple_states(self):
        """Test parsing multiple states."""
        result = parse_states("FL,TX,CA")
        assert result == {"FL", "TX", "CA"}

    def test_parse_states_with_spaces(self):
        """Test parsing states with whitespace."""
        result = parse_states(" FL , TX , CA ")
        assert result == {"FL", "TX", "CA"}

    def test_parse_states_uppercase(self):
        """Test states are uppercased."""
        result = parse_states("fl,tx,ca")
        assert result == {"FL", "TX", "CA"}

    def test_parse_none_returns_none(self):
        """Test None input returns None."""
        result = parse_states(None)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        """Test empty string returns None."""
        result = parse_states("")
        assert result is None


class TestParseList:
    """Test cases for parse_list function."""

    def test_parse_single_item(self):
        """Test parsing single item."""
        result = parse_list("FTC")
        assert result == ["FTC"]

    def test_parse_multiple_items(self):
        """Test parsing multiple items."""
        result = parse_list("FTC,HRC,TMC")
        assert result == ["FTC", "HRC", "TMC"]

    def test_parse_with_spaces(self):
        """Test parsing items with whitespace."""
        result = parse_list(" FTC , HRC , TMC ")
        assert result == ["FTC", "HRC", "TMC"]

    def test_parse_none_returns_none(self):
        """Test None input returns None."""
        result = parse_list(None)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        """Test empty string returns None."""
        result = parse_list("")
        assert result is None

    def test_parse_with_empty_entries(self):
        """Test parsing with empty entries."""
        result = parse_list("FTC,,HRC,")
        assert result == ["FTC", "HRC"]


class TestMain:
    """Test cases for main function."""

    @pytest.fixture
    def mock_clients(self):
        """Create mock clients."""
        with patch(
            "src.presentation.cli.batch_runner.UKGClient"
        ) as mock_ukg, patch(
            "src.presentation.cli.batch_runner.TravelPerkClient"
        ) as mock_tp, patch(
            "src.presentation.cli.batch_runner.UserSyncService"
        ) as mock_sync:
            mock_ukg_instance = MagicMock()
            mock_ukg_instance.get_all_employment_details_by_company.return_value = []
            mock_ukg.return_value = mock_ukg_instance

            mock_tp_instance = MagicMock()
            mock_tp.return_value = mock_tp_instance

            mock_sync_instance = MagicMock()
            mock_sync_instance.sync_batch.return_value = {}
            mock_sync_instance.insert_supervisors.return_value = {}
            mock_sync.return_value = mock_sync_instance

            yield {
                "ukg": mock_ukg,
                "ukg_instance": mock_ukg_instance,
                "travelperk": mock_tp,
                "travelperk_instance": mock_tp_instance,
                "sync": mock_sync,
                "sync_instance": mock_sync_instance,
            }

    def test_main_success(self, mock_clients, monkeypatch):
        """Test main function executes successfully."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        mock_clients["ukg_instance"].get_all_employment_details_by_company.assert_called_once()
        mock_clients["sync_instance"].sync_batch.assert_called_once()

    def test_main_with_cli_company_id(self, mock_clients, monkeypatch):
        """Test main with company ID from CLI."""
        with patch.object(sys, "argv", ["batch_runner.py", "--company-id", "ABCDE"]):
            main()

        mock_clients["ukg_instance"].get_all_employment_details_by_company.assert_called_once()
        call_args = mock_clients["ukg_instance"].get_all_employment_details_by_company.call_args
        assert call_args[0][0] == "ABCDE"

    def test_main_missing_company_id(self, mock_clients, monkeypatch):
        """Test main fails without company ID."""
        monkeypatch.delenv("COMPANY_ID", raising=False)

        with patch.object(sys, "argv", ["batch_runner.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert "company-id" in str(exc_info.value).lower() or "COMPANY_ID" in str(exc_info.value)

    def test_main_sets_workers_env(self, mock_clients, monkeypatch):
        """Test main sets WORKERS environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--workers", "8"]):
            main()

        assert os.environ.get("WORKERS") == "8"

    def test_main_sets_dry_run_env(self, mock_clients, monkeypatch):
        """Test main sets DRY_RUN environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--dry-run"]):
            main()

        assert os.environ.get("DRY_RUN") == "1"

    def test_main_sets_save_local_env(self, mock_clients, monkeypatch):
        """Test main sets SAVE_LOCAL environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--save-local"]):
            main()

        assert os.environ.get("SAVE_LOCAL") == "1"

    def test_main_sets_limit_env(self, mock_clients, monkeypatch):
        """Test main sets LIMIT environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--limit", "50"]):
            main()

        assert os.environ.get("LIMIT") == "50"

    def test_main_with_states_filter(self, mock_clients, monkeypatch):
        """Test main with states filter."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--states", "FL,TX"]):
            main()

        call_args = mock_clients["sync_instance"].sync_batch.call_args
        assert call_args[1]["states_filter"] == {"FL", "TX"}

    def test_main_with_insert_supervisor(self, mock_clients, monkeypatch, caplog):
        """Test main with supervisor pre-insertion."""
        import logging
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        mock_clients["sync_instance"].insert_supervisors.return_value = {"99999": "tp-sup-id"}

        with caplog.at_level(logging.INFO):
            with patch.object(sys, "argv", ["batch_runner.py", "--insert-supervisor", "99999"]):
                main()

        mock_clients["sync_instance"].insert_supervisors.assert_called_once()
        # Check log messages instead of stdout
        assert any("supervisor" in record.message.lower() for record in caplog.records)

    def test_main_with_employee_type_codes(self, mock_clients, monkeypatch):
        """Test main with employee type code filter."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with patch.object(sys, "argv", ["batch_runner.py", "--employee-type-codes", "FTC,HRC"]):
            main()

        call_args = mock_clients["ukg_instance"].get_all_employment_details_by_company.call_args
        assert call_args[1]["employee_type_codes"] == ["FTC", "HRC"]

    def test_main_saves_mapping(self, mock_clients, monkeypatch, tmp_path):
        """Test main saves mapping to file."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        mock_clients["sync_instance"].sync_batch.return_value = {"12345": "tp-id-123"}

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        mapping_file = tmp_path / "employee_to_travelperk_id_mapping.json"
        assert mapping_file.exists()

    def test_main_prints_config(self, mock_clients, monkeypatch, caplog):
        """Test main logs configuration."""
        import logging
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")

        with caplog.at_level(logging.INFO):
            with patch.object(sys, "argv", ["batch_runner.py"]):
                main()

        # Check log messages for configuration output
        log_text = " ".join(record.message for record in caplog.records)
        assert "CONFIGURATION" in log_text or "Company ID" in log_text
        assert "J9A6Y" in log_text
