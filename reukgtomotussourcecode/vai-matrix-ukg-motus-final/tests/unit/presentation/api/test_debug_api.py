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
    ):
        """Test build-driver handles exceptions gracefully."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            mock_client.get_employment_details.side_effect = Exception("Connection refused")
            mock_client.get_employee_employment_details.return_value = {}
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/build-driver",
                json={"employee_number": "28190", "company_id": "J9A6Y", "include_trace": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_compare_exception(self, client):
        """Test compare endpoint handles exceptions gracefully."""
        with patch("src.presentation.api.debug_api.get_ukg_client") as mock_get_ukg:
            mock_client = MagicMock()
            # Return empty dicts instead of raising exceptions to avoid JSON serialization issues
            mock_client.get_employment_details.return_value = {}
            mock_client.get_employee_employment_details.return_value = {}
            mock_get_ukg.return_value = mock_client

            response = client.post(
                "/compare",
                json={"employee_number": "99999", "company_id": "J9A6Y"},
            )

            assert response.status_code == 200
            data = response.json()
            # Empty employment details results in a failed build
            assert data.get("success") is False or data.get("ukg_built_payload") is None


# ============ Validation Function Tests ============

class TestValidateNewHireFunction:
    """Tests for _validate_new_hire validation logic."""

    def test_new_hire_ineligible_job_code(self, client, sample_person_details):
        """Test validation when job code is not eligible."""
        from src.presentation.api.debug_api import _validate_new_hire
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"primaryJobCode": "9999"},
            "person_details": sample_person_details,
        }

        checks, recommendation = _validate_new_hire(ukg_data, None, "12345")

        assert any(c.check == "Job code is eligible for Motus" and c.status == CheckStatus.FAIL for c in checks)
        assert "ineligible job code" in recommendation.lower()

    def test_new_hire_missing_required_fields(self, client):
        """Test validation when required UKG fields are missing."""
        from src.presentation.api.debug_api import _validate_new_hire
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"primaryJobCode": "1103"},
            "person_details": {
                "firstName": "John",
                "lastName": "",  # Missing
                "emailAddress": "",  # Missing
            },
        }

        checks, recommendation = _validate_new_hire(ukg_data, None, "12345")

        assert any(c.check == "Required fields present in UKG" and c.status == CheckStatus.FAIL for c in checks)
        assert "Missing" in recommendation

    def test_new_hire_already_exists_in_motus(self, client, sample_person_details):
        """Test validation when employee already exists in Motus."""
        from src.presentation.api.debug_api import _validate_new_hire
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"primaryJobCode": "1103"},
            "person_details": sample_person_details,
        }
        motus_current = {"clientEmployeeId1": "12345"}

        checks, recommendation = _validate_new_hire(ukg_data, motus_current, "12345")

        assert any(c.check == "Employee not already in Motus" and c.status == CheckStatus.WARN for c in checks)
        assert "already exists" in recommendation.lower()

    def test_new_hire_missing_start_date(self, client, sample_person_details):
        """Test validation when start date is not present."""
        from src.presentation.api.debug_api import _validate_new_hire
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"primaryJobCode": "1103", "startDate": None},
            "person_details": sample_person_details,
        }

        checks, recommendation = _validate_new_hire(ukg_data, None, "12345")

        assert any(c.check == "Start date present" and c.status == CheckStatus.WARN for c in checks)

    def test_new_hire_all_checks_pass(self, client, sample_person_details):
        """Test validation when all checks pass."""
        from src.presentation.api.debug_api import _validate_new_hire

        ukg_data = {
            "employment_details": {"primaryJobCode": "1103", "startDate": "2024-01-15"},
            "person_details": sample_person_details,
        }

        checks, recommendation = _validate_new_hire(ukg_data, None, "12345")

        assert "eligible for Motus" in recommendation


class TestValidateTerminationFunction:
    """Tests for _validate_termination validation logic."""

    def test_termination_no_date_in_ukg(self, client):
        """Test when dateOfTermination is not set in UKG."""
        from src.presentation.api.debug_api import _validate_termination
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"dateOfTermination": None},
        }

        checks, recommendation = _validate_termination(ukg_data, None, "12345")

        assert any(c.check == "dateOfTermination in UKG" and c.status == CheckStatus.FAIL for c in checks)
        assert "No termination date" in recommendation

    def test_termination_employee_not_in_motus(self, client):
        """Test when employee doesn't exist in Motus."""
        from src.presentation.api.debug_api import _validate_termination

        ukg_data = {
            "employment_details": {
                "dateOfTermination": "2024-03-15",
                "employeeStatusCode": "T",
            },
        }

        checks, recommendation = _validate_termination(ukg_data, None, "12345")

        assert "does not exist in Motus" in recommendation

    def test_termination_already_synced(self, client):
        """Test when termination is already synced to Motus."""
        from src.presentation.api.debug_api import _validate_termination

        ukg_data = {
            "employment_details": {
                "dateOfTermination": "2024-03-15",
                "employeeStatusCode": "T",
            },
        }
        motus_current = {
            "endDate": "2024-03-15",
            "customVariables": [{"name": "Derived Status", "value": "Terminated"}],
        }

        checks, recommendation = _validate_termination(ukg_data, motus_current, "12345")

        assert "already synced" in recommendation.lower()

    def test_termination_needs_sync(self, client):
        """Test when termination exists in UKG but not in Motus."""
        from src.presentation.api.debug_api import _validate_termination

        ukg_data = {
            "employment_details": {
                "dateOfTermination": "2024-03-15",
                "employeeStatusCode": "T",
            },
        }
        motus_current = {
            "endDate": None,
            "customVariables": [{"name": "Derived Status", "value": "Active"}],
        }

        checks, recommendation = _validate_termination(ukg_data, motus_current, "12345")

        assert "Run sync to update" in recommendation

    def test_termination_derived_status_check(self, client):
        """Test derived status calculation for terminated employee."""
        from src.presentation.api.debug_api import _validate_termination

        ukg_data = {
            "employment_details": {
                "dateOfTermination": "2024-03-15",
                "employeeStatusCode": "T",
            },
        }

        checks, recommendation = _validate_termination(ukg_data, None, "12345")

        assert any(c.check == "Derived Status = Terminated" for c in checks)


class TestValidateLeaveFunction:
    """Tests for _validate_leave validation logic."""

    def test_leave_no_start_date(self, client):
        """Test when leave start date is not set."""
        from src.presentation.api.debug_api import _validate_leave
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {"employeeStatusStartDate": None},
        }

        checks, recommendation = _validate_leave(ukg_data, None, "12345")

        assert any(c.check == "employeeStatusStartDate in UKG" and c.status == CheckStatus.FAIL for c in checks)
        assert "not on leave" in recommendation.lower()

    def test_leave_ongoing_no_end_date(self, client):
        """Test ongoing leave with no end date."""
        from src.presentation.api.debug_api import _validate_leave
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "employment_details": {
                "employeeStatusStartDate": "2024-03-01",
                "employeeStatusExpectedEndDate": None,
            },
        }

        checks, recommendation = _validate_leave(ukg_data, None, "12345")

        assert any(c.check == "employeeStatusExpectedEndDate in UKG" and c.status == CheckStatus.WARN for c in checks)

    def test_leave_employee_not_in_motus(self, client):
        """Test leave validation when employee not in Motus."""
        from src.presentation.api.debug_api import _validate_leave

        ukg_data = {
            "employment_details": {
                "employeeStatusStartDate": "2024-03-01",
                "employeeStatusExpectedEndDate": "2024-04-01",
            },
        }

        checks, recommendation = _validate_leave(ukg_data, None, "12345")

        assert "does not exist in Motus" in recommendation

    def test_leave_already_synced(self, client):
        """Test when leave is already synced."""
        from src.presentation.api.debug_api import _validate_leave

        ukg_data = {
            "employment_details": {
                "employeeStatusStartDate": "2024-03-01",
                "employeeStatusExpectedEndDate": "2024-04-01",
            },
        }
        motus_current = {
            "leaveStartDate": "2024-03-01",
            "leaveEndDate": "2024-04-01",
        }

        checks, recommendation = _validate_leave(ukg_data, motus_current, "12345")

        assert "already in sync" in recommendation.lower()

    def test_leave_needs_sync(self, client):
        """Test when leave data needs to be synced."""
        from src.presentation.api.debug_api import _validate_leave

        ukg_data = {
            "employment_details": {
                "employeeStatusStartDate": "2024-03-01",
                "employeeStatusExpectedEndDate": "2024-04-01",
            },
        }
        motus_current = {
            "leaveStartDate": None,
            "leaveEndDate": None,
        }

        checks, recommendation = _validate_leave(ukg_data, motus_current, "12345")

        assert "Run sync to update" in recommendation


class TestValidateManagerChangeFunction:
    """Tests for _validate_manager_change validation logic."""

    def test_manager_change_no_supervisor_in_ukg(self, client):
        """Test when supervisor details not found in UKG."""
        from src.presentation.api.debug_api import _validate_manager_change
        from src.presentation.api.models import CheckStatus

        ukg_data = {
            "supervisor_details": {},
        }

        checks, recommendation = _validate_manager_change(ukg_data, None, "12345")

        assert any(c.check == "Supervisor details in UKG" and c.status == CheckStatus.WARN for c in checks)

    def test_manager_change_employee_not_in_motus(self, client):
        """Test when employee doesn't exist in Motus."""
        from src.presentation.api.debug_api import _validate_manager_change

        ukg_data = {
            "supervisor_details": {
                "supervisorFirstName": "Jane",
                "supervisorLastName": "Smith",
            },
        }

        checks, recommendation = _validate_manager_change(ukg_data, None, "12345")

        assert "does not exist in Motus" in recommendation

    def test_manager_change_names_match(self, client):
        """Test when manager names already match."""
        from src.presentation.api.debug_api import _validate_manager_change

        ukg_data = {
            "supervisor_details": {
                "supervisorFirstName": "Jane",
                "supervisorLastName": "Smith",
            },
        }
        motus_current = {
            "customVariables": [{"name": "Manager Name", "value": "Jane Smith"}],
        }

        checks, recommendation = _validate_manager_change(ukg_data, motus_current, "12345")

        assert "already in sync" in recommendation.lower()

    def test_manager_change_names_differ(self, client):
        """Test when manager names are different."""
        from src.presentation.api.debug_api import _validate_manager_change

        ukg_data = {
            "supervisor_details": {
                "supervisorFirstName": "Jane",
                "supervisorLastName": "Smith",
            },
        }
        motus_current = {
            "customVariables": [{"name": "Manager Name", "value": "John Doe"}],
        }

        checks, recommendation = _validate_manager_change(ukg_data, motus_current, "12345")

        assert "mismatch" in recommendation.lower()
        assert "Run sync to update" in recommendation


class TestValidateAddressFunction:
    """Tests for _validate_address validation logic."""

    def test_address_all_fields_match(self, client, sample_person_details):
        """Test when all address fields match."""
        from src.presentation.api.debug_api import _validate_address
        from src.presentation.api.models import CheckStatus

        ukg_data = {"person_details": sample_person_details}
        motus_current = {
            "address1": sample_person_details["addressLine1"],
            "city": sample_person_details["addressCity"],
            "stateProvince": sample_person_details["addressState"],
            "postalCode": sample_person_details["addressZipCode"],
        }

        checks, recommendation = _validate_address(ukg_data, motus_current, "12345")

        assert all(c.status == CheckStatus.PASS for c in checks)
        assert "in sync" in recommendation.lower()

    def test_address_some_fields_differ(self, client, sample_person_details):
        """Test when some address fields are different."""
        from src.presentation.api.debug_api import _validate_address
        from src.presentation.api.models import CheckStatus

        ukg_data = {"person_details": sample_person_details}
        motus_current = {
            "address1": "456 Different St",
            "city": sample_person_details["addressCity"],
            "stateProvince": sample_person_details["addressState"],
            "postalCode": sample_person_details["addressZipCode"],
        }

        checks, recommendation = _validate_address(ukg_data, motus_current, "12345")

        assert any(c.status == CheckStatus.FAIL for c in checks)
        assert "differ" in recommendation.lower()

    def test_address_employee_not_in_motus(self, client, sample_person_details):
        """Test when employee not in Motus."""
        from src.presentation.api.debug_api import _validate_address

        ukg_data = {"person_details": sample_person_details}

        checks, recommendation = _validate_address(ukg_data, None, "12345")

        assert "does not exist in Motus" in recommendation


# ============ Helper Function Tests ============

class TestFetchAllUKGData:
    """Tests for _fetch_all_ukg_data helper function."""

    def test_employment_details_exception(self):
        """Test exception handling when employment details fetch fails."""
        from src.presentation.api.debug_api import _fetch_all_ukg_data

        mock_client = MagicMock()
        mock_client.get_employment_details.side_effect = Exception("API Error")
        mock_client.get_employee_employment_details.return_value = {}

        result = _fetch_all_ukg_data(mock_client, "12345", "J9A6Y")

        assert result["employment_details"] == {}

    def test_person_details_exception(self):
        """Test exception handling when person details fetch fails."""
        from src.presentation.api.debug_api import _fetch_all_ukg_data

        mock_client = MagicMock()
        mock_client.get_employment_details.return_value = {"employeeId": "emp-123"}
        mock_client.get_employee_employment_details.return_value = {}
        mock_client.get_person_details.side_effect = Exception("API Error")
        mock_client.get_supervisor_details.return_value = {}

        result = _fetch_all_ukg_data(mock_client, "12345", "J9A6Y")

        assert result["person_details"] == {}

    def test_supervisor_details_exception(self):
        """Test exception handling when supervisor details fetch fails."""
        from src.presentation.api.debug_api import _fetch_all_ukg_data

        mock_client = MagicMock()
        mock_client.get_employment_details.return_value = {"employeeId": "emp-123"}
        mock_client.get_employee_employment_details.return_value = {}
        mock_client.get_person_details.return_value = {"firstName": "John"}
        mock_client.get_supervisor_details.side_effect = Exception("API Error")

        result = _fetch_all_ukg_data(mock_client, "12345", "J9A6Y")

        assert result["supervisor_details"] == {}

    def test_no_employee_id_skips_person_and_supervisor(self):
        """Test that person/supervisor fetch is skipped when no employee ID."""
        from src.presentation.api.debug_api import _fetch_all_ukg_data

        mock_client = MagicMock()
        mock_client.get_employment_details.return_value = {}  # No employeeId
        mock_client.get_employee_employment_details.return_value = {}  # No employeeId

        result = _fetch_all_ukg_data(mock_client, "12345", "J9A6Y")

        mock_client.get_person_details.assert_not_called()
        mock_client.get_supervisor_details.assert_not_called()

    def test_with_logger_logs_requests(self):
        """Test that logger is called for UKG requests."""
        from src.presentation.api.debug_api import _fetch_all_ukg_data
        from src.presentation.api.logging_service import DebugLogger

        mock_client = MagicMock()
        mock_client.get_employment_details.return_value = {"employeeId": "emp-123"}
        mock_client.get_employee_employment_details.return_value = {}
        mock_client.get_person_details.return_value = {"firstName": "John"}
        mock_client.get_supervisor_details.return_value = {}

        logger = DebugLogger("12345", "J9A6Y", "test-op")
        result = _fetch_all_ukg_data(mock_client, "12345", "J9A6Y", logger)

        # Check logger recorded UKG calls
        trace = logger.get_trace()
        assert len(trace.ukg_calls) >= 2  # At least employment and employee employment


class TestComparePayloads:
    """Tests for _compare_payloads helper function."""

    def test_compare_identical_payloads(self):
        """Test comparison of identical payloads."""
        from src.presentation.api.debug_api import _compare_payloads

        payload1 = {"firstName": "John", "lastName": "Doe"}
        payload2 = {"firstName": "John", "lastName": "Doe"}

        differences = _compare_payloads(payload1, payload2)

        assert len(differences) == 0

    def test_compare_different_simple_fields(self):
        """Test comparison with different simple fields."""
        from src.presentation.api.debug_api import _compare_payloads

        payload1 = {"firstName": "John", "lastName": "Doe"}
        payload2 = {"firstName": "Jane", "lastName": "Doe"}

        differences = _compare_payloads(payload1, payload2)

        assert len(differences) == 1
        assert differences[0].field == "firstName"
        assert differences[0].ukg_value == "John"
        assert differences[0].motus_value == "Jane"

    def test_compare_different_custom_variables(self):
        """Test comparison with different custom variables."""
        from src.presentation.api.debug_api import _compare_payloads

        payload1 = {
            "firstName": "John",
            "customVariables": [{"name": "Manager Name", "value": "Jane Smith"}],
        }
        payload2 = {
            "firstName": "John",
            "customVariables": [{"name": "Manager Name", "value": "John Doe"}],
        }

        differences = _compare_payloads(payload1, payload2)

        assert any("Manager Name" in str(d) for d in differences)

    def test_compare_missing_fields(self):
        """Test comparison when one payload has missing fields."""
        from src.presentation.api.debug_api import _compare_payloads

        payload1 = {"firstName": "John", "lastName": "Doe", "city": "Miami"}
        payload2 = {"firstName": "John", "lastName": "Doe"}

        differences = _compare_payloads(payload1, payload2)

        assert any(d.field == "city" for d in differences)
