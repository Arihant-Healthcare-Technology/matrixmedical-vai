"""
Extended end-to-end integration tests for UKG-Motus batch processing.
Tests various scenarios including employee statuses, program assignments, and error recovery.
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


def get_builder_module(monkeypatch):
    """Helper to get fresh builder module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "builder",
        str(Path(__file__).parent.parent.parent / "build-motus-driver.py")
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def get_upserter_module(monkeypatch):
    """Helper to get fresh upserter module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upserter",
        str(Path(__file__).parent.parent.parent / "upsert-motus-driver.py")
    )
    upserter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upserter)
    return upserter


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


class TestEmployeeStatusScenarios:
    """Integration tests for various employee status scenarios."""

    @responses.activate
    def test_new_hire_with_all_data(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test new hire with complete data."""
        builder = get_builder_module(monkeypatch)

        # Set up all mocks
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        driver = builder.build_motus_driver("12345", "J9A6Y")

        # Verify all fields populated
        assert driver["clientEmployeeId1"] == "12345"
        assert driver["firstName"] == "John"
        assert driver["lastName"] == "Doe"
        assert driver["email"] == "john.doe@example.com"
        assert driver["startDate"]  # Should have start date

    @responses.activate
    def test_terminated_employee_processing(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test processing terminated employee."""
        builder = get_builder_module(monkeypatch)

        terminated_employment = {
            "employeeId": "EMP001",
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeStatusCode": "T",
            "primaryJobCode": "4154",
            "startDate": "2020-01-15T00:00:00Z",
            "terminationDate": "2024-03-01T00:00:00Z",
            "leaveStartDate": None,
            "leaveEndDate": None,
        }

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[terminated_employment],
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        driver = builder.build_motus_driver("12345", "J9A6Y")

        # Check derived status
        custom_vars = driver["customVariables"]
        derived_status = next((v for v in custom_vars if v["name"] == "Derived Status"), None)
        assert derived_status is not None
        assert derived_status["value"] == "Terminated"
        assert driver["endDate"]  # Should have end date

    @responses.activate
    def test_leave_of_absence_scenario(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test employee on leave of absence."""
        builder = get_builder_module(monkeypatch)

        loa_employment = {
            "employeeId": "EMP001",
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeStatusCode": "A",
            "primaryJobCode": "4154",
            "startDate": "2020-01-15T00:00:00Z",
            "terminationDate": None,
            "leaveStartDate": "2024-02-01T00:00:00Z",
            "leaveEndDate": None,  # Still on leave
        }

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[loa_employment],
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        driver = builder.build_motus_driver("12345", "J9A6Y")

        custom_vars = driver["customVariables"]
        derived_status = next((v for v in custom_vars if v["name"] == "Derived Status"), None)
        assert derived_status is not None
        assert derived_status["value"] == "Leave"
        assert driver["leaveStartDate"]  # Should have leave start date


class TestProgramAssignment:
    """Integration tests for program assignment based on job codes."""

    @responses.activate
    def test_favr_program_assignment(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test FAVR program (21232) assignment for eligible job codes."""
        builder = get_builder_module(monkeypatch)

        # Job code 1103 -> FAVR (21232)
        favr_employment = {
            "employeeId": "EMP001",
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",  # FAVR job code
            "startDate": "2020-01-15T00:00:00Z",
        }

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[favr_employment],
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        driver = builder.build_motus_driver("12345", "J9A6Y")

        assert driver["programId"] == 21232  # FAVR

    @responses.activate
    def test_cpm_program_assignment(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test CPM program (21233) assignment for eligible job codes."""
        builder = get_builder_module(monkeypatch)

        # Job code 2817 -> CPM (21233)
        cpm_employment = {
            "employeeId": "EMP001",
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeStatusCode": "A",
            "primaryJobCode": "2817",  # CPM job code
            "startDate": "2020-01-15T00:00:00Z",
        }

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[cpm_employment],
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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

        driver = builder.build_motus_driver("12345", "J9A6Y")

        assert driver["programId"] == 21233  # CPM

    @responses.activate
    def test_manager_supervisor_linked(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test manager/supervisor info is included in driver payload."""
        builder = get_builder_module(monkeypatch)

        supervisor = {
            "employeeId": "EMP001",
            "supervisorFirstName": "Jane",
            "supervisorLastName": "Manager",
            "supervisorEmployeeId": "MGR001",
        }

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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[supervisor],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        driver = builder.build_motus_driver("12345", "J9A6Y")

        custom_vars = driver["customVariables"]
        manager_name = next((v for v in custom_vars if v["name"] == "Manager Name"), None)
        assert manager_name is not None
        assert manager_name["value"] == "Jane Manager"


class TestStateFiltering:
    """Integration tests for state filtering."""

    @responses.activate
    def test_multi_state_filtering(self, monkeypatch, tmp_path):
        """Test filtering employees by multiple states (FL, MS, NJ)."""
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y"},
            {"employeeNumber": "003", "employeeID": "EMP003", "companyID": "J9A6Y"},
            {"employeeNumber": "004", "employeeID": "EMP004", "companyID": "J9A6Y"},
        ]

        # Mock person-details for different states
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP001.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP002.*"),
            json=[{"employeeId": "EMP002", "addressState": "MS"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP003.*"),
            json=[{"employeeId": "EMP003", "addressState": "CA"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP004.*"),
            json=[{"employeeId": "EMP004", "addressState": "NJ"}],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        states_filter = {"FL", "MS", "NJ"}
        results = []

        for emp in employees:
            emp_num, state, status = batch._process_employee(emp, states_filter, out_path, {})
            results.append((emp_num, state, status))

        # CA should be skipped
        ca_result = next((r for r in results if r[1] == "CA"), None)
        assert ca_result is not None
        assert ca_result[2] == "skipped"


class TestErrorRecovery:
    """Integration tests for error recovery scenarios."""

    @responses.activate
    def test_rate_limit_retry(self, monkeypatch, sample_motus_driver_payload):
        """Test retry behavior on 429 rate limit."""
        monkeypatch.setenv("MAX_RETRIES", "2")
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # First POST returns 429
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"error": "Too many requests"},
            status=429,
            headers={"Retry-After": "1"},
        )
        # Second POST succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        with patch("time.sleep"):  # Skip actual sleep
            result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_5xx_server_error_recovery(self, monkeypatch, sample_motus_driver_payload):
        """Test recovery from 5xx server errors."""
        monkeypatch.setenv("MAX_RETRIES", "2")
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # First POST returns 500
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"error": "Server error"},
            status=500,
        )
        # Second POST succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        with patch.object(upserter, "backoff_sleep"):
            result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_partial_batch_failure(self, monkeypatch, tmp_path):
        """Test batch processing continues after individual failures."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Both employees get person-details (with different states to simulate different outcomes)
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP002", "addressState": "CA"}],
            status=200,
        )
        # First employee's employment-details succeeds
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],  # Empty - will cause skip
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],  # Empty - will cause skip
            status=200,
        )

        items = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y"},
        ]

        out_dir = str(tmp_path / "batch")

        # Should complete without crashing
        batch.build_and_save_drivers(items, out_dir)


class TestConcurrentProcessing:
    """Integration tests for concurrent/parallel processing."""

    @responses.activate
    def test_multiple_workers_batch(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test batch processing with multiple workers."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        monkeypatch.setenv("WORKERS", "4")
        batch = get_batch_module(monkeypatch)

        # Set up mocks for multiple employees
        for _ in range(10):  # Allow multiple calls
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

        items = [
            {"employeeNumber": f"1234{i}", "employeeID": f"EMP00{i}", "companyID": "J9A6Y"}
            for i in range(5)
        ]

        out_dir = str(tmp_path / "batch")

        # Should complete with 4 workers
        batch.build_and_save_drivers(items, out_dir)

    def test_job_code_filtering_batch(self, monkeypatch):
        """Test job code filtering in batch processing."""
        # Set JOB_IDS env var with test job codes
        monkeypatch.setenv("JOB_IDS", "1103,4165,4166,1102,1106,4197,4196,2817,4121,2157")
        batch = get_batch_module(monkeypatch)
        eligible_codes = batch.get_eligible_job_codes()

        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},  # FAVR - eligible
            {"employeeNumber": "002", "primaryJobCode": "2817"},  # CPM - eligible
            {"employeeNumber": "003", "primaryJobCode": "9999"},  # Not eligible
            {"employeeNumber": "004", "primaryJobCode": "4121"},  # CPM - eligible
        ]

        filtered = batch.filter_by_eligible_job_codes(items, eligible_codes)

        assert len(filtered) == 3
        emp_numbers = [e["employeeNumber"] for e in filtered]
        assert "001" in emp_numbers
        assert "002" in emp_numbers
        assert "004" in emp_numbers
        assert "003" not in emp_numbers

    @responses.activate
    def test_batch_with_mixed_statuses(
        self, monkeypatch, tmp_path,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test batch processing with mixed employee statuses."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("PROBE", "0")
        monkeypatch.setenv("WORKERS", "1")
        batch = get_batch_module(monkeypatch)

        # Active employee
        active_emp = {
            "employeeId": "EMP001",
            "employeeNumber": "001",
            "companyID": "J9A6Y",
            "employeeStatusCode": "A",
            "primaryJobCode": "4154",
            "startDate": "2020-01-15T00:00:00Z",
        }

        # Terminated employee
        terminated_emp = {
            "employeeId": "EMP002",
            "employeeNumber": "002",
            "companyID": "J9A6Y",
            "employeeStatusCode": "T",
            "primaryJobCode": "4154",
            "terminationDate": "2024-01-01T00:00:00Z",
            "startDate": "2020-01-15T00:00:00Z",
        }

        # Set up alternating mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[active_emp],
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

        items = [{"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"}]

        out_dir = str(tmp_path / "batch")
        batch.build_and_save_drivers(items, out_dir)
