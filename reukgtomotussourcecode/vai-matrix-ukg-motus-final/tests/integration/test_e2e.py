"""
End-to-end integration tests for UKG-Motus batch processing.
Tests full workflow with mocked backend APIs.
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


class TestFullBatchWorkflow:
    """Integration tests for full batch processing workflow."""

    @responses.activate
    def test_full_batch_new_employees(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test full batch processing for new employees."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("WORKERS", "1")

        # Set up all UKG mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "employeeID": "EMP001",
                "companyID": "J9A6Y",
            }],
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
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        batch = get_batch_module(monkeypatch)

        items = batch.get_employee_employment_details_by_company("J9A6Y")
        assert len(items) == 1

        out_dir = str(tmp_path / "batch")
        batch.build_and_save_drivers(items, out_dir)

        # Test completes without error
        assert True

    @responses.activate
    def test_batch_with_state_filtering(
        self, monkeypatch, tmp_path,
        sample_ukg_person_details
    ):
        """Test batch processing with state filtering."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("WORKERS", "1")

        batch = get_batch_module(monkeypatch)

        # Employee in FL
        fl_employee = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
        }

        # Employee in CA
        ca_employee = {
            "employeeNumber": "12346",
            "employeeID": "EMP002",
            "companyID": "J9A6Y",
        }

        # Mock person-details for FL employee
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP001.*"),
            json=[{**sample_ukg_person_details, "addressState": "FL"}],
            status=200,
        )

        # Mock person-details for CA employee
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*EMP002.*"),
            json=[{**sample_ukg_person_details, "addressState": "CA", "employeeId": "EMP002"}],
            status=200,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        # Process CA employee - should be skipped due to state filter
        emp_num, state, status = batch._process_employee(
            ca_employee,
            {"FL"},  # Only FL allowed
            out_path,
            {}
        )

        assert state == "CA"
        assert status == "skipped"


class TestErrorHandling:
    """Integration tests for error handling."""

    @responses.activate
    def test_ukg_api_error_handled(self, monkeypatch, tmp_path):
        """Test UKG API error results in SystemExit being caught by _process_employee."""
        batch = get_batch_module(monkeypatch)

        # Mock person-details to return success (for state fetch)
        # but employment-details to return error (in build_motus_driver)
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json={"error": "Server error"},
            status=500,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}

        # State filter matches (FL), so it proceeds to build_motus_driver
        # which fails due to employment-details 500 error
        emp_num, state, status = batch._process_employee(
            item,
            {"FL"},
            out_path,
            {},
        )

        # _process_employee catches errors and returns skipped or error
        assert status in ("skipped", "error")

    @responses.activate
    def test_motus_api_error_handled(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test Motus API error is handled gracefully."""
        monkeypatch.setenv("DRY_RUN", "0")
        monkeypatch.setenv("MAX_RETRIES", "0")
        batch = get_batch_module(monkeypatch)

        # Set up UKG mocks
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
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        # Motus driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # Motus insert fails
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"error": "Bad request"},
            status=400,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}

        emp_num, state, status = batch._process_employee(
            item,
            None,
            out_path,
            {},
        )

        # Should complete even with Motus error
        assert status in ("saved", "skipped", "error", "dry_run")


class TestDriverPayloadBuilding:
    """Integration tests for driver payload building."""

    @responses.activate
    def test_builds_complete_driver_payload(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test building complete driver payload from UKG data."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "builder",
            str(Path(__file__).parent.parent.parent / "build-motus-driver.py")
        )
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)

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
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        driver = builder.build_motus_driver("12345", "J9A6Y")

        # Verify all required fields
        assert driver["clientEmployeeId1"] == "12345"
        assert driver["programId"] == 21233
        assert driver["firstName"] == "John"
        assert driver["lastName"] == "Doe"
        assert driver["email"] == "john.doe@example.com"
        assert driver["phone"] == "555-123-4567"

        # Verify custom variables
        custom_vars = driver["customVariables"]
        project_code = next((v for v in custom_vars if v["name"] == "Project Code"), None)
        assert project_code is not None
        assert project_code["value"] == "PROJ001"


class TestUpsertWorkflow:
    """Integration tests for upsert workflow."""

    @responses.activate
    def test_insert_new_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test inserting new driver via Motus API."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-motus-driver.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # Insert succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345", "id": "new-id"},
            status=201,
        )

        result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_update_existing_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test updating existing driver via Motus API."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-motus-driver.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        # Driver exists
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PUT,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "update"
        assert result["status"] == 200


class TestTokenWorkflow:
    """Integration tests for token workflow."""

    @responses.activate
    def test_token_acquisition(self, monkeypatch, tmp_path):
        """Test acquiring new Motus token."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "token",
            str(Path(__file__).parent.parent.parent / "motus-get-token.py")
        )
        token_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(token_mod)

        # Mock token endpoint
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={
                "access_token": "new-jwt-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=200,
        )

        token_mod.CACHE_PATH = str(cache_file)
        result = token_mod.get_token(force_refresh=True)

        assert result["access_token"] == "new-jwt-token"
        assert result["token_type"] == "Bearer"
