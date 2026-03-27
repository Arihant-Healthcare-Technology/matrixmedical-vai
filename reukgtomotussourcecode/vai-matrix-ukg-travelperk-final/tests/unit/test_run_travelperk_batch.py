"""
Unit tests for run-travelperk-batch.py module.
Tests CLI parsing, batch processing, state filtering, two-phase processing.
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
        str(Path(__file__).parent.parent.parent / "run-travelperk-batch.py")
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
                {"employeeNumber": "12345", "employeeID": "EMP001", "employeeTypeCode": "FTC"},
                {"employeeNumber": "12346", "employeeID": "EMP002", "employeeTypeCode": "HRC"},
            ],
            status=200,
        )

        result = batch.get_employee_employment_details_by_company("J9A6Y")
        assert len(result) == 2

    @responses.activate
    def test_filters_by_employee_type_code(self, monkeypatch):
        """Test filters by employeeTypeCode."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[
                {"employeeNumber": "12345", "employeeID": "EMP001", "employeeTypeCode": "FTC"},
                {"employeeNumber": "12346", "employeeID": "EMP002", "employeeTypeCode": "HRC"},
                {"employeeNumber": "12347", "employeeID": "EMP003", "employeeTypeCode": "TMC"},
            ],
            status=200,
        )

        result = batch.get_employee_employment_details_by_company("J9A6Y", employee_type_codes=["FTC", "TMC"])
        assert len(result) == 2
        assert all(item["employeeTypeCode"] in ["FTC", "TMC"] for item in result)


class TestFetchPersonState:
    """Tests for _fetch_person_state function."""

    @responses.activate
    def test_fetch_state_success(self, monkeypatch, sample_ukg_person_details):
        """Test fetching person state."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        cache = {"EMP001": "NY"}
        result = batch._fetch_person_state("EMP001", cache)

        assert result == "NY"
        assert len(responses.calls) == 0

    @responses.activate
    def test_handles_error_returns_empty(self, monkeypatch):
        """Test error returns empty string after retries."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={"error": "Server error"},
            status=500,
        )

        cache = {}
        result = batch._fetch_person_state("EMP999", cache, max_retries=1)
        assert result == ""


class TestProcessEmployee:
    """Tests for _process_employee function."""

    @responses.activate
    def test_skips_missing_employee_number(self, monkeypatch, tmp_path):
        """Test skips employee without employee number."""
        batch = get_batch_module(monkeypatch)

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeID": "EMP001"}
        emp_num, state, status, tp_id = batch._process_employee(item, None, out_path, {})

        assert status == "skipped"

    @responses.activate
    def test_skips_missing_employee_id(self, monkeypatch, tmp_path):
        """Test skips employee without employee ID."""
        batch = get_batch_module(monkeypatch)

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345"}
        emp_num, state, status, tp_id = batch._process_employee(item, None, out_path, {})

        assert status == "skipped"

    @responses.activate
    def test_filters_by_state(self, monkeypatch, tmp_path, sample_ukg_person_details):
        """Test state filtering."""
        batch = get_batch_module(monkeypatch)

        # Mock person-details to return CA state
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{**sample_ukg_person_details, "addressState": "CA"}],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}
        states_filter = {"FL"}  # Only FL allowed

        emp_num, state, status, tp_id = batch._process_employee(item, states_filter, out_path, {})

        assert state == "CA"
        assert status == "skipped"

    @responses.activate
    def test_processes_employee_with_matching_state_returns_error_without_company_id(
        self, monkeypatch, tmp_path,
        sample_ukg_person_details
    ):
        """Test processes employee with matching state returns error when company_id missing.

        Note: The current source code has a bug where _process_employee calls
        build_travelperk_user(emp_number) without the required company_id parameter.
        This test documents the current behavior.
        """
        monkeypatch.setenv("DRY_RUN", "1")
        batch = get_batch_module(monkeypatch)

        # Mock person-details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}
        states_filter = {"FL"}

        emp_num, state, status, tp_id = batch._process_employee(
            item, states_filter, out_path, {}, dry_run=True
        )

        assert state == "FL"
        # Current behavior returns error because build_travelperk_user needs company_id
        assert status == "error"


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

    def test_parse_limit(self, monkeypatch):
        """Test parsing limit argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--limit", "10"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.limit == 10

    def test_parse_insert_supervisor(self, monkeypatch):
        """Test parsing insert-supervisor argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--insert-supervisor", "004295,009299"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.insert_supervisor == "004295,009299"

    def test_parse_employee_type_codes(self, monkeypatch):
        """Test parsing employee-type-codes argument."""
        monkeypatch.setattr(sys, "argv", ["batch", "--employee-type-codes", "FTC,HRC,TMC"])
        batch = get_batch_module(monkeypatch)

        args = batch.parse_cli()
        assert args.employee_type_codes == "FTC,HRC,TMC"


class TestModuleLoading:
    """Tests for module loading functions."""

    def test_load_builder(self, monkeypatch):
        """Test load_builder returns module."""
        batch = get_batch_module(monkeypatch)
        builder = batch.load_builder()
        assert hasattr(builder, "build_travelperk_user")

    def test_load_upserter(self, monkeypatch):
        """Test load_upserter returns module."""
        batch = get_batch_module(monkeypatch)
        upserter = batch.load_upserter()
        assert hasattr(upserter, "upsert_user_payload")


class TestInsertSupervisorsByEmployeeNumbers:
    """Tests for insert_supervisors_by_employee_numbers function."""

    def test_inserts_single_supervisor(self, monkeypatch, tmp_path):
        """Test inserting a single supervisor."""
        batch = get_batch_module(monkeypatch)

        # Mock the builder and upserter
        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.return_value = {
            "externalId": "12345",
            "userName": "john.doe@example.com",
            "name": {"givenName": "John", "familyName": "Doe"},
        }

        mock_upserter = MagicMock()
        mock_upserter.upsert_user_payload.return_value = {"id": "tp-123"}

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["12345"],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        assert "12345" in result
        assert result["12345"] == "tp-123"

    def test_inserts_multiple_supervisors(self, monkeypatch, tmp_path):
        """Test inserting multiple supervisors."""
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.return_value = {
            "externalId": "12345",
            "userName": "user@example.com",
        }

        mock_upserter = MagicMock()
        mock_upserter.upsert_user_payload.side_effect = [
            {"id": "tp-123"},
            {"id": "tp-456"},
        ]

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["12345", "67890"],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        assert len(result) == 2

    def test_skips_empty_employee_numbers(self, monkeypatch, tmp_path):
        """Test skips empty employee numbers."""
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_upserter = MagicMock()

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["", "  "],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        assert len(result) == 0
        mock_builder.build_travelperk_user.assert_not_called()

    def test_handles_system_exit(self, monkeypatch, tmp_path):
        """Test handles SystemExit from builder."""
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.side_effect = SystemExit("Employee not found")

        mock_upserter = MagicMock()

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["12345"],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        assert len(result) == 0

    def test_handles_exception(self, monkeypatch, tmp_path):
        """Test handles exceptions from builder."""
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.side_effect = Exception("API error")

        mock_upserter = MagicMock()

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["12345"],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        assert len(result) == 0

    def test_dry_run_mode(self, monkeypatch, tmp_path):
        """Test dry-run mode passes flag to upserter."""
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.return_value = {"externalId": "12345"}

        mock_upserter = MagicMock()
        mock_upserter.upsert_user_payload.return_value = {}  # No ID in dry-run

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                result = batch.insert_supervisors_by_employee_numbers(
                    ["12345"],
                    out_dir=str(tmp_path),
                    dry_run=True
                )

        mock_upserter.upsert_user_payload.assert_called_once()
        call_args = mock_upserter.upsert_user_payload.call_args
        assert call_args.kwargs.get('dry_run') is True

    def test_saves_local_file_when_env_set(self, monkeypatch, tmp_path):
        """Test saves local JSON file when SAVE_LOCAL=1."""
        monkeypatch.setenv("SAVE_LOCAL", "1")
        batch = get_batch_module(monkeypatch)

        mock_builder = MagicMock()
        mock_builder.build_travelperk_user.return_value = {"externalId": "12345"}

        mock_upserter = MagicMock()
        mock_upserter.upsert_user_payload.return_value = {"id": "tp-123"}

        with patch.object(batch, 'load_builder', return_value=mock_builder):
            with patch.object(batch, 'load_upserter', return_value=mock_upserter):
                batch.insert_supervisors_by_employee_numbers(
                    ["12345"],
                    out_dir=str(tmp_path),
                    dry_run=False
                )

        # Check file was created
        expected_file = tmp_path / "travelperk_user_12345.json"
        assert expected_file.exists()


class TestBuildAndUpsertUsers:
    """Tests for build_and_upsert_users function."""

    def test_processes_users_without_supervisor(self, monkeypatch, tmp_path):
        """Test processes users without supervisor in phase 1."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value={"12345"})
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        # Mock builder
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "12345"})

        # Mock upsert
        batch.upserter.upsert_user_payload = MagicMock(return_value={"id": "tp-123"})

        items = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=False
        )

        assert "12345" in result

    def test_uses_pre_inserted_mapping(self, monkeypatch, tmp_path):
        """Test uses pre-inserted supervisor mapping."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value=set())
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        pre_inserted = {"00001": "tp-pre-001", "00002": "tp-pre-002"}

        result = batch.build_and_upsert_users(
            [],
            out_dir=str(tmp_path),
            pre_inserted_mapping=pre_inserted
        )

        assert "00001" in result
        assert "00002" in result

    def test_applies_state_filter(self, monkeypatch, tmp_path):
        """Test applies state filter."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value={"12345"})
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        # Mock builder to return CA state
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "CA"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "12345"})

        items = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            states_filter={"FL"}  # Only FL allowed, employee is CA
        )

        # Employee should be skipped due to state filter
        assert "12345" not in result

    def test_applies_limit(self, monkeypatch, tmp_path):
        """Test applies limit to items per phase."""
        monkeypatch.setenv("WORKERS", "1")
        monkeypatch.setenv("LIMIT", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value={"12345", "67890"})
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        # Mock builder
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "12345"})
        batch.upserter.upsert_user_payload = MagicMock(return_value={"id": "tp-123"})

        items = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
            {"employeeNumber": "67890", "employeeID": "EMP002"},
        ]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=False
        )

        # With limit=1, only one employee should be processed
        assert len(result) == 1

    def test_phase2_with_supervisor_lookup(self, monkeypatch, tmp_path):
        """Test phase 2 looks up supervisor in TravelPerk."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={"67890": "12345"})  # 67890's supervisor is 12345
        batch.upserter.get_users_without_supervisor = MagicMock(return_value=set())
        batch.upserter.get_users_with_supervisor = MagicMock(return_value={"67890"})
        batch.upserter.travelperk_get_user_by_external_id = MagicMock(return_value={"id": "tp-supervisor"})

        # Mock builder
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "67890"})

        # Mock upsert
        batch.upserter.upsert_user_payload = MagicMock(return_value={"id": "tp-456"})

        items = [{"employeeNumber": "67890", "employeeID": "EMP002"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=False
        )

        # Should have looked up supervisor
        batch.upserter.travelperk_get_user_by_external_id.assert_called_with("12345")

    def test_phase2_supervisor_not_found(self, monkeypatch, tmp_path):
        """Test phase 2 handles supervisor not found in TravelPerk."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={"67890": "12345"})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value=set())
        batch.upserter.get_users_with_supervisor = MagicMock(return_value={"67890"})
        batch.upserter.travelperk_get_user_by_external_id = MagicMock(return_value=None)

        # Mock builder
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "67890"})
        batch.upserter.upsert_user_payload = MagicMock(return_value={"id": "tp-456"})

        items = [{"employeeNumber": "67890", "employeeID": "EMP002"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=False
        )

        # Should still process the employee even without supervisor
        assert "67890" in result

    def test_handles_errors_in_processing(self, monkeypatch, tmp_path):
        """Test handles errors during employee processing."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value={"12345"})
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        # Mock builder to raise exception
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(side_effect=Exception("Build error"))

        items = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=False
        )

        # Employee should not be in mapping due to error
        assert "12345" not in result

    def test_dry_run_returns_mapping(self, monkeypatch, tmp_path):
        """Test dry-run mode still returns mapping."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Mock upserter functions
        batch.upserter.get_all_supervisor_details = MagicMock(return_value=[])
        batch.upserter.build_supervisor_mapping = MagicMock(return_value={})
        batch.upserter.get_users_without_supervisor = MagicMock(return_value={"12345"})
        batch.upserter.get_users_with_supervisor = MagicMock(return_value=set())

        # Mock builder
        batch.builder.get_person_details = MagicMock(return_value={"addressState": "FL"})
        batch.builder.build_travelperk_user = MagicMock(return_value={"externalId": "12345"})
        batch.upserter.upsert_user_payload = MagicMock(return_value={"id": "tp-dry-123"})

        items = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        result = batch.build_and_upsert_users(
            items,
            out_dir=str(tmp_path),
            dry_run=True
        )

        assert "12345" in result


class TestNormalizeListEdgeCases:
    """Additional tests for _normalize_list edge cases."""

    def test_none_returns_empty(self, monkeypatch):
        """Test None input returns empty list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list(None)
        assert result == []

    def test_dict_with_non_list_items(self, monkeypatch):
        """Test dict with non-list items key returns single-item list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list({"items": "not a list"})
        assert result == [{"items": "not a list"}]

    def test_number_returns_empty(self, monkeypatch):
        """Test number input returns empty list."""
        batch = get_batch_module(monkeypatch)

        result = batch._normalize_list(123)
        assert result == []
