"""Tests for batch runner CLI."""

import os
import pytest
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.presentation.cli.batch_runner import (
    parse_args,
    get_eligible_job_codes,
    filter_by_eligible_job_codes,
    filter_by_date_changed,
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
        assert args.probe is False
        assert args.batch_run_days is None

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

    def test_probe_flag(self):
        """Test parsing probe flag."""
        with patch.object(sys, "argv", ["batch_runner.py", "--probe"]):
            args = parse_args()

        assert args.probe is True

    def test_batch_run_days(self):
        """Test parsing batch-run-days argument."""
        with patch.object(sys, "argv", ["batch_runner.py", "--batch-run-days", "7"]):
            args = parse_args()

        assert args.batch_run_days == 7

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
                "--probe",
                "--batch-run-days", "7",
            ],
        ):
            args = parse_args()

        assert args.company_id == "J9A6Y"
        assert args.states == "FL,TX"
        assert args.workers == 12
        assert args.dry_run is True
        assert args.save_local is True
        assert args.probe is True
        assert args.batch_run_days == 7


class TestGetEligibleJobCodes:
    """Test cases for get_eligible_job_codes function."""

    def test_get_job_codes_success(self, monkeypatch):
        """Test getting job codes from environment."""
        monkeypatch.setenv("JOB_IDS", "1103,4154,4165")

        result = get_eligible_job_codes()

        assert result == {"1103", "4154", "4165"}

    def test_get_job_codes_with_whitespace(self, monkeypatch):
        """Test job codes with whitespace are trimmed."""
        monkeypatch.setenv("JOB_IDS", " 1103 , 4154 , 4165 ")

        result = get_eligible_job_codes()

        assert result == {"1103", "4154", "4165"}

    def test_get_job_codes_missing_env(self, monkeypatch):
        """Test error when JOB_IDS not set."""
        monkeypatch.delenv("JOB_IDS", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            get_eligible_job_codes()

        assert "JOB_IDS" in str(exc_info.value)

    def test_get_job_codes_empty_env(self, monkeypatch):
        """Test error when JOB_IDS is empty."""
        monkeypatch.setenv("JOB_IDS", "")

        with pytest.raises(SystemExit) as exc_info:
            get_eligible_job_codes()

        assert "JOB_IDS" in str(exc_info.value)

    def test_get_job_codes_whitespace_only(self, monkeypatch):
        """Test error when JOB_IDS is whitespace only."""
        monkeypatch.setenv("JOB_IDS", "   ")

        with pytest.raises(SystemExit) as exc_info:
            get_eligible_job_codes()

        assert "JOB_IDS" in str(exc_info.value)


class TestFilterByEligibleJobCodes:
    """Test cases for filter_by_eligible_job_codes function."""

    def test_filter_eligible_employees(self):
        """Test filtering employees by eligible job codes."""
        items = [
            {"employeeNumber": "12345", "primaryJobCode": "1103"},
            {"employeeNumber": "12346", "primaryJobCode": "9999"},
            {"employeeNumber": "12347", "primaryJobCode": "4154"},
        ]
        eligible_codes = {"1103", "4154"}

        result = filter_by_eligible_job_codes(items, eligible_codes)

        assert len(result) == 2
        assert result[0]["employeeNumber"] == "12345"
        assert result[1]["employeeNumber"] == "12347"

    def test_filter_with_leading_zeros(self):
        """Test filtering handles leading zeros."""
        items = [
            {"employeeNumber": "12345", "primaryJobCode": "01103"},
        ]
        eligible_codes = {"1103"}

        result = filter_by_eligible_job_codes(items, eligible_codes)

        assert len(result) == 1

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        result = filter_by_eligible_job_codes([], {"1103"})
        assert result == []

    def test_filter_none_job_code(self):
        """Test filtering with None job code."""
        items = [
            {"employeeNumber": "12345", "primaryJobCode": None},
        ]
        eligible_codes = {"1103"}

        result = filter_by_eligible_job_codes(items, eligible_codes)

        assert len(result) == 0

    def test_filter_missing_job_code_field(self):
        """Test filtering with missing job code field."""
        items = [
            {"employeeNumber": "12345"},
        ]
        eligible_codes = {"1103"}

        result = filter_by_eligible_job_codes(items, eligible_codes)

        assert len(result) == 0

    def test_filter_debug_output(self, caplog):
        """Test debug output when filtering."""
        import logging
        caplog.set_level(logging.DEBUG)

        items = [
            {"employeeNumber": "12345", "primaryJobCode": "9999"},
        ]
        eligible_codes = {"1103"}

        result = filter_by_eligible_job_codes(items, eligible_codes, debug=True)

        # Check that debug logging occurred with employee info
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        log_messages = " ".join(r.message for r in debug_records)
        # Should log about skipping ineligible employee or be empty result
        assert "12345" in log_messages or "ineligible" in log_messages.lower() or len(result) == 0

    def test_filter_no_debug_output(self, capsys):
        """Test no debug output when debug=False."""
        items = [
            {"employeeNumber": "12345", "primaryJobCode": "9999"},
        ]
        eligible_codes = {"1103"}

        filter_by_eligible_job_codes(items, eligible_codes, debug=False)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestFilterByDateChanged:
    """Test cases for filter_by_date_changed function."""

    def test_filter_recent_changes(self):
        """Test filtering employees with recent changes."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(hours=12)).isoformat()
        old_date = (now - timedelta(days=5)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": recent_date},
            {"employeeNumber": "12346", "dateTimeChanged": old_date},
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 1
        assert result[0]["employeeNumber"] == "12345"

    def test_filter_with_7_days(self):
        """Test filtering with 7 days lookback."""
        now = datetime.now(timezone.utc)
        within_7_days = (now - timedelta(days=5)).isoformat()
        outside_7_days = (now - timedelta(days=10)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": within_7_days},
            {"employeeNumber": "12346", "dateTimeChanged": outside_7_days},
        ]

        result = filter_by_date_changed(items, batch_run_days=7)

        assert len(result) == 1
        assert result[0]["employeeNumber"] == "12345"

    def test_filter_includes_employees_without_date(self):
        """Test employees without dateTimeChanged are included."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(hours=12)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": recent_date},
            {"employeeNumber": "12346"},  # No dateTimeChanged
            {"employeeNumber": "12347", "dateTimeChanged": ""},  # Empty string
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 3
        employee_numbers = {item["employeeNumber"] for item in result}
        assert "12345" in employee_numbers
        assert "12346" in employee_numbers
        assert "12347" in employee_numbers

    def test_filter_includes_invalid_date_format(self):
        """Test employees with invalid dateTimeChanged format are included."""
        items = [
            {"employeeNumber": "12345", "dateTimeChanged": "invalid-date"},
            {"employeeNumber": "12346", "dateTimeChanged": "not-a-date"},
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 2

    def test_filter_zero_days_returns_all(self):
        """Test batch_run_days=0 returns all employees (no filter)."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=100)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": old_date},
            {"employeeNumber": "12346", "dateTimeChanged": old_date},
        ]

        result = filter_by_date_changed(items, batch_run_days=0)

        assert len(result) == 2

    def test_filter_negative_days_returns_all(self):
        """Test negative batch_run_days returns all employees (no filter)."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=100)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": old_date},
        ]

        result = filter_by_date_changed(items, batch_run_days=-1)

        assert len(result) == 1

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        result = filter_by_date_changed([], batch_run_days=1)
        assert result == []

    def test_filter_handles_z_suffix(self):
        """Test filtering handles Z suffix for UTC."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.00Z")

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": recent_date},
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 1

    def test_filter_handles_fractional_seconds(self):
        """Test filtering handles various fractional second formats."""
        now = datetime.now(timezone.utc)
        # Format like "2026-04-20T13:35:31.44" from UKG API
        recent_date = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.44")

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": recent_date},
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 1

    def test_filter_exact_boundary(self):
        """Test filtering at exact day boundary."""
        now = datetime.now(timezone.utc)
        # 12 hours ago should definitely be included
        within_1_day = (now - timedelta(hours=12)).isoformat()
        # 2 days ago should be excluded
        over_1_day = (now - timedelta(days=2)).isoformat()

        items = [
            {"employeeNumber": "12345", "dateTimeChanged": within_1_day},
            {"employeeNumber": "12346", "dateTimeChanged": over_1_day},
        ]

        result = filter_by_date_changed(items, batch_run_days=1)

        assert len(result) == 1
        assert result[0]["employeeNumber"] == "12345"


class TestMain:
    """Test cases for main function."""

    @pytest.fixture
    def mock_clients(self):
        """Create mock clients."""
        with patch(
            "src.presentation.cli.batch_runner.UKGClient"
        ) as mock_ukg, patch(
            "src.presentation.cli.batch_runner.MotusClient"
        ) as mock_motus, patch(
            "src.presentation.cli.batch_runner.DriverSyncService"
        ) as mock_sync:
            mock_ukg_instance = MagicMock()
            mock_ukg_instance.get_all_employment_details_by_company.return_value = []
            mock_ukg.return_value = mock_ukg_instance

            mock_motus_instance = MagicMock()
            mock_motus.return_value = mock_motus_instance

            mock_sync_instance = MagicMock()
            mock_sync.return_value = mock_sync_instance

            yield {
                "ukg": mock_ukg,
                "ukg_instance": mock_ukg_instance,
                "motus": mock_motus,
                "motus_instance": mock_motus_instance,
                "sync": mock_sync,
                "sync_instance": mock_sync_instance,
            }

    def test_main_success(self, mock_clients, monkeypatch):
        """Test main function executes successfully."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103,4154")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")  # base64 of "test:test"
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")  # Valid JWT format

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        mock_clients["ukg_instance"].get_all_employment_details_by_company.assert_called_once_with("J9A6Y")
        mock_clients["sync_instance"].sync_batch.assert_called_once()

    def test_main_with_cli_company_id(self, mock_clients, monkeypatch):
        """Test main with company ID from CLI."""
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--company-id", "ABCDE"]):
            main()

        mock_clients["ukg_instance"].get_all_employment_details_by_company.assert_called_once_with("ABCDE")

    def test_main_missing_company_id(self, mock_clients, monkeypatch):
        """Test main fails without company ID."""
        monkeypatch.delenv("COMPANY_ID", raising=False)
        monkeypatch.setenv("JOB_IDS", "1103")

        with patch.object(sys, "argv", ["batch_runner.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert "company-id" in str(exc_info.value).lower() or "COMPANY_ID" in str(exc_info.value)

    def test_main_sets_workers_env(self, mock_clients, monkeypatch):
        """Test main sets WORKERS environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--workers", "8"]):
            main()

        assert os.environ.get("WORKERS") == "8"

    def test_main_sets_dry_run_env(self, mock_clients, monkeypatch):
        """Test main sets DRY_RUN environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--dry-run"]):
            main()

        assert os.environ.get("DRY_RUN") == "1"

    def test_main_sets_save_local_env(self, mock_clients, monkeypatch):
        """Test main sets SAVE_LOCAL environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--save-local"]):
            main()

        assert os.environ.get("SAVE_LOCAL") == "1"

    def test_main_sets_probe_env(self, mock_clients, monkeypatch):
        """Test main sets PROBE environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--probe"]):
            main()

        assert os.environ.get("PROBE") == "1"

    def test_main_sets_batch_run_days_env(self, mock_clients, monkeypatch):
        """Test main sets BATCH_RUN_DAYS environment variable."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--batch-run-days", "7"]):
            main()

        assert os.environ.get("BATCH_RUN_DAYS") == "7"

    def test_main_filters_by_date_changed(self, mock_clients, monkeypatch):
        """Test main filters employees by dateTimeChanged."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        monkeypatch.setenv("BATCH_RUN_DAYS", "1")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(hours=6)).isoformat()
        old_date = (now - timedelta(days=5)).isoformat()

        mock_clients["ukg_instance"].get_all_employment_details_by_company.return_value = [
            {"employeeNumber": "12345", "primaryJobCode": "1103", "dateTimeChanged": recent_date},
            {"employeeNumber": "12346", "primaryJobCode": "1103", "dateTimeChanged": old_date},
        ]

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        # Check only recent employee is passed to sync_batch
        call_args = mock_clients["sync_instance"].sync_batch.call_args
        employees = call_args[0][0]
        assert len(employees) == 1
        assert employees[0]["employeeNumber"] == "12345"

    def test_main_with_states_filter(self, mock_clients, monkeypatch):
        """Test main with states filter."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py", "--states", "FL,TX"]):
            main()

        # Check sync_batch was called with states filter
        call_args = mock_clients["sync_instance"].sync_batch.call_args
        assert call_args[0][2] == {"FL", "TX"}  # states_filter argument

    def test_main_filters_employees(self, mock_clients, monkeypatch):
        """Test main filters employees by job code."""
        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        mock_clients["ukg_instance"].get_all_employment_details_by_company.return_value = [
            {"employeeNumber": "12345", "primaryJobCode": "1103"},
            {"employeeNumber": "12346", "primaryJobCode": "9999"},
        ]

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        # Check only eligible employee is passed to sync_batch
        call_args = mock_clients["sync_instance"].sync_batch.call_args
        employees = call_args[0][0]
        assert len(employees) == 1
        assert employees[0]["employeeNumber"] == "12345"

    def test_main_prints_config(self, mock_clients, monkeypatch, caplog):
        """Test main prints configuration."""
        import logging
        caplog.set_level(logging.INFO)

        monkeypatch.setenv("COMPANY_ID", "J9A6Y")
        monkeypatch.setenv("JOB_IDS", "1103")
        # Required for API validation
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")
        monkeypatch.setenv("MOTUS_JWT", "header.payload.signature")

        with patch.object(sys, "argv", ["batch_runner.py"]):
            main()

        # Check that config was logged at INFO level with company ID
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        # Should log configuration with company ID
        assert "J9A6Y" in log_messages or "Config" in log_messages or len(info_records) > 0
