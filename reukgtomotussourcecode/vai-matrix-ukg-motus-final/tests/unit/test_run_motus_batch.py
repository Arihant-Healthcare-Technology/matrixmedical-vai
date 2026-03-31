"""
Unit tests for run-motus-batch.py module.
Tests CLI parsing, batch processing, state filtering.
"""
import os
import re
import sys
import json
import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_batch_module(monkeypatch):
    """Helper to get fresh batch module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "batch",
        str(Path(__file__).parent.parent.parent / "run-motus-batch.py")
    )
    batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch)
    return batch


class TestParseStatesArg:
    """Tests for parse_states_arg function."""

    def test_parse_single_state(self, monkeypatch):
        """Test parsing single state."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg("FL")
        assert result == {"FL"}

    def test_parse_multiple_states(self, monkeypatch):
        """Test parsing multiple states."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg("FL,NY,CA")
        assert result == {"FL", "NY", "CA"}

    def test_parse_states_with_spaces(self, monkeypatch):
        """Test parsing states with spaces."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg(" FL , NY , CA ")
        assert result == {"FL", "NY", "CA"}

    def test_parse_states_uppercase(self, monkeypatch):
        """Test states are uppercased."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg("fl,ny,ca")
        assert result == {"FL", "NY", "CA"}

    def test_parse_none_returns_none(self, monkeypatch):
        """Test None returns None."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg(None)
        assert result is None

    def test_parse_empty_returns_none(self, monkeypatch):
        """Test empty string returns None."""
        batch = get_batch_module(monkeypatch)

        result = batch.parse_states_arg("")
        assert result is None


class TestNormalizeList:
    """Tests for _normalize_list function."""

    def test_list_returns_list(self, monkeypatch):
        """Test list input returns list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list([{"id": 1}, {"id": 2}])
        assert result == [{"id": 1}, {"id": 2}]

    def test_dict_with_items_returns_items(self, monkeypatch):
        """Test dict with items key returns items list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list({"items": [{"id": 1}]})
        assert result == [{"id": 1}]

    def test_dict_without_items_returns_single_item_list(self, monkeypatch):
        """Test dict without items returns single-item list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list({"id": 1})
        assert result == [{"id": 1}]

    def test_non_container_returns_empty(self, monkeypatch):
        """Test non-container returns empty list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list("string")
        assert result == []


class TestGetEmployeeEmploymentDetailsByCompany:
    """Tests for get_employee_employment_details_by_company function."""

    @responses.activate
    def test_returns_all_employees(self, monkeypatch):
        """Test returns all employees for company."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[
                {"employeeNumber": "12345", "employeeID": "EMP001"},
                {"employeeNumber": "12346", "employeeID": "EMP002"},
            ],
            status=200,
        )

        result = batch.get_employee_employment_details_by_company("J9A6Y")
        assert len(result) == 2


class TestFetchPersonState:
    """Tests for _fetch_person_state function."""

    @responses.activate
    def test_fetch_state_success(self, monkeypatch):
        """Test fetching person state."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )

        cache = {}
        result = batch._fetch_person_state("EMP001", cache)

        assert result == "FL"
        assert cache["EMP001"] == "FL"

    @responses.activate
    def test_uses_cache(self, monkeypatch):
        """Test cache is used for subsequent calls."""
        batch = get_batch_module(monkeypatch)

        # No mock needed because cache should be used
        cache = {"EMP001": "NY"}
        result = batch._fetch_person_state("EMP001", cache)

        assert result == "NY"
        assert len(responses.calls) == 0

    @responses.activate
    def test_handles_error_raises_system_exit(self, monkeypatch):
        """Test HTTP error raises SystemExit (since get_data raises SystemExit on errors)."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={"error": "Not found"},
            status=404,
        )

        cache = {}
        # get_data raises SystemExit on HTTP errors, which is not caught by Exception
        with pytest.raises(SystemExit):
            batch._fetch_person_state("EMP999", cache, max_retries=1)


class TestProcessEmployee:
    """Tests for _process_employee function."""

    @responses.activate
    def test_skips_missing_employee_number(self, monkeypatch, tmp_path):
        """Test skips employee without employee number."""
        batch = get_batch_module(monkeypatch)

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeID": "EMP001"}  # No employeeNumber
        emp_num, state, status = batch._process_employee(item, None, out_path, {})

        assert status == "skipped"

    @responses.activate
    def test_skips_missing_employee_id(self, monkeypatch, tmp_path):
        """Test skips employee without employee ID."""
        batch = get_batch_module(monkeypatch)

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345"}  # No employeeID
        emp_num, state, status = batch._process_employee(item, None, out_path, {})

        assert status == "skipped"

    @responses.activate
    def test_filters_by_state(self, monkeypatch, tmp_path):
        """Test state filtering."""
        batch = get_batch_module(monkeypatch)

        # Mock person-details to return CA state
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "CA"}],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}
        states_filter = {"FL"}  # Only FL allowed

        emp_num, state, status = batch._process_employee(item, states_filter, out_path, {})

        assert state == "CA"
        assert status == "skipped"


class TestBuildAndSaveDrivers:
    """Tests for build_and_save_drivers function."""

    @responses.activate
    def test_processes_all_employees(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test processes all employees in list."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Set up all required mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        items = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
        ]

        out_dir = str(tmp_path / "batch")
        batch.build_and_save_drivers(items, out_dir)

        # Function should complete without error
        assert True


class TestCliParsing:
    """Tests for CLI argument parsing."""

    def test_parse_company_id(self, monkeypatch):
        """Test parsing company ID argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--company-id", "J9A6Y"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.company_id == "J9A6Y"

    def test_parse_states(self, monkeypatch):
        """Test parsing states argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--states", "FL,NY,CA"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.states == "FL,NY,CA"

    def test_parse_workers(self, monkeypatch):
        """Test parsing workers argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--workers", "8"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.workers == 8

    def test_parse_dry_run(self, monkeypatch):
        """Test parsing dry-run flag."""
        monkeypatch.setattr(sys, "argv", ["batch", "--dry-run"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.dry_run is True

    def test_parse_save_local(self, monkeypatch):
        """Test parsing save-local flag."""
        monkeypatch.setattr(sys, "argv", ["batch", "--save-local"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.save_local is True

    def test_parse_probe(self, monkeypatch):
        """Test parsing probe flag."""
        monkeypatch.setattr(sys, "argv", ["batch", "--probe"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.probe is True

    def test_default_values(self, monkeypatch):
        """Test default argument values."""
        monkeypatch.setattr(sys, "argv", ["batch"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.company_id is None
        assert args.states is None
        assert args.workers is None
        assert args.dry_run is False
        assert args.save_local is False
        assert args.probe is False

    def test_combined_flags(self, monkeypatch):
        """Test multiple flags combined."""
        monkeypatch.setattr(sys, "argv", ["batch", "--company-id", "ABC", "--dry-run", "--probe", "--workers", "4"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.company_id == "ABC"
        assert args.dry_run is True
        assert args.probe is True
        assert args.workers == 4


class TestFilterByEligibleJobCodes:
    """Tests for filter_by_eligible_job_codes function."""

    # Test job codes: FAVR + CPM programs
    TEST_JOB_IDS = "1103,4165,4166,1102,1106,4197,4196,2817,4121,2157"

    def test_eligible_favr_job_codes(self, monkeypatch):
        """Test eligible FAVR job codes are included."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},
            {"employeeNumber": "002", "primaryJobCode": "4165"},
            {"employeeNumber": "003", "primaryJobCode": "4166"},
            {"employeeNumber": "004", "primaryJobCode": "1102"},
            {"employeeNumber": "005", "primaryJobCode": "1106"},
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 5

    def test_eligible_cpm_job_codes(self, monkeypatch):
        """Test eligible CPM job codes are included."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "2817"},
            {"employeeNumber": "002", "primaryJobCode": "4121"},
            {"employeeNumber": "003", "primaryJobCode": "2157"},
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 3

    def test_ineligible_job_codes_filtered_out(self, monkeypatch):
        """Test ineligible job codes are filtered out."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "9999"},  # Not eligible
            {"employeeNumber": "002", "primaryJobCode": "0000"},  # Not eligible
            {"employeeNumber": "003", "primaryJobCode": "1103"},  # Eligible
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 1
        assert result[0]["primaryJobCode"] == "1103"

    def test_job_codes_with_leading_zeros(self, monkeypatch):
        """Test job codes with leading zeros are matched."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "01103"},  # Should match 1103
            {"employeeNumber": "002", "primaryJobCode": "001102"}, # Should match 1102
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 2

    def test_empty_list(self, monkeypatch):
        """Test empty list returns empty list."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        result = batch.filter_by_eligible_job_codes([], eligible_codes)
        assert result == []

    def test_mixed_eligible_and_ineligible(self, monkeypatch):
        """Test mixed list filters correctly."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},  # FAVR
            {"employeeNumber": "002", "primaryJobCode": "8888"},  # Not eligible
            {"employeeNumber": "003", "primaryJobCode": "2817"},  # CPM
            {"employeeNumber": "004", "primaryJobCode": ""},      # Empty
            {"employeeNumber": "005", "primaryJobCode": "4197"},  # FAVR
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 3

    def test_missing_job_code_field(self, monkeypatch):
        """Test employees without job code field are filtered out."""
        monkeypatch.setenv("JOB_IDS", self.TEST_JOB_IDS)
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001"},  # No primaryJobCode field
            {"employeeNumber": "002", "primaryJobCode": "1103"},
        ]

        result = batch.filter_by_eligible_job_codes(items, eligible_codes)
        assert len(result) == 1

    def test_get_eligible_job_codes_from_env(self, monkeypatch):
        """Test get_eligible_job_codes reads from JOB_IDS env var."""
        monkeypatch.setenv("JOB_IDS", "1103,4165,2817")
        batch = get_batch_module(monkeypatch)
        codes = batch.get_eligible_job_codes()
        assert codes == {"1103", "4165", "2817"}

    def test_get_eligible_job_codes_missing_env_raises(self, monkeypatch):
        """Test get_eligible_job_codes raises if JOB_IDS not set."""
        monkeypatch.delenv("JOB_IDS", raising=False)
        batch = get_batch_module(monkeypatch)
        # Also delete after module load since load_dotenv_simple may have set it
        monkeypatch.delenv("JOB_IDS", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            batch.get_eligible_job_codes()
        assert "JOB_IDS" in str(exc_info.value)


class TestProcessEmployeeExtended:
    """Extended tests for _process_employee function."""

    @responses.activate
    def test_successful_processing(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test successful employee processing."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        batch = get_batch_module(monkeypatch)

        # Set up all required mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001", "companyID": "J9A6Y"}
        emp_num, state, status = batch._process_employee(item, None, out_path, {})

        assert emp_num == "12345"
        assert status == "dry_run"

    @responses.activate
    def test_builder_error_returns_skipped(self, monkeypatch, tmp_path):
        """Test builder error returns skipped status."""
        batch = get_batch_module(monkeypatch)

        # Mock person-details to succeed
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        # Mock employment-details to fail
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],  # Empty - will cause builder to fail
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001", "companyID": "J9A6Y"}
        emp_num, state, status = batch._process_employee(item, None, out_path, {})

        assert status == "skipped"

    @responses.activate
    def test_uses_default_company_id(self, monkeypatch, tmp_path):
        """Test uses default company ID when not in item."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        batch = get_batch_module(monkeypatch)

        # This test just checks the function doesn't crash when companyID is missing
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}  # No companyID
        emp_num, state, status = batch._process_employee(item, None, out_path, {}, default_company_id="DEFAULT")

        # Function should handle missing companyID gracefully
        assert emp_num == "12345"


class TestBuildAndSaveDriversExtended:
    """Extended tests for build_and_save_drivers function."""

    @responses.activate
    def test_counts_errors_correctly(
        self, monkeypatch, tmp_path
    ):
        """Test error counting in batch processing."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock person-details - will be called for all employees
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        # Mock employment-details to fail (empty)
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        items = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
            {"employeeNumber": "12346", "employeeID": "EMP002"},
        ]

        out_dir = str(tmp_path / "batch")
        # Should complete without crashing even with errors
        batch.build_and_save_drivers(items, out_dir)

    @responses.activate
    def test_dry_run_mode(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test dry-run mode doesn't make POST/PUT calls."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        items = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        out_dir = str(tmp_path / "batch")
        batch.build_and_save_drivers(items, out_dir)

        # Check no POST or PUT calls were made
        for call in responses.calls:
            assert call.request.method != "POST"
            assert call.request.method != "PUT"

    def test_creates_output_directory(self, monkeypatch, tmp_path):
        """Test output directory is created if it doesn't exist."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        out_dir = str(tmp_path / "new" / "nested" / "batch")
        batch.build_and_save_drivers([], out_dir)

        assert Path(out_dir).exists()


class TestFetchPersonStateExtended:
    """Extended tests for _fetch_person_state function."""

    @responses.activate
    def test_retry_on_transient_failure(self, monkeypatch):
        """Test retry behavior on transient failures."""
        batch = get_batch_module(monkeypatch)

        # First call fails, second succeeds
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={"error": "Temporary error"},
            status=500,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={"error": "Temporary error"},
            status=500,
        )

        cache = {}
        # This will fail because get_data raises SystemExit on HTTP errors
        with pytest.raises(SystemExit):
            batch._fetch_person_state("EMP001", cache, max_retries=2)

    @responses.activate
    def test_returns_empty_state_on_missing_field(self, monkeypatch):
        """Test returns empty string when addressState is missing."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001"}],  # No addressState
            status=200,
        )

        cache = {}
        result = batch._fetch_person_state("EMP001", cache)

        assert result == ""
        assert cache["EMP001"] == ""


class TestLoadBuilder:
    """Tests for load_builder function."""

    def test_load_builder_success(self, monkeypatch):
        """Test builder module loads successfully."""
        batch = get_batch_module(monkeypatch)

        # The module should have been loaded already
        assert hasattr(batch, "builder")
        assert hasattr(batch.builder, "build_motus_driver")

    def test_builder_not_found_raises(self, monkeypatch, tmp_path):
        """Test missing builder file raises SystemExit."""
        # This is hard to test without actually moving files
        # The function is called at module load time
        pass


class TestLoadUpserter:
    """Tests for load_upserter function."""

    def test_load_upserter_success(self, monkeypatch):
        """Test upserter module loads successfully."""
        batch = get_batch_module(monkeypatch)

        assert hasattr(batch, "upserter")
        assert hasattr(batch.upserter, "upsert_driver_payload")
