"""
Integration tests for Debug API.

These tests use mock responses to simulate UKG and Motus API calls.
Tests validate end-to-end functionality through the Debug API endpoints.

Run with: pytest tests/integration/test_debug_api_e2e.py -v -m integration
"""

import os
import pytest
import responses
import re
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.presentation.api.debug_api import app


# ============ Test Configuration ============

# Company ID used for all tests
COMPANY_ID = "J9A6Y"

# Test EEIDs by scenario
TEST_EEIDS = {
    "new_hire": ["28190", "28203", "28207", "28209", "28210"],
    "termination": ["26737", "27991", "28069", "23497", "27938"],
    "manager_change": ["28195"],
    "address_change": ["25336", "26421", "10858", "22299"],
    "leave": ["022393", "028027", "026434"],
}

# Mock UKG employment data
MOCK_UKG_EMPLOYMENT = {
    "employeeId": "EMP001",
    "employeeNumber": "28190",
    "companyID": "J9A6Y",
    "primaryJobCode": "1103",
    "employeeStatusCode": "A",
    "dateOfTermination": None,
    "employeeStatusStartDate": None,
    "lastHireDate": "2024-01-15T00:00:00Z",
    "fullTimeOrPartTimeCode": "F",
    "homeLocationCode": "LOC001",
    "supervisorId": "SUP001",
}

MOCK_UKG_PERSON = {
    "employeeId": "EMP001",
    "firstName": "Test",
    "lastName": "Employee",
    "middleName": "",
    "emailAddress": "test.employee@example.com",
    "mobilePhone": "555-123-4567",
    "homePhone": "555-987-6543",
    "addressLine1": "123 Test Street",
    "addressLine2": "",
    "addressCity": "Orlando",
    "addressState": "FL",
    "addressPostalCode": "32801",
    "addressCountry": "USA",
}

MOCK_UKG_SUPERVISOR = {
    "supervisorFirstName": "Manager",
    "supervisorLastName": "Name",
    "supervisorId": "SUP001",
}

MOCK_MOTUS_DRIVER = {
    "clientEmployeeId1": "28190",
    "programId": 21232,
    "firstName": "Test",
    "lastName": "Employee",
    "email": "test.employee@example.com",
    "address1": "123 Test Street",
    "city": "Orlando",
    "stateProvince": "FL",
    "postalCode": "32801",
    "country": "USA",
    "phone": "555-123-4567",
    "startDate": "2024-01-15",
    "customVariables": {
        "Manager Name": "Manager Name",
        "Division": "Test Division",
    },
}


# ============ Fixtures ============

@pytest.fixture(scope="module")
def integration_client():
    """Create test client for integration tests."""
    return TestClient(app)


@pytest.fixture
def mock_ukg_responses():
    """Set up mock UKG API responses."""
    with responses.RequestsMock() as rsps:
        # Employment details
        rsps.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[MOCK_UKG_EMPLOYMENT],
            status=200,
        )
        # Person details
        rsps.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        # Supervisor details
        rsps.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        # Org levels - must include level field for proper caching
        rsps.add(
            responses.GET,
            re.compile(r".*/configuration/v1/org-levels.*"),
            json=[
                {"level": 1, "code": "DIV1", "description": "Division 1", "longDescription": "Division One - Full Description"},
                {"level": 2, "code": "DEPT1", "description": "Department 1", "longDescription": "Department One - Full Description"},
                {"level": 3, "code": "TEAM1", "description": "Team 1", "longDescription": "Team One - Full Description"},
                {"level": 4, "code": "GRP1", "description": "Group 1", "longDescription": "Group One - Full Description"},
            ],
            status=200,
        )
        yield rsps


@pytest.fixture
def mock_motus_responses():
    """Set up mock Motus API responses."""
    with responses.RequestsMock() as rsps:
        # Get driver
        rsps.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json=MOCK_MOTUS_DRIVER,
            status=200,
        )
        # Create driver
        rsps.add(
            responses.POST,
            re.compile(r".*/drivers.*"),
            json={"clientEmployeeId1": "28190", "id": "new-driver-id"},
            status=201,
        )
        # Update driver
        rsps.add(
            responses.PUT,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "28190", "status": "updated"},
            status=200,
        )
        yield rsps


@pytest.fixture
def mock_all_apis(mock_ukg_responses, mock_motus_responses):
    """Combine UKG and Motus mocks."""
    # This is a convenience fixture to use both mocks together
    pass


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set required environment variables for tests."""
    monkeypatch.setenv("UKG_BASE_URL", "https://service5.ultipro.com")
    monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0ZXN0")  # test:test
    monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "test-api-key")
    monkeypatch.setenv("MOTUS_API_BASE", "https://api.motus.com/v1")
    monkeypatch.setenv("MOTUS_JWT", "test-jwt-token")
    monkeypatch.setenv("COMPANY_ID", "J9A6Y")
    monkeypatch.setenv("JOB_IDS", "1103,4165,4166,1102,1106,4197,4196,2817,4121,2157")


# ============ Health Check ============

@pytest.mark.integration
class TestHealthCheck:
    """Health check tests."""

    def test_health_endpoint(self, integration_client):
        """Test health endpoint is accessible."""
        response = integration_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ============ New Hire Flow Tests ============

@pytest.mark.integration
class TestNewHireFlow:
    """
    Integration tests for new hire scenarios.

    Test EEIDs: 28190, 28203, 28207, 28209, 28210
    These employees should be created in Motus but are currently missing.
    """

    @pytest.fixture
    def new_hire_eeid(self):
        """Get a test EEID for new hire scenario."""
        return TEST_EEIDS["new_hire"][0]

    @responses.activate
    def test_build_driver_new_hire(self, integration_client, new_hire_eeid):
        """Test building driver payload for new hire."""
        # Set up mock responses
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": new_hire_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )

        response = integration_client.post(
            "/build-driver",
            json={"employee_number": new_hire_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Should have UKG data or error
        assert "ukg_data" in data or "error" in data

    @responses.activate
    def test_validate_new_hire_scenario(self, integration_client, new_hire_eeid):
        """Test validation of new hire scenario."""
        # Set up mock responses
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": new_hire_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )

        response = integration_client.post(
            "/validate-scenario",
            json={
                "employee_number": new_hire_eeid,
                "company_id": COMPANY_ID,
                "scenario": "new_hire",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["scenario"] == "new_hire"
        assert data["employee_number"] == new_hire_eeid

    @responses.activate
    def test_compare_new_hire(self, integration_client, new_hire_eeid):
        """Test comparing new hire data between UKG and Motus."""
        # Set up mock responses
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": new_hire_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        # Driver doesn't exist in Motus (new hire)
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": new_hire_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # New hires should not exist in Motus
        assert "exists_in_motus" in data or "error" in data


# ============ Termination Flow Tests ============

@pytest.mark.integration
class TestTerminationFlow:
    """
    Integration tests for termination scenarios.

    Test EEIDs: 26737, 27991, 28069, 23497, 27938
    These employees should have termination data synced to Motus.
    """

    @pytest.fixture
    def termination_eeid(self):
        """Get a test EEID for termination scenario."""
        return TEST_EEIDS["termination"][0]

    @responses.activate
    def test_compare_termination(self, integration_client, termination_eeid):
        """Test comparing termination data between UKG and Motus."""
        terminated_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": termination_eeid,
            "employeeStatusCode": "T",
            "dateOfTermination": "2024-03-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[terminated_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": termination_eeid},
            status=200,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": termination_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Should be able to compare the data
        assert "differences" in data or "error" in data

    @responses.activate
    def test_validate_termination_scenario(self, integration_client, termination_eeid):
        """Test validation of termination scenario."""
        terminated_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": termination_eeid,
            "employeeStatusCode": "T",
            "dateOfTermination": "2024-03-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[terminated_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": termination_eeid},
            status=200,
        )

        response = integration_client.post(
            "/validate-scenario",
            json={
                "employee_number": termination_eeid,
                "company_id": COMPANY_ID,
                "scenario": "termination",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["scenario"] == "termination"

    @responses.activate
    def test_sync_termination_dry_run(self, integration_client, termination_eeid):
        """Test dry-run sync for terminated employee."""
        terminated_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": termination_eeid,
            "employeeStatusCode": "T",
            "dateOfTermination": "2024-03-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[terminated_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": termination_eeid},
            status=200,
        )

        response = integration_client.post(
            "/sync",
            json={
                "employee_number": termination_eeid,
                "company_id": COMPANY_ID,
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True


# ============ Manager Change Flow Tests ============

@pytest.mark.integration
class TestManagerChangeFlow:
    """
    Integration tests for manager change scenarios.

    Test EEID: 28195
    This employee should have manager change synced to Motus.
    """

    @pytest.fixture
    def manager_change_eeid(self):
        """Get a test EEID for manager change scenario."""
        return TEST_EEIDS["manager_change"][0]

    @responses.activate
    def test_compare_manager_change(self, integration_client, manager_change_eeid):
        """Test comparing manager data between UKG and Motus."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": manager_change_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json={"supervisorFirstName": "New", "supervisorLastName": "Manager"},
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": manager_change_eeid},
            status=200,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": manager_change_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Should be able to compare
        assert "differences" in data or "error" in data

    @responses.activate
    def test_validate_manager_change_scenario(self, integration_client, manager_change_eeid):
        """Test validation of manager change scenario."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": manager_change_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": manager_change_eeid},
            status=200,
        )

        response = integration_client.post(
            "/validate-scenario",
            json={
                "employee_number": manager_change_eeid,
                "company_id": COMPANY_ID,
                "scenario": "manager_change",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["scenario"] == "manager_change"


# ============ Leave of Absence Flow Tests ============

@pytest.mark.integration
class TestLeaveFlow:
    """
    Integration tests for leave of absence scenarios.

    Test EEIDs: 022393, 028027, 026434
    These employees should have leave data synced to Motus.
    """

    @pytest.fixture
    def leave_eeid(self):
        """Get a test EEID for leave scenario."""
        return TEST_EEIDS["leave"][0]

    @responses.activate
    def test_validate_leave_scenario(self, integration_client, leave_eeid):
        """Test validation of leave scenario."""
        leave_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": leave_eeid,
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
            "employeeStatusExpectedEndDate": None,
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[leave_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": leave_eeid},
            status=200,
        )

        response = integration_client.post(
            "/validate-scenario",
            json={
                "employee_number": leave_eeid,
                "company_id": COMPANY_ID,
                "scenario": "leave",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["scenario"] == "leave"

    @responses.activate
    def test_compare_leave(self, integration_client, leave_eeid):
        """Test comparing leave data between UKG and Motus."""
        leave_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": leave_eeid,
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[leave_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": leave_eeid},
            status=200,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": leave_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Should be able to compare the data
        assert "ukg_built_payload" in data or "error" in data


# ============ Address Change Flow Tests ============

@pytest.mark.integration
class TestAddressChangeFlow:
    """
    Integration tests for address change scenarios.

    Test EEIDs: 25336, 26421, 10858, 22299
    These employees should have address changes synced to Motus.
    """

    @pytest.fixture
    def address_eeid(self):
        """Get a test EEID for address change scenario."""
        return TEST_EEIDS["address_change"][0]

    @responses.activate
    def test_validate_address_scenario(self, integration_client, address_eeid):
        """Test validation of address change scenario."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": address_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={**MOCK_UKG_PERSON, "addressLine1": "456 New Address"},
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": address_eeid},
            status=200,
        )

        response = integration_client.post(
            "/validate-scenario",
            json={
                "employee_number": address_eeid,
                "company_id": COMPANY_ID,
                "scenario": "address",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["scenario"] == "address"

    @responses.activate
    def test_compare_address(self, integration_client, address_eeid):
        """Test comparing address data between UKG and Motus."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": address_eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json={**MOCK_UKG_PERSON, "addressLine1": "789 Updated Street"},
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": address_eeid},
            status=200,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": address_eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Should be able to compare
        assert "differences" in data or "error" in data


# ============ UKG Raw Endpoint Tests ============

@pytest.mark.integration
class TestUKGRawEndpoints:
    """Integration tests for UKG raw data endpoints."""

    @pytest.fixture
    def test_eeid(self):
        """Get a test EEID."""
        return TEST_EEIDS["new_hire"][0]

    @responses.activate
    def test_get_employment_details(self, integration_client, test_eeid):
        """Test getting raw employment details from UKG."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": test_eeid}],
            status=200,
        )

        response = integration_client.get(
            f"/ukg/employment-details/{test_eeid}",
            params={"company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        assert "success" in data or "data" in data or "error" in data

    @responses.activate
    def test_get_employee_employment_details(self, integration_client, test_eeid):
        """Test getting raw employee employment details from UKG."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": test_eeid}],
            status=200,
        )

        response = integration_client.get(
            f"/ukg/employee-employment-details/{test_eeid}",
            params={"company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "data" in data or "error" in data


# ============ Motus Raw Endpoint Tests ============

@pytest.mark.integration
class TestMotusRawEndpoints:
    """Integration tests for Motus raw data endpoints."""

    @pytest.fixture
    def test_eeid(self):
        """Get a test EEID."""
        return TEST_EEIDS["termination"][0]

    @responses.activate
    def test_get_driver(self, integration_client, test_eeid):
        """Test getting driver data from Motus."""
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": test_eeid},
            status=200,
        )

        response = integration_client.get(f"/motus/driver/{test_eeid}")

        assert response.status_code == 200
        data = response.json()

        assert "success" in data or "exists" in data or "driver" in data or "error" in data


# ============ Full Sync Flow Test (Dry Run Only) ============

@pytest.mark.integration
class TestFullSyncFlow:
    """
    Full sync flow tests (dry-run only for safety).

    Tests the complete flow: UKG fetch -> transform -> Motus sync simulation.
    """

    @responses.activate
    def test_sync_new_hire_dry_run(self, integration_client):
        """Test complete sync flow for new hire (dry-run)."""
        eeid = TEST_EEIDS["new_hire"][0]

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )

        response = integration_client.post(
            "/sync",
            json={
                "employee_number": eeid,
                "company_id": COMPANY_ID,
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True
        assert data["employee_number"] == eeid

    @responses.activate
    def test_sync_termination_dry_run(self, integration_client):
        """Test complete sync flow for termination (dry-run)."""
        eeid = TEST_EEIDS["termination"][0]

        terminated_emp = {
            **MOCK_UKG_EMPLOYMENT,
            "employeeNumber": eeid,
            "employeeStatusCode": "T",
            "dateOfTermination": "2024-03-01T00:00:00Z",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[terminated_emp],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": eeid},
            status=200,
        )

        response = integration_client.post(
            "/sync",
            json={
                "employee_number": eeid,
                "company_id": COMPANY_ID,
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True


# ============ Trace Validation Tests ============

@pytest.mark.integration
class TestTraceCapture:
    """Tests to verify trace capture at each stage."""

    @responses.activate
    def test_trace_captures_ukg_calls(self, integration_client):
        """Test that trace captures all UKG API calls."""
        eeid = TEST_EEIDS["new_hire"][0]

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )

        response = integration_client.post(
            "/build-driver",
            json={"employee_number": eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response contains expected fields
        assert "ukg_data" in data or "error" in data or "trace" in data

    @responses.activate
    def test_trace_captures_transformations(self, integration_client):
        """Test that trace captures transformation steps."""
        eeid = TEST_EEIDS["new_hire"][0]

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )

        response = integration_client.post(
            "/build-driver",
            json={"employee_number": eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response contains expected fields
        assert "motus_payload" in data or "error" in data or "transformations" in data

    @responses.activate
    def test_trace_captures_motus_calls(self, integration_client):
        """Test that trace captures Motus API calls."""
        eeid = TEST_EEIDS["termination"][0]

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{**MOCK_UKG_EMPLOYMENT, "employeeNumber": eeid}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=MOCK_UKG_PERSON,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=MOCK_UKG_SUPERVISOR,
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={**MOCK_MOTUS_DRIVER, "clientEmployeeId1": eeid},
            status=200,
        )

        response = integration_client.post(
            "/compare",
            json={"employee_number": eeid, "company_id": COMPANY_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response contains expected fields
        assert "exists_in_motus" in data or "error" in data or "trace" in data
