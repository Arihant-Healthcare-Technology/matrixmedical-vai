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
