"""
Shared test fixtures for Motus tests.
Provides mock UKG and Motus API responses, sample data factories.
"""
import os
import sys
import pytest
import responses
import re
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("UKG_BASE_URL", "https://service4.ultipro.com")
    monkeypatch.setenv("UKG_USERNAME", "testuser")
    monkeypatch.setenv("UKG_PASSWORD", "testpass")
    monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
    monkeypatch.setenv("MOTUS_API_BASE", "https://api.motus.com/v1")
    monkeypatch.setenv("MOTUS_JWT", "test-jwt-token")
    monkeypatch.setenv("MOTUS_PROGRAM_ID", "21233")
    monkeypatch.setenv("MOTUS_TOKEN_URL", "https://token.motus.com/tokenservice/token/api")
    monkeypatch.setenv("MOTUS_LOGIN_ID", "test-login")
    monkeypatch.setenv("MOTUS_PASSWORD", "test-password")
    monkeypatch.setenv("DEBUG", "0")
    monkeypatch.setenv("WORKERS", "2")


@pytest.fixture
def sample_ukg_employment_details() -> Dict[str, Any]:
    """Sample UKG employment-details response."""
    return {
        "employeeId": "EMP001",
        "employeeNumber": "12345",
        "companyID": "J9A6Y",
        "employeeStatusCode": "A",
        "primaryJobCode": "4154",
        "jobDescription": "Field Technician",
        "startDate": "2020-01-15T00:00:00Z",
        "terminationDate": None,
        "leaveStartDate": None,
        "leaveEndDate": None,
        "lastHireDate": "2020-01-15T00:00:00Z",
        "fullTimeOrPartTimeCode": "F",
        "employeeTypeCode": "FTC",
        "primaryWorkLocationCode": "LOC001",
        "orgLevel1Code": "DIV1",
        "orgLevel2Code": "DEPT1",
        "orgLevel3Code": "TEAM1",
        "orgLevel4Code": None,
    }


@pytest.fixture
def sample_ukg_employee_employment_details() -> Dict[str, Any]:
    """Sample UKG employee-employment-details response."""
    return {
        "employeeId": "EMP001",
        "employeeID": "EMP001",
        "employeeNumber": "12345",
        "companyID": "J9A6Y",
        "primaryProjectCode": "PROJ001",
        "primaryProjectDescription": "Main Project",
    }


@pytest.fixture
def sample_ukg_person_details() -> Dict[str, Any]:
    """Sample UKG person-details response."""
    return {
        "employeeId": "EMP001",
        "firstName": "John",
        "lastName": "Doe",
        "emailAddress": "john.doe@example.com",
        "homePhone": "5551234567",
        "mobilePhone": "5559876543",
        "addressLine1": "123 Main St",
        "addressLine2": "Apt 4B",
        "addressCity": "Orlando",
        "addressState": "FL",
        "addressCountry": "USA",
        "addressZipCode": "32801",
    }


@pytest.fixture
def sample_motus_driver_payload(
    sample_ukg_person_details,
    sample_ukg_employment_details
) -> Dict[str, Any]:
    """Sample Motus driver payload."""
    return {
        "clientEmployeeId1": "12345",
        "clientEmployeeId2": None,
        "programId": 21233,
        "firstName": "John",
        "lastName": "Doe",
        "address1": "123 Main St",
        "address2": "Apt 4B",
        "city": "Orlando",
        "stateProvince": "FL",
        "country": "USA",
        "postalCode": "32801",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "alternatePhone": "5559876543",
        "startDate": "01/15/2020",
        "endDate": "",
        "leaveStartDate": "",
        "leaveEndDate": "",
        "annualBusinessMiles": 0,
        "commuteDeductionType": None,
        "commuteDeductionCap": None,
        "customVariables": [
            {"name": "Project Code", "value": "PROJ001"},
            {"name": "Project", "value": "Main Project"},
            {"name": "Job Code", "value": "4154"},
            {"name": "Job", "value": "Field Technician"},
            {"name": "Location Code", "value": ""},
            {"name": "Location", "value": ""},
            {"name": "Org Level 1 Code", "value": "DIV1"},
            {"name": "Org Level 2 Code", "value": "DEPT1"},
            {"name": "Org Level 3 Code", "value": "TEAM1"},
            {"name": "Org Level 4 Code", "value": ""},
            {"name": "Full/Part Time Code", "value": "F"},
            {"name": "Employment Type Code", "value": "FTC"},
            {"name": "Employment Status Code", "value": "A"},
            {"name": "Last Hire", "value": "01/15/2020"},
            {"name": "Termination Date", "value": ""},
        ],
    }


@pytest.fixture
def sample_location() -> Dict[str, Any]:
    """Sample UKG location response."""
    return {
        "locationCode": "LOC001",
        "description": "Orlando Office",
        "state": "FL",
        "country": "USA",
    }


@pytest.fixture
def sample_supervisor_details() -> Dict[str, Any]:
    """Sample UKG supervisor-details response."""
    return {
        "employeeId": "EMP001",
        "supervisorFirstName": "Jane",
        "supervisorLastName": "Manager",
        "supervisorEmployeeId": "MGR001",
        "supervisorEmployeeNumber": "99999",
    }


@pytest.fixture
def mock_ukg_responses(
    sample_ukg_employment_details,
    sample_ukg_employee_employment_details,
    sample_ukg_person_details,
    sample_location,
):
    """Set up mocked UKG API responses."""
    def _setup():
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
    return _setup


@pytest.fixture
def mock_motus_responses():
    """Set up mocked Motus API responses."""
    def _setup(driver_exists=False):
        if driver_exists:
            # Driver exists - return 200 with existing data
            responses.add(
                responses.GET,
                re.compile(r".*/drivers/.*"),
                json={"clientEmployeeId1": "12345", "status": "active"},
                status=200,
            )
            # Update succeeds
            responses.add(
                responses.PUT,
                re.compile(r".*/drivers/.*"),
                json={"clientEmployeeId1": "12345", "status": "updated"},
                status=200,
            )
        else:
            # Driver doesn't exist - return 404
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
    return _setup


@pytest.fixture
def mock_motus_token():
    """Set up mocked Motus token endpoint."""
    def _setup():
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={
                "access_token": "new-test-jwt-token",
                "token_type": "Bearer",
                "expires_in": 3300,
            },
            status=200,
        )
    return _setup


def get_builder_module(monkeypatch):
    """Helper to get fresh builder module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "builder",
        str(Path(__file__).parent.parent / "build-motus-driver.py")
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def get_upserter_module(monkeypatch):
    """Helper to get fresh upserter module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upserter",
        str(Path(__file__).parent.parent / "upsert-motus-driver.py")
    )
    upserter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upserter)
    return upserter


def get_batch_module(monkeypatch):
    """Helper to get fresh batch module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "batch",
        str(Path(__file__).parent.parent / "run-motus-batch.py")
    )
    batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch)
    return batch


def get_token_module(monkeypatch):
    """Helper to get fresh token module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "token",
        str(Path(__file__).parent.parent / "motus-get-token.py")
    )
    token = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(token)
    return token
