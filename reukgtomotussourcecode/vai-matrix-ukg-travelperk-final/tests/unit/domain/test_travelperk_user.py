"""Tests for TravelPerkUser domain model."""

import pytest
from src.domain.models import TravelPerkUser, UserName, UserEmail
from src.domain.models.employment_status import EmploymentStatus


class TestTravelPerkUser:
    """Test cases for TravelPerkUser domain model."""

    @pytest.fixture
    def valid_user_data(self):
        """Sample valid user data."""
        return {
            "external_id": "12345",
            "user_name": "john.doe@example.com",
            "name": UserName(given_name="John", family_name="Doe"),
            "active": True,
        }

    @pytest.fixture
    def sample_user(self, valid_user_data):
        """Create a sample user instance."""
        return TravelPerkUser(**valid_user_data)

    def test_create_user_with_valid_data(self, valid_user_data):
        """Test creating a user with valid data."""
        user = TravelPerkUser(**valid_user_data)

        assert user.external_id == "12345"
        assert user.user_name == "john.doe@example.com"
        assert user.name.given_name == "John"
        assert user.name.family_name == "Doe"
        assert user.active is True

    def test_validate_valid_user(self, sample_user):
        """Test validation passes for valid user."""
        errors = sample_user.validate()
        assert len(errors) == 0

    def test_validate_missing_external_id(self, valid_user_data):
        """Test validation fails for missing external ID."""
        valid_user_data["external_id"] = ""
        user = TravelPerkUser(**valid_user_data)

        errors = user.validate()
        assert len(errors) > 0
        assert any("external_id" in e for e in errors)

    def test_validate_missing_user_name(self, valid_user_data):
        """Test validation fails for missing userName (email)."""
        valid_user_data["user_name"] = ""
        user = TravelPerkUser(**valid_user_data)

        errors = user.validate()
        assert len(errors) > 0
        assert any("user_name" in e for e in errors)

    def test_validate_invalid_email(self, valid_user_data):
        """Test validation fails for invalid email."""
        valid_user_data["user_name"] = "not-an-email"
        user = TravelPerkUser(**valid_user_data)

        errors = user.validate()
        assert len(errors) > 0
        assert any("email" in e.lower() for e in errors)

    def test_validate_missing_first_name(self, valid_user_data):
        """Test validation fails for missing first name."""
        valid_user_data["name"] = UserName(given_name="", family_name="Doe")
        user = TravelPerkUser(**valid_user_data)

        errors = user.validate()
        assert len(errors) > 0
        assert any("given_name" in e for e in errors)

    def test_validate_missing_last_name(self, valid_user_data):
        """Test validation fails for missing last name."""
        valid_user_data["name"] = UserName(given_name="John", family_name="")
        user = TravelPerkUser(**valid_user_data)

        errors = user.validate()
        assert len(errors) > 0
        assert any("family_name" in e for e in errors)

    def test_to_api_payload_format(self, sample_user):
        """Test API payload has correct SCIM format."""
        payload = sample_user.to_api_payload()

        assert "schemas" in payload
        assert len(payload["schemas"]) == 3
        assert payload["userName"] == "john.doe@example.com"
        assert payload["externalId"] == "12345"
        assert payload["name"]["givenName"] == "John"
        assert payload["name"]["familyName"] == "Doe"
        assert payload["active"] is True

    def test_to_api_payload_with_cost_center(self, sample_user):
        """Test API payload includes cost center."""
        sample_user.cost_center = "PROJ001"
        payload = sample_user.to_api_payload()

        enterprise_ext = payload.get(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {}
        )
        assert enterprise_ext.get("costCenter") == "PROJ001"

    def test_to_api_payload_with_manager(self, sample_user):
        """Test API payload includes manager."""
        sample_user.manager_id = "MGR123"
        payload = sample_user.to_api_payload()

        enterprise_ext = payload.get(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {}
        )
        assert enterprise_ext.get("manager") == {"value": "MGR123"}

    def test_to_patch_operations(self, sample_user):
        """Test PATCH operations generation."""
        operations = sample_user.to_patch_operations()

        assert len(operations) >= 3
        op_paths = [op["path"] for op in operations]
        assert "active" in op_paths
        assert "name.givenName" in op_paths
        assert "name.familyName" in op_paths

    def test_to_patch_payload(self, sample_user):
        """Test PATCH payload format."""
        payload = sample_user.to_patch_payload()

        assert "schemas" in payload
        assert "urn:ietf:params:scim:api:messages:2.0:PatchOp" in payload["schemas"]
        assert "Operations" in payload
        assert len(payload["Operations"]) > 0

    def test_from_ukg_data(self):
        """Test creating user from UKG API data."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "730",
            "employeeStatusCode": "A",
            "terminationDate": None,
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(
            employment,
            person,
            org_level4_description="730 - Test Department",
        )

        assert user.external_id == "12345"
        assert user.user_name == "john.doe@example.com"
        assert user.name.given_name == "John"
        assert user.name.family_name == "Doe"
        assert user.active is True
        assert user.cost_center == "730 - Test Department"

    def test_from_ukg_data_terminated(self):
        """Test terminated employee is marked inactive."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "730",
            "employeeStatusCode": "T",
            "terminationDate": "2023-12-31",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person)

        assert user.active is False

    def test_from_ukg_data_with_org_level_description(self):
        """Test creating user with org_level4_description parameter."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "730",
            "employeeStatusCode": "A",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(
            employment,
            person,
            org_level4_description="730 - Southeast Clinical Part-time",
        )

        assert user.cost_center == "730 - Southeast Clinical Part-time"

    def test_from_ukg_data_fallback_to_org_level4_code(self):
        """Test fallback to orgLevel4Code when no description provided."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "730",
            "employeeStatusCode": "A",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person, org_level4_description="")

        assert user.cost_center == "730"

    def test_from_ukg_data_no_cost_center(self):
        """Test no cost_center when both orgLevel4Code and description are empty."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "",
            "employeeStatusCode": "A",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person, org_level4_description="")

        assert user.cost_center is None

    # --- Additional Negative Scenario Tests ---

    def test_from_ukg_data_org_level4_code_is_none(self):
        """Test handling when orgLevel4Code is None."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": None,
            "employeeStatusCode": "A",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person, org_level4_description="")

        assert user.cost_center is None

    def test_from_ukg_data_org_level4_code_missing(self):
        """Test handling when orgLevel4Code key doesn't exist."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "employeeStatusCode": "A",
            # No orgLevel4Code key
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person, org_level4_description="")

        assert user.cost_center is None

    def test_from_ukg_data_org_level4_code_whitespace(self):
        """Test handling when orgLevel4Code is whitespace only."""
        employment = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "orgLevel4Code": "   ",
            "employeeStatusCode": "A",
        }
        person = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }

        user = TravelPerkUser.from_ukg_data(employment, person, org_level4_description="")

        # Whitespace is stripped, resulting in empty string -> None
        assert user.cost_center is None


class TestUserName:
    """Test cases for UserName."""

    def test_create_user_name(self):
        """Test creating a user name."""
        name = UserName(given_name="John", family_name="Doe")

        assert name.given_name == "John"
        assert name.family_name == "Doe"

    def test_to_dict(self):
        """Test converting to SCIM format."""
        name = UserName(given_name="John", family_name="Doe")
        result = name.to_dict()

        assert result == {"givenName": "John", "familyName": "Doe"}


class TestUserEmail:
    """Test cases for UserEmail."""

    def test_create_user_email(self):
        """Test creating a user email."""
        email = UserEmail(value="john@example.com")

        assert email.value == "john@example.com"
        assert email.email_type == "work"
        assert email.primary is True

    def test_to_dict(self):
        """Test converting to SCIM format."""
        email = UserEmail(value="john@example.com")
        result = email.to_dict()

        assert result == {
            "value": "john@example.com",
            "type": "work",
            "primary": True,
        }


class TestEmploymentStatus:
    """Test cases for EmploymentStatus enum."""

    def test_active_status(self):
        """Test ACTIVE status."""
        assert EmploymentStatus.ACTIVE.value == "A"
        assert EmploymentStatus.ACTIVE.is_active is True

    def test_terminated_status(self):
        """Test TERMINATED status."""
        assert EmploymentStatus.TERMINATED.value == "T"
        assert EmploymentStatus.TERMINATED.is_active is False

    def test_from_code_active(self):
        """Test creating from code string."""
        status = EmploymentStatus.from_code("A")
        assert status == EmploymentStatus.ACTIVE
        assert status.is_active is True

    def test_from_code_terminated(self):
        """Test creating from terminated code."""
        status = EmploymentStatus.from_code("T")
        assert status == EmploymentStatus.TERMINATED
        assert status.is_active is False

    def test_from_code_unknown(self):
        """Test unknown code defaults to INACTIVE."""
        status = EmploymentStatus.from_code("X")
        assert status == EmploymentStatus.INACTIVE
        assert status.is_active is False

    def test_from_code_case_insensitive(self):
        """Test code matching is case insensitive."""
        status = EmploymentStatus.from_code("a")
        assert status == EmploymentStatus.ACTIVE
