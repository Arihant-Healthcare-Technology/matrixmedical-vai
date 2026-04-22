"""Tests for UserBuilderService."""

import pytest
from unittest.mock import MagicMock

from src.application.services import UserBuilderService
from src.domain.models import TravelPerkUser
from src.domain.exceptions import EmployeeNotFoundError, UserValidationError


class TestUserBuilderService:
    """Test cases for UserBuilderService."""

    @pytest.fixture
    def mock_ukg_client(self):
        """Create a mock UKG client."""
        client = MagicMock()
        # Default to empty string for org level description
        client.get_org_level_description.return_value = ""
        return client

    @pytest.fixture
    def builder_service(self, mock_ukg_client):
        """Create a UserBuilderService with mock client."""
        return UserBuilderService(mock_ukg_client, debug=False)

    @pytest.fixture
    def sample_employment(self):
        """Sample employment details."""
        return {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "primaryProjectCode": "PROJ001",
            "employeeStatusCode": "A",
            "terminationDate": None,
        }

    @pytest.fixture
    def sample_person(self):
        """Sample person details."""
        return {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

    def test_build_user_success(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test successful user build."""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        user = builder_service.build_user("12345", "J9A6Y")

        assert isinstance(user, TravelPerkUser)
        assert user.external_id == "12345"
        assert user.user_name == "john.doe@example.com"
        assert user.name.given_name == "John"
        assert user.name.family_name == "Doe"

    def test_build_user_employee_not_found(
        self,
        builder_service,
        mock_ukg_client,
    ):
        """Test error when employee not found."""
        mock_ukg_client.get_employment_details.return_value = {}

        with pytest.raises(EmployeeNotFoundError) as exc_info:
            builder_service.build_user("99999", "J9A6Y")

        assert "99999" in str(exc_info.value)

    def test_build_user_missing_email(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test error when email is missing."""
        sample_person["emailAddress"] = ""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        with pytest.raises(UserValidationError) as exc_info:
            builder_service.build_user("12345", "J9A6Y")

        assert "email" in str(exc_info.value).lower()

    def test_build_user_payload(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test build_user_payload returns dict."""
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person

        payload = builder_service.build_user_payload("12345", "J9A6Y")

        assert isinstance(payload, dict)
        assert payload["externalId"] == "12345"
        assert payload["userName"] == "john.doe@example.com"
        assert "schemas" in payload

    def test_build_user_includes_cost_center(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test cost center is included in user from org level description."""
        sample_employment["orgLevel4Code"] = "730"
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = "730 - Test Department"

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center == "730 - Test Department"

    def test_build_user_terminated_employee(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test terminated employee is marked inactive."""
        sample_employment["employeeStatusCode"] = "T"
        sample_employment["terminationDate"] = "2023-12-31"
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.active is False

    def test_build_user_with_org_level_description(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test user is built with org level description as cost center."""
        sample_employment["orgLevel4Code"] = "730"
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = "730 - Southeast Clinical"

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center == "730 - Southeast Clinical"
        mock_ukg_client.get_org_level_description.assert_called_once_with(4, "730")

    def test_build_user_fallback_when_no_description(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test fallback to orgLevel4Code when no description found."""
        sample_employment["orgLevel4Code"] = "730"
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center == "730"

    def test_build_user_no_org_level4_code(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test handling when orgLevel4Code is empty."""
        sample_employment["orgLevel4Code"] = ""
        sample_employment.pop("primaryProjectCode", None)
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center is None
        mock_ukg_client.get_org_level_description.assert_called_once_with(4, "")

    # --- Additional Negative Scenario Tests ---

    def test_build_user_org_level4_code_is_none(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test handling when orgLevel4Code is None."""
        sample_employment["orgLevel4Code"] = None
        sample_employment.pop("primaryProjectCode", None)
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center is None

    def test_build_user_org_level4_code_missing(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test handling when orgLevel4Code key doesn't exist."""
        sample_employment.pop("orgLevel4Code", None)
        sample_employment.pop("primaryProjectCode", None)
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center is None
        mock_ukg_client.get_org_level_description.assert_called_once_with(4, "")

    def test_build_user_org_level4_code_whitespace(
        self,
        builder_service,
        mock_ukg_client,
        sample_employment,
        sample_person,
    ):
        """Test handling when orgLevel4Code is whitespace only."""
        sample_employment["orgLevel4Code"] = "   "
        sample_employment.pop("primaryProjectCode", None)
        mock_ukg_client.get_employment_details.return_value = sample_employment
        mock_ukg_client.get_person_details.return_value = sample_person
        mock_ukg_client.get_org_level_description.return_value = ""

        user = builder_service.build_user("12345", "J9A6Y")

        assert user.cost_center is None
        # Whitespace should be stripped before calling
        mock_ukg_client.get_org_level_description.assert_called_once_with(4, "")
