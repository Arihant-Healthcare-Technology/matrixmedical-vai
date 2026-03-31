"""
Unit tests for Debug API endpoints.

Tests all API endpoints with mocked UKG and Motus clients.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.presentation.api.debug_api import app, get_ukg_client, get_motus_client


# ============ Fixtures ============

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_ukg_client():
    """Create mock UKG client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_motus_client():
    """Create mock Motus client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def sample_employment_details():
    """Sample UKG employment details."""
    return {
        "employeeNumber": "28190",
        "employeeId": "emp-123",
        "companyID": "J9A6Y",
        "primaryJobCode": "1103",
        "jobDescription": "Clinical Specialist",
        "employeeStatusCode": "A",
        "originalHireDate": "2024-01-15",
        "dateOfTermination": None,
        "employeeStatusStartDate": None,
        "employeeStatusExpectedEndDate": None,
        "primaryWorkLocationCode": "LOC001",
        "orgLevel1Code": "ORG1",
        "orgLevel2Code": "ORG2",
        "orgLevel3Code": "ORG3",
        "orgLevel4Code": "ORG4",
        "fullTimeOrPartTimeCode": "F",
        "employeeTypeCode": "REG",
        "lastHireDate": "2024-01-15",
    }


@pytest.fixture
def sample_person_details():
    """Sample UKG person details."""
    return {
        "employeeId": "emp-123",
        "firstName": "John",
        "lastName": "Doe",
        "emailAddress": "john.doe@matrix.com",
        "addressLine1": "123 Main St",
        "addressLine2": "Suite 100",
        "addressCity": "Miami",
        "addressState": "FL",
        "addressZipCode": "33101",
        "addressCountry": "US",
        "homePhone": "3055550001",
        "mobilePhone": "3055550002",
    }


@pytest.fixture
def sample_supervisor_details():
    """Sample UKG supervisor details."""
    return {
        "employeeId": "emp-123",
        "supervisorFirstName": "Jane",
        "supervisorLastName": "Smith",
    }


@pytest.fixture
def sample_employee_employment_details():
    """Sample UKG employee employment details."""
    return {
        "employeeNumber": "28190",
        "employeeId": "emp-123",
        "companyID": "J9A6Y",
        "primaryProjectCode": "PROJ001",
        "primaryProjectDescription": "Clinical Operations",
    }


@pytest.fixture
def sample_motus_driver():
    """Sample Motus driver data."""
    return {
        "clientEmployeeId1": "28190",
        "programId": 21232,
        "firstName": "John",
        "lastName": "Doe",
        "email": "john.doe@matrix.com",
        "address1": "123 Main St",
        "city": "Miami",
        "stateProvince": "FL",
        "postalCode": "33101",
        "startDate": "2024-01-15",
        "endDate": None,
        "employeeStatusStartDate": None,
        "employeeStatusExpectedEndDate": None,
        "customVariables": [
            {"name": "Manager Name", "value": "Jane Smith"},
            {"name": "Derived Status", "value": "Active"},
        ],
    }


# ============ Health Endpoint Tests ============

class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok(self, client):
        """Test health check returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "motus-debug-api"
        assert "version" in data


# ============ Build Driver Endpoint Tests ============

class TestBuildDriverEndpoint:
    """Tests for build-driver endpoint."""

    def test_build_driver_success(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_supervisor_details,
        sample_employee_employment_details,
    ):
        """Test successful driver build."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.return_value = sample_employment_details
            mock_client.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_client.get_person_details.return_value = sample_person_details
            mock_client.get_supervisor_details.return_value = sample_supervisor_details
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/build-driver",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["employee_number"] == "28190"
            assert data["motus_payload"] is not None
            assert data["motus_payload"]["programId"] == 21232  # FAVR
            assert data["transformations"]["derived_status"] == "Active"
            assert "trace" in data

    def test_build_driver_employee_not_found(self, client):
        """Test build driver when employee not found."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.return_value = {}
            mock_client.get_employee_employment_details.return_value = {}
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/build-driver",
                json={"employee_number": "99999", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_build_driver_invalid_job_code(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
    ):
        """Test build driver with invalid job code."""
        # Modify to have ineligible job code
        sample_employment_details["primaryJobCode"] = "9999"

        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.return_value = sample_employment_details
            mock_client.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_client.get_person_details.return_value = sample_person_details
            mock_client.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/build-driver",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert any("No program ID" in err for err in data.get("validation_errors", []))


# ============ Compare Endpoint Tests ============

class TestCompareEndpoint:
    """Tests for compare endpoint."""

    def test_compare_employee_exists_in_motus(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_supervisor_details,
        sample_employee_employment_details,
        sample_motus_driver,
    ):
        """Test compare when employee exists in both systems."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = sample_supervisor_details
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = sample_motus_driver
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/compare",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["exists_in_motus"] is True
            assert data["ukg_built_payload"] is not None
            assert data["motus_current"] is not None

    def test_compare_employee_not_in_motus(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
    ):
        """Test compare when employee not in Motus."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = None
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/compare",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["exists_in_motus"] is False
            assert data["motus_current"] is None

    def test_compare_detects_differences(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
        sample_motus_driver,
    ):
        """Test that compare detects field differences."""
        # Modify Motus data to have different address
        sample_motus_driver["address1"] = "456 Different St"

        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = sample_motus_driver
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/compare",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["differences"]) > 0
            address_diff = next(
                (d for d in data["differences"] if d["field"] == "address1"),
                None
            )
            assert address_diff is not None


# ============ Validate Scenario Endpoint Tests ============

class TestValidateScenarioEndpoint:
    """Tests for validate-scenario endpoint."""

    def test_validate_new_hire_eligible_job_code(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
    ):
        """Test new hire validation with eligible job code."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = None  # Not in Motus
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/validate-scenario",
                json={
                    "employee_number": "28190",
                    "company_id": "J9A6Y",
                    "scenario": "new_hire",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "new_hire"
            # Check that job code eligibility passed
            job_check = next(
                (c for c in data["checks"] if "eligible" in c["check"].lower()),
                None
            )
            assert job_check is not None
            assert job_check["status"] == "PASS"

    def test_validate_termination_date_present(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
        sample_motus_driver,
    ):
        """Test termination validation when termination date is present."""
        # Set termination date
        sample_employment_details["dateOfTermination"] = "2024-03-15"
        sample_employment_details["employeeStatusCode"] = "T"

        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = sample_motus_driver
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/validate-scenario",
                json={
                    "employee_number": "26737",
                    "company_id": "J9A6Y",
                    "scenario": "termination",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "termination"
            # Check termination date check passed
            term_check = next(
                (c for c in data["checks"] if "dateOfTermination" in c["check"]),
                None
            )
            assert term_check is not None
            assert term_check["status"] == "PASS"

    def test_validate_leave_start_date_present(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_employee_employment_details,
        sample_motus_driver,
    ):
        """Test leave validation when leave start date is present."""
        # Set leave dates
        sample_employment_details["employeeStatusStartDate"] = "2024-02-01"
        sample_employment_details["employeeStatusExpectedEndDate"] = None

        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = {}
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = sample_motus_driver
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/validate-scenario",
                json={
                    "employee_number": "022393",
                    "company_id": "J9A6Y",
                    "scenario": "leave",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "leave"
            # Check leave start date check passed
            leave_check = next(
                (c for c in data["checks"] if "employeeStatusStartDate" in c["check"]),
                None
            )
            assert leave_check is not None
            assert leave_check["status"] == "PASS"


# ============ Sync Endpoint Tests ============

class TestSyncEndpoint:
    """Tests for sync endpoint."""

    def test_sync_dry_run_insert(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_supervisor_details,
        sample_employee_employment_details,
    ):
        """Test sync with dry_run returns would_insert for new employee."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = sample_supervisor_details
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = None  # Not in Motus
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/sync",
                json={
                    "employee_number": "28190",
                    "company_id": "J9A6Y",
                    "dry_run": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dry_run"] is True
            assert data["action"] == "would_insert"

    def test_sync_dry_run_update(
        self,
        client,
        sample_employment_details,
        sample_person_details,
        sample_supervisor_details,
        sample_employee_employment_details,
        sample_motus_driver,
    ):
        """Test sync with dry_run returns would_update for existing employee."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg, \
             patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:

            mock_ukg = MagicMock()
            mock_ukg.get_employment_details.return_value = sample_employment_details
            mock_ukg.get_employee_employment_details.return_value = sample_employee_employment_details
            mock_ukg.get_person_details.return_value = sample_person_details
            mock_ukg.get_supervisor_details.return_value = sample_supervisor_details
            mock_get_ukg.return_value = mock_ukg

            mock_motus = MagicMock()
            mock_motus.get_driver.return_value = sample_motus_driver  # Exists in Motus
            mock_get_motus.return_value = mock_motus

            response = client.post(
                "/sync",
                json={
                    "employee_number": "28190",
                    "company_id": "J9A6Y",
                    "dry_run": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dry_run"] is True
            assert data["action"] == "would_update"


# ============ UKG Raw Data Endpoint Tests ============

class TestUKGEndpoints:
    """Tests for UKG raw data endpoints."""

    def test_get_employment_details(self, client, sample_employment_details):
        """Test getting employment details."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.return_value = sample_employment_details
            mock_get_ukg.return_value = mock_client

            response = client.get(
                "/ukg/employment-details/28190",
                params={"company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["employeeNumber"] == "28190"

    def test_get_person_details(self, client, sample_person_details):
        """Test getting person details."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_person_details.return_value = sample_person_details
            mock_get_ukg.return_value = mock_client

            response = client.get("/ukg/person-details/emp-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["firstName"] == "John"


# ============ Motus Raw Data Endpoint Tests ============

class TestMotusEndpoints:
    """Tests for Motus raw data endpoints."""

    def test_get_driver_exists(self, client, sample_motus_driver):
        """Test getting existing driver."""
        with patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:
            mock_client = MagicMock()
            mock_client.get_driver.return_value = sample_motus_driver
            mock_get_motus.return_value = mock_client

            response = client.get("/motus/driver/28190")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["exists"] is True
            assert data["driver"]["clientEmployeeId1"] == "28190"

    def test_get_driver_not_found(self, client):
        """Test getting non-existent driver."""
        with patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:
            mock_client = MagicMock()
            mock_client.get_driver.return_value = None
            mock_get_motus.return_value = mock_client

            response = client.get("/motus/driver/99999")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["exists"] is False
            assert data["driver"] is None


# ============ Exception Handling Tests ============

class TestExceptionHandling:
    """Tests for exception handling in API endpoints."""

    def test_get_ukg_employment_details_exception(self, client):
        """Test employment details endpoint handles exceptions."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.side_effect = Exception("API connection error")
            mock_get_ukg.return_value = mock_client

            response = client.get(
                "/ukg/employment-details/28190",
                params={"company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "API connection error" in data["error"]

    def test_get_ukg_employee_employment_details_exception(self, client):
        """Test employee employment details endpoint handles exceptions."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employee_employment_details.side_effect = Exception("Network timeout")
            mock_get_ukg.return_value = mock_client

            response = client.get(
                "/ukg/employee-employment-details/28190",
                params={"company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Network timeout" in data["error"]

    def test_get_ukg_person_details_exception(self, client):
        """Test person details endpoint handles exceptions."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_person_details.side_effect = Exception("Invalid employee ID")
            mock_get_ukg.return_value = mock_client

            response = client.get("/ukg/person-details/emp-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Invalid employee ID" in data["error"]

    def test_get_ukg_supervisor_details_exception(self, client):
        """Test supervisor details endpoint handles exceptions."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_supervisor_details.side_effect = Exception("Supervisor not found")
            mock_get_ukg.return_value = mock_client

            response = client.get("/ukg/supervisor-details/emp-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Supervisor not found" in data["error"]

    def test_get_motus_driver_exception(self, client):
        """Test Motus driver endpoint handles exceptions."""
        with patch("src.presentation.api.debug_api.get_motus_client") as mock_get_motus:
            mock_client = MagicMock()
            mock_client.get_driver.side_effect = Exception("Motus API unavailable")
            mock_get_motus.return_value = mock_client

            response = client.get("/motus/driver/28190")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Motus API unavailable" in data["error"]

    def test_build_driver_exception(
        self,
        client,
        sample_employment_details,
    ):
        """Test build-driver handles exceptions gracefully."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.side_effect = Exception("Connection refused")
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/build-driver",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data

    def test_compare_exception(self, client):
        """Test compare endpoint handles exceptions gracefully."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.side_effect = Exception("UKG service down")
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/compare",
                json={"employee_number": "28190", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False or "error" in data
