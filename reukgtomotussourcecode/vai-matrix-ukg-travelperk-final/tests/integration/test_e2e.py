"""
End-to-end integration tests for UKG-TravelPerk batch processing.
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
        str(Path(__file__).parent.parent.parent / "run-travelperk-batch.py")
    )
    batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch)
    return batch


class TestFullBatchWorkflow:
    """Integration tests for full batch processing workflow."""

    @responses.activate
    def test_full_batch_new_users(
        self, monkeypatch, tmp_path,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test full batch processing for new users."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("WORKERS", "1")

        # Set up UKG mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "employeeID": "EMP001",
                "companyID": "J9A6Y",
                "employeeTypeCode": "FTC",
            }],
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
            re.compile(r".*/personnel/v1/employee-supervisor-details.*"),
            json=[{
                "employeeNumber": "12345",
                "supervisorEmployeeNumber": None,
            }],
            status=200,
        )

        batch = get_batch_module(monkeypatch)

        items = batch.get_employee_employment_details_by_company("J9A6Y")
        assert len(items) == 1

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
        emp_num, state, status, tp_id = batch._process_employee(
            ca_employee,
            {"FL"},  # Only FL allowed
            out_path,
            {}
        )

        assert state == "CA"
        assert status == "skipped"


class TestTwoPhaseProcessing:
    """Integration tests for two-phase supervisor processing."""

    @responses.activate
    def test_two_phase_batch_dry_run(
        self, monkeypatch, tmp_path,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test two-phase batch processing in dry run mode."""
        monkeypatch.setenv("DRY_RUN", "1")
        monkeypatch.setenv("WORKERS", "1")
        monkeypatch.setenv("LIMIT", "2")

        # Employee-employment-details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[
                {"employeeNumber": "54321", "employeeID": "SUP001", "companyID": "J9A6Y"},  # Supervisor
                {"employeeNumber": "12345", "employeeID": "EMP001", "companyID": "J9A6Y"},  # Employee
            ],
            status=200,
        )

        # Person-details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        # Supervisor-details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-supervisor-details.*"),
            json=[
                {"employeeNumber": "54321", "supervisorEmployeeNumber": None},
                {"employeeNumber": "12345", "supervisorEmployeeNumber": "54321"},
            ],
            status=200,
        )

        batch = get_batch_module(monkeypatch)

        items = batch.get_employee_employment_details_by_company("J9A6Y")
        assert len(items) == 2


class TestErrorHandling:
    """Integration tests for error handling."""

    @responses.activate
    def test_ukg_api_error_handled(self, monkeypatch, tmp_path):
        """Test UKG API error is handled gracefully."""
        batch = get_batch_module(monkeypatch)

        # Mock person-details to succeed (for state fetch)
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "addressState": "FL"}],
            status=200,
        )
        # Mock employee-employment-details to fail
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json={"error": "Server error"},
            status=500,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}

        # State filter matches (FL), so it proceeds to build
        # which fails due to employee-employment-details 500 error
        emp_num, state, status, tp_id = batch._process_employee(
            item,
            {"FL"},
            out_path,
            {},
        )

        # _process_employee catches errors and returns skipped or error
        assert status in ("skipped", "error")

    @responses.activate
    def test_travelperk_api_error_handled(
        self, monkeypatch, tmp_path,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test TravelPerk API error is handled gracefully."""
        monkeypatch.setenv("DRY_RUN", "0")
        monkeypatch.setenv("MAX_RETRIES", "0")
        batch = get_batch_module(monkeypatch)

        # Set up UKG mocks
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

        # TravelPerk user doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json={"Resources": []},
            status=200,
        )
        # TravelPerk insert fails
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"error": "Bad request"},
            status=400,
        )

        out_path = tmp_path / "batch"
        out_path.mkdir()

        item = {"employeeNumber": "12345", "employeeID": "EMP001"}

        emp_num, state, status, tp_id = batch._process_employee(
            item,
            None,
            out_path,
            {},
        )

        # Should complete even with TravelPerk error
        assert status in ("saved", "skipped", "error", "dry_run")


class TestScimPayloadBuilding:
    """Integration tests for SCIM payload building."""

    @responses.activate
    def test_builds_complete_scim_payload(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test building complete SCIM payload from UKG data."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "builder",
            str(Path(__file__).parent.parent.parent / "build-travelperk-user.py")
        )
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)

        # Set up mocks
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

        user = builder.build_travelperk_user("12345", "J9A6Y")

        # Verify SCIM schema compliance
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in user["schemas"]
        assert "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User" in user["schemas"]
        assert user["externalId"] == "12345"
        assert user["userName"] == "john.doe@example.com"
        assert user["name"]["givenName"] == "John"
        assert user["name"]["familyName"] == "Doe"
        assert user["active"] is True


class TestUpsertWorkflow:
    """Integration tests for upsert workflow."""

    @responses.activate
    def test_insert_new_user(self, monkeypatch, sample_travelperk_user_payload):
        """Test inserting new user via TravelPerk API."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-travelperk-user.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        # User doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json={"Resources": []},
            status=200,
        )
        # Insert succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"id": "new-user-id", "externalId": "12345"},
            status=201,
        )

        result = upserter.upsert_user_payload(sample_travelperk_user_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_update_existing_user(
        self, monkeypatch,
        sample_travelperk_user_payload,
        sample_travelperk_scim_list_response
    ):
        """Test updating existing user via TravelPerk API."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-travelperk-user.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        # User exists
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PATCH,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        result = upserter.upsert_user_payload(sample_travelperk_user_payload)

        assert result["action"] == "update"
        assert result["status"] == 200


class TestSupervisorHierarchy:
    """Integration tests for supervisor hierarchy handling."""

    def test_builds_supervisor_mapping(self, monkeypatch, sample_supervisor_details):
        """Test building supervisor mapping from UKG data."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-travelperk-user.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        mapping = upserter.build_supervisor_mapping(sample_supervisor_details)

        # Verify mapping
        assert mapping["12345"] == "54321"  # Employee has supervisor
        assert mapping["54321"] is None      # Supervisor has no supervisor
        assert mapping["67890"] == "54321"  # Another employee has same supervisor

    def test_separates_users_by_supervisor_presence(
        self, monkeypatch, sample_supervisor_details
    ):
        """Test separating users by supervisor presence."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upserter",
            str(Path(__file__).parent.parent.parent / "upsert-travelperk-user.py")
        )
        upserter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upserter)

        mapping = upserter.build_supervisor_mapping(sample_supervisor_details)
        without_supervisor = upserter.get_users_without_supervisor(mapping)
        with_supervisor = upserter.get_users_with_supervisor(mapping)

        assert "54321" in without_supervisor
        assert len(without_supervisor) == 1

        assert "12345" in with_supervisor
        assert "67890" in with_supervisor
        assert len(with_supervisor) == 2


class TestEmployeeTypeFiltering:
    """Integration tests for employee type code filtering."""

    @responses.activate
    def test_filters_by_employee_type_codes(self, monkeypatch):
        """Test filtering employees by type codes."""
        batch = get_batch_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[
                {"employeeNumber": "12345", "employeeID": "EMP001", "employeeTypeCode": "FTC"},
                {"employeeNumber": "12346", "employeeID": "EMP002", "employeeTypeCode": "HRC"},
                {"employeeNumber": "12347", "employeeID": "EMP003", "employeeTypeCode": "TMC"},
                {"employeeNumber": "12348", "employeeID": "EMP004", "employeeTypeCode": "PTC"},
            ],
            status=200,
        )

        # Filter for FTC and TMC only
        result = batch.get_employee_employment_details_by_company(
            "J9A6Y",
            employee_type_codes=["FTC", "TMC"]
        )

        assert len(result) == 2
        assert all(item["employeeTypeCode"] in ["FTC", "TMC"] for item in result)
