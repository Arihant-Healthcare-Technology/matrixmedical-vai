"""Tests for MotusDriver domain model."""

import pytest
from src.domain.models import MotusDriver, CustomVariable
from src.domain.models.program import ProgramType, resolve_program_id_from_job_code


class TestMotusDriver:
    """Test cases for MotusDriver domain model."""

    @pytest.fixture
    def valid_driver_data(self):
        """Sample valid driver data."""
        return {
            "client_employee_id1": "12345",
            "program_id": ProgramType.CPM.value,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "address1": "123 Main St",
            "city": "Orlando",
            "state_province": "FL",
            "country": "USA",
            "postal_code": "32801",
            "start_date": "2020-01-15",
        }

    @pytest.fixture
    def sample_driver(self, valid_driver_data):
        """Create a sample driver instance."""
        return MotusDriver(**valid_driver_data)

    def test_create_driver_with_valid_data(self, valid_driver_data):
        """Test creating a driver with valid data."""
        driver = MotusDriver(**valid_driver_data)

        assert driver.client_employee_id1 == "12345"
        assert driver.program_id == ProgramType.CPM.value
        assert driver.first_name == "John"
        assert driver.last_name == "Doe"
        assert driver.email == "john.doe@example.com"

    def test_validate_valid_driver(self, sample_driver):
        """Test validation passes for valid driver."""
        errors = sample_driver.validate()
        assert len(errors) == 0

    def test_validate_missing_employee_id(self, valid_driver_data):
        """Test validation fails for missing employee ID."""
        valid_driver_data["client_employee_id1"] = ""
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("client_employee_id1" in e for e in errors)

    def test_validate_missing_email(self, valid_driver_data):
        """Test validation fails for missing email."""
        valid_driver_data["email"] = ""
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("email" in e for e in errors)

    def test_validate_invalid_email(self, valid_driver_data):
        """Test validation fails for invalid email."""
        valid_driver_data["email"] = "not-an-email"
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("email" in e for e in errors)

    def test_validate_missing_first_name(self, valid_driver_data):
        """Test validation fails for missing first name."""
        valid_driver_data["first_name"] = ""
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("first_name" in e for e in errors)

    def test_validate_missing_last_name(self, valid_driver_data):
        """Test validation fails for missing last name."""
        valid_driver_data["last_name"] = ""
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("last_name" in e for e in errors)

    def test_validate_missing_program_id(self, valid_driver_data):
        """Test validation fails for missing program ID."""
        valid_driver_data["program_id"] = 0
        driver = MotusDriver(**valid_driver_data)

        errors = driver.validate()
        assert len(errors) > 0
        assert any("program_id" in e for e in errors)

    def test_to_api_payload_format(self, sample_driver):
        """Test API payload has correct format."""
        payload = sample_driver.to_api_payload()

        assert payload["clientEmployeeId1"] == "12345"
        assert payload["programId"] == ProgramType.CPM.value
        assert payload["firstName"] == "John"
        assert payload["lastName"] == "Doe"
        assert payload["email"] == "john.doe@example.com"
        assert payload["address1"] == "123 Main St"
        assert payload["city"] == "Orlando"
        assert payload["stateProvince"] == "FL"

    def test_to_api_payload_custom_variables(self, sample_driver):
        """Test API payload includes custom variables."""
        sample_driver.custom_variables = [
            CustomVariable(name="Job Code", value="4154"),
            CustomVariable(name="Project Code", value="PROJ001"),
        ]

        payload = sample_driver.to_api_payload()

        assert "customVariables" in payload
        assert len(payload["customVariables"]) == 2
        assert payload["customVariables"][0]["name"] == "Job Code"
        assert payload["customVariables"][0]["value"] == "4154"

    def test_to_api_payload_excludes_empty_values(self, valid_driver_data):
        """Test API payload excludes null and empty values."""
        valid_driver_data["address2"] = None
        valid_driver_data["alternate_phone"] = ""
        valid_driver_data["end_date"] = None
        valid_driver_data["client_employee_id2"] = None
        driver = MotusDriver(**valid_driver_data)

        payload = driver.to_api_payload()

        # These should NOT be in the payload
        assert "address2" not in payload
        assert "alternatePhone" not in payload
        assert "endDate" not in payload
        assert "clientEmployeeId2" not in payload

        # Required fields should still be present
        assert "clientEmployeeId1" in payload
        assert "firstName" in payload
        assert "email" in payload

    def test_to_api_payload_excludes_zero_annual_miles(self, valid_driver_data):
        """Test API payload excludes annualBusinessMiles when 0."""
        valid_driver_data["annual_business_miles"] = 0
        driver = MotusDriver(**valid_driver_data)

        payload = driver.to_api_payload()

        # annualBusinessMiles=0 should be excluded (Motus uses program default)
        assert "annualBusinessMiles" not in payload

    def test_to_api_payload_includes_nonzero_annual_miles(self, valid_driver_data):
        """Test API payload includes annualBusinessMiles when non-zero."""
        valid_driver_data["annual_business_miles"] = 15000
        driver = MotusDriver(**valid_driver_data)

        payload = driver.to_api_payload()

        assert "annualBusinessMiles" in payload
        assert payload["annualBusinessMiles"] == 15000

    def test_to_api_payload_excludes_empty_custom_variables(self, sample_driver):
        """Test API payload excludes custom variables with empty values."""
        sample_driver.custom_variables = [
            CustomVariable(name="Job Code", value="4154"),
            CustomVariable(name="Empty Var", value=""),
            CustomVariable(name="Whitespace Var", value="   "),
            CustomVariable(name="Project", value="PROJ001"),
        ]

        payload = sample_driver.to_api_payload()

        # Should only have 2 custom variables (non-empty ones)
        assert "customVariables" in payload
        assert len(payload["customVariables"]) == 2
        names = [cv["name"] for cv in payload["customVariables"]]
        assert "Job Code" in names
        assert "Project" in names
        assert "Empty Var" not in names
        assert "Whitespace Var" not in names

    def test_to_api_payload_no_custom_variables_when_all_empty(self, sample_driver):
        """Test API payload excludes customVariables key when all are empty."""
        sample_driver.custom_variables = [
            CustomVariable(name="Empty1", value=""),
            CustomVariable(name="Empty2", value="   "),
        ]

        payload = sample_driver.to_api_payload()

        # customVariables key should not be present when all values are empty
        assert "customVariables" not in payload

    def test_from_ukg_data(self):
        """Test creating driver from UKG API data."""
        person = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
            "addressLine1": "123 Main St",
            "addressCity": "Orlando",
            "addressState": "FL",
            "addressCountry": "USA",
            "addressZipCode": "32801",
            "homePhone": "555-123-4567",
        }
        employment_details = {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "primaryJobCode": "4154",
            "jobDescription": "Field Tech",
            "employeeStatusCode": "A",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": None,
        }

        driver = MotusDriver.from_ukg_data(
            employee_number="12345",
            program_id=ProgramType.CPM.value,
            person=person,
            employment_details=employment_details,
        )

        assert driver.client_employee_id1 == "12345"
        assert driver.first_name == "John"
        assert driver.last_name == "Doe"
        assert driver.email == "john.doe@example.com"
        assert driver.program_id == ProgramType.CPM.value
        assert driver.address1 == "123 Main St"

    def test_from_ukg_data_with_supervisor(self):
        """Test creating driver from UKG data with supervisor name."""
        person = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }
        employment_details = {
            "primaryJobCode": "4154",
            "originalHireDate": "2020-01-15T00:00:00Z",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number="12345",
            program_id=ProgramType.CPM.value,
            person=person,
            employment_details=employment_details,
            supervisor_name="Jane Manager",
        )

        # Check custom variables include supervisor name
        manager_cv = next(
            (cv for cv in driver.custom_variables if cv.name == "Manager Name"),
            None
        )
        assert manager_cv is not None
        assert manager_cv.value == "Jane Manager"

    def test_from_ukg_data_with_location(self):
        """Test creating driver from UKG data with location."""
        person = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }
        employment_details = {
            "primaryJobCode": "4154",
            "primaryWorkLocationCode": "LOC001",
        }
        location = {
            "description": "Florida Office",
            "state": "FL",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number="12345",
            program_id=ProgramType.CPM.value,
            person=person,
            employment_details=employment_details,
            location=location,
        )

        # Check location custom variables
        loc_code_cv = next(
            (cv for cv in driver.custom_variables if cv.name == "Location Code"),
            None
        )
        assert loc_code_cv is not None
        assert loc_code_cv.value == "LOC001"

    def test_full_name_property(self, sample_driver):
        """Test full_name property."""
        assert sample_driver.full_name == "John Doe"

    def test_program_type_property(self, sample_driver):
        """Test program_type property."""
        assert sample_driver.program_type == ProgramType.CPM

    def test_program_type_property_favr(self, valid_driver_data):
        """Test program_type property for FAVR."""
        valid_driver_data["program_id"] = ProgramType.FAVR.value
        driver = MotusDriver(**valid_driver_data)
        assert driver.program_type == ProgramType.FAVR

    def test_program_type_property_unknown(self, valid_driver_data):
        """Test program_type property for unknown program ID."""
        valid_driver_data["program_id"] = 99999
        driver = MotusDriver(**valid_driver_data)
        assert driver.program_type is None

    def test_is_valid_true(self, sample_driver):
        """Test is_valid returns True for valid driver."""
        assert sample_driver.is_valid() is True

    def test_is_valid_false(self, valid_driver_data):
        """Test is_valid returns False for invalid driver."""
        valid_driver_data["email"] = ""
        driver = MotusDriver(**valid_driver_data)
        assert driver.is_valid() is False

    def test_to_dict(self, sample_driver):
        """Test to_dict conversion."""
        result = sample_driver.to_dict()

        assert result["client_employee_id1"] == "12345"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email"] == "john.doe@example.com"

    def test_phone_normalization(self, valid_driver_data):
        """Test phone number normalization."""
        valid_driver_data["phone"] = "5551234567"
        driver = MotusDriver(**valid_driver_data)

        assert driver.phone == "555-123-4567"

    def test_phone_normalization_already_formatted(self, valid_driver_data):
        """Test phone number already in correct format."""
        valid_driver_data["phone"] = "555-123-4567"
        driver = MotusDriver(**valid_driver_data)

        assert driver.phone == "555-123-4567"

    def test_email_normalization(self, valid_driver_data):
        """Test email normalization to lowercase."""
        valid_driver_data["email"] = "John.Doe@Example.COM"
        driver = MotusDriver(**valid_driver_data)

        assert driver.email == "john.doe@example.com"


class TestCustomVariable:
    """Test cases for CustomVariable."""

    def test_create_custom_variable(self):
        """Test creating a custom variable."""
        cv = CustomVariable(name="Job Code", value="4154")

        assert cv.name == "Job Code"
        assert cv.value == "4154"

    def test_to_dict(self):
        """Test converting to dictionary."""
        cv = CustomVariable(name="Job Code", value="4154")
        result = cv.to_dict()

        assert result == {"name": "Job Code", "value": "4154"}


class TestProgramType:
    """Test cases for ProgramType enum."""

    def test_favr_value(self):
        """Test FAVR program ID."""
        assert ProgramType.FAVR.value == 21232

    def test_cpm_value(self):
        """Test CPM program ID."""
        assert ProgramType.CPM.value == 21233


class TestResolveJobCode:
    """Test cases for resolve_program_id_from_job_code function."""

    def test_resolve_favr_job_code(self):
        """Test resolving FAVR program from job code."""
        program_id = resolve_program_id_from_job_code("1103")
        assert program_id == ProgramType.FAVR.value

    def test_resolve_cpm_job_code(self):
        """Test resolving CPM program from job code."""
        program_id = resolve_program_id_from_job_code("4154")
        assert program_id == ProgramType.CPM.value

    def test_resolve_unknown_job_code(self):
        """Test unknown job code returns None."""
        program_id = resolve_program_id_from_job_code("9999")
        assert program_id is None

    def test_resolve_unknown_job_code_with_default(self):
        """Test unknown job code returns default value."""
        program_id = resolve_program_id_from_job_code("9999", default=ProgramType.CPM.value)
        assert program_id == ProgramType.CPM.value

    def test_resolve_none_job_code(self):
        """Test None job code returns None."""
        program_id = resolve_program_id_from_job_code(None)
        assert program_id is None

    def test_resolve_none_job_code_with_default(self):
        """Test None job code returns default value."""
        program_id = resolve_program_id_from_job_code(None, default=ProgramType.FAVR.value)
        assert program_id == ProgramType.FAVR.value

    def test_resolve_job_code_strips_whitespace(self):
        """Test job code with whitespace is handled."""
        program_id = resolve_program_id_from_job_code(" 4154 ")
        assert program_id == ProgramType.CPM.value

    def test_resolve_job_code_strips_leading_zeros(self):
        """Test job code with leading zeros."""
        # Assuming "01103" should match "1103"
        program_id = resolve_program_id_from_job_code("01103")
        assert program_id == ProgramType.FAVR.value
