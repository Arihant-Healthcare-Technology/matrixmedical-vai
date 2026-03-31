"""Tests for DriverBuilderService."""

import pytest
from unittest.mock import MagicMock, patch

from src.application.services import DriverBuilderService
from src.domain.models import MotusDriver
from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError


class TestDriverBuilderService:
    """Test cases for DriverBuilderService."""

    @pytest.fixture
    def mock_ukg_client(self):
        """Create a mock UKG client."""
        client = MagicMock()
        client.get_supervisor_details.return_value = {}
        client.get_location.return_value = {}
        return client

    @pytest.fixture
    def builder_service(self, mock_ukg_client):
        """Create a DriverBuilderService with mock client."""
        return DriverBuilderService(mock_ukg_client, debug=False)

    @pytest.fixture
    def sample_employment(self):
        """Sample employment details."""
        return {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "primaryJobCode": "4154",
            "jobDescription": "Field Tech",
            "employeeStatusCode": "A",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": None,
        }

    @pytest.fixture
    def sample_employee_employment(self):
        """Sample employee employment details."""
        return {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "primaryProjectCode": "PROJ001",
            "primaryProjectDescription": "Main Project",
        }

    @pytest.fixture
    def sample_person(self):
        """Sample person details."""
        return {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
            "addressLine1": "123 Main St",
            "addressCity": "Orlando",
            "addressState": "FL",
            "addressCountry": "USA",
            "addressZipCode": "32801",
        }

    def test_build_driver_success(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_employee_employment,
        sample_person,
    ):
        """Test successful driver build."""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_employee_employment_details.return_value = sample_employee_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        driver = builder_service.build_driver("12345", "J9A6Y")

        assert isinstance(driver, MotusDriver)
        assert driver.client_employee_id1 == "12345"
        assert driver.first_name == "John"
        assert driver.last_name == "Doe"
        assert driver.email == "john.doe@example.com"

    def test_build_driver_employee_not_found(
        self,
        builder_service,
        mock_ukg_client,
    ):
        """Test error when employee not found."""
        mock_ukg_client.get_employment_details.return_value = {}

        with pytest.raises(EmployeeNotFoundError) as exc_info:
            builder_service.build_driver("99999", "J9A6Y")

        assert "99999" in str(exc_info.value)

    def test_build_driver_no_employee_id(
        self,
        builder_service,
        mock_ukg_client,
        sample_person,
    ):
        """Test error when employee ID missing from employment details."""
        employment = {"employeeNumber": "12345", "companyID": "J9A6Y", "primaryJobCode": "4154"}
        mock_ukg_client.get_employment_details.return_value = employment
        mock_ukg_client.get_employee_employment_details.return_value = {}

        with pytest.raises(EmployeeNotFoundError) as exc_info:
            builder_service.build_driver("12345", "J9A6Y")

        assert "No employeeId found" in str(exc_info.value)

    def test_build_driver_unknown_job_code(
        self,
        builder_service,
        mock_ukg_client,
        sample_employee_employment,
        sample_person,
    ):
        """Test error when job code doesn't map to program."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "primaryJobCode": "9999",  # Unknown job code
            "employeeStatusCode": "A",
        }
        mock_ukg_client.get_employment_details.return_value = employment
        mock_ukg_client.get_employee_employment_details.return_value = sample_employee_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        with pytest.raises(ProgramNotFoundError) as exc_info:
            builder_service.build_driver("12345", "J9A6Y")

        assert "No programId found" in str(exc_info.value)

    def test_build_driver_with_supervisor(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_employee_employment,
        sample_person,
    ):
        """Test driver build with supervisor information."""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_employee_employment_details.return_value = sample_employee_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_supervisor_details.return_value = {
            "supervisorFirstName": "Jane",
            "supervisorLastName": "Manager",
        }

        driver = builder_service.build_driver("12345", "J9A6Y")

        # Manager name is stored in custom variables
        manager_cv = next(
            (cv for cv in driver.custom_variables if cv.name == "Manager Name"),
            None
        )
        assert manager_cv is not None
        assert manager_cv.value == "Jane Manager"

    def test_build_driver_to_payload(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_employee_employment,
        sample_person,
    ):
        """Test building driver and converting to payload."""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_employee_employment_details.return_value = sample_employee_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        driver = builder_service.build_driver("12345", "J9A6Y")
        payload = driver.to_api_payload()

        assert isinstance(payload, dict)
        assert payload["clientEmployeeId1"] == "12345"
        assert payload["firstName"] == "John"
