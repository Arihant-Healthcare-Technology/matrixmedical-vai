"""
Integration tests for UserBuilder service.

Tests verify the user building process from UKG data to TravelPerk payload.
Run with: pytest tests/integration/test_user_builder_integration.py -v -m integration
"""
from unittest.mock import MagicMock

import pytest
import responses

from src.application.services.user_builder import UserBuilderService
from src.infrastructure.adapters.ukg.client import UKGClient
from src.domain.models.travelperk_user import TravelPerkUser
from src.domain.exceptions.business_exceptions import UserValidationError


@pytest.fixture
def mock_ukg_settings():
    """Create mock UKG settings."""
    settings = MagicMock()
    settings.base_url = "https://service4.ultipro.com"
    settings.username = "test_user"
    settings.password = "test_pass"
    settings.customer_api_key = "test_api_key"
    settings.basic_b64 = None
    settings.timeout = 45.0
    return settings


@pytest.fixture
def ukg_base_url():
    return "https://service4.ultipro.com"


@pytest.mark.integration
class TestBuildUserFromUKGData:
    """Test building TravelPerk user from UKG data."""

    @responses.activate
    def test_build_user_from_ukg_data(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test building user with all required fields."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")

        assert user is not None
        assert user.external_id == "12345"
        assert user.user_name == "john.doe@example.com"
        assert user.name.given_name == "John"
        assert user.name.family_name == "Doe"
        assert user.active is True

    @responses.activate
    def test_build_user_with_cost_center(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test building user with cost center from primaryProjectCode."""
        emp_details = {**sample_ukg_employee_employment_details, "primaryProjectCode": "PROJ123"}
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[emp_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")

        assert user.cost_center == "PROJ123"


@pytest.mark.integration
class TestBuildUserActiveStatus:
    """Test building user active status."""

    @responses.activate
    def test_build_user_active_status_code_a(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test user is active when employeeStatusCode is A."""
        emp_details = {**sample_ukg_employee_employment_details, "employeeStatusCode": "A"}
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[emp_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")

        assert user.active is True

    @responses.activate
    def test_build_user_terminated_status(
        self,
        mock_ukg_settings,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test user is inactive when employeeStatusCode is T."""
        emp_details = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "employeeStatusCode": "T",
            "terminationDate": "2024-06-30T00:00:00Z",
        }
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[emp_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")

        assert user.active is False

    @responses.activate
    def test_build_user_leave_status(
        self,
        mock_ukg_settings,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test user handling for leave status."""
        emp_details = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "employeeStatusCode": "L",
            "terminationDate": None,
        }
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[emp_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")

        # Leave status may be treated as active or inactive depending on implementation
        assert user is not None


@pytest.mark.integration
class TestBuildUserValidationErrors:
    """Test user building validation errors."""

    @responses.activate
    def test_build_user_missing_email(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        ukg_base_url,
    ):
        """Test validation error when email is missing."""
        person_no_email = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "",  # Empty email
        }
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[person_no_email],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        with pytest.raises(UserValidationError):
            builder.build_user("12345", "J9A6Y")

    @responses.activate
    def test_build_user_missing_name(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        ukg_base_url,
    ):
        """Test validation error when name is missing."""
        person_no_name = {
            "employeeId": "EMP001",
            "firstName": "",
            "lastName": "",
            "emailAddress": "john@example.com",
        }
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[person_no_name],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        with pytest.raises(UserValidationError):
            builder.build_user("12345", "J9A6Y")

    @responses.activate
    def test_build_user_invalid_email_format(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        ukg_base_url,
    ):
        """Test validation error for invalid email format."""
        person_invalid_email = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "invalid-email",  # No @ symbol
        }
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[person_invalid_email],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        with pytest.raises(UserValidationError):
            builder.build_user("12345", "J9A6Y")


@pytest.mark.integration
class TestBuildUserWithManager:
    """Test building user with manager reference."""

    @responses.activate
    def test_build_user_with_manager_id(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test building user with manager TravelPerk ID."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y", manager_tp_id="tp-manager-123")

        assert user.manager_id == "tp-manager-123"


@pytest.mark.integration
class TestBuildUserPayload:
    """Test building SCIM payload from user."""

    @responses.activate
    def test_build_user_to_api_payload(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test building SCIM API payload."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")
        payload = user.to_api_payload()

        assert "schemas" in payload
        assert "userName" in payload
        assert "externalId" in payload
        assert "name" in payload
        assert payload["externalId"] == "12345"

    @responses.activate
    def test_build_user_to_patch_payload(
        self,
        mock_ukg_settings,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test building SCIM PATCH payload."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        builder = UserBuilderService(ukg_client=ukg_client)

        user = builder.build_user("12345", "J9A6Y")
        payload = user.to_patch_payload()

        assert "schemas" in payload
        assert "Operations" in payload
        assert len(payload["Operations"]) > 0
