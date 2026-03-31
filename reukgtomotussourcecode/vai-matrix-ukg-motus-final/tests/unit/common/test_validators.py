"""
Tests for the validators module.

Tests cover:
- ValidationResult dataclass
- ValidationResults collection
- Simple validation functions
- Detailed validation functions
- EntityValidator class
- Batch validation
"""

import pytest
from datetime import datetime

from common.validators import (
    ValidationResult,
    ValidationResults,
    validate_email,
    validate_state_code,
    validate_country_code,
    validate_phone,
    validate_employee_number,
    validate_date_string,
    validate_required,
    validate_length,
    validate_email_detailed,
    validate_state_code_detailed,
    validate_employee_number_detailed,
    EntityValidator,
    validate_batch,
    US_STATES,
    COUNTRY_CODES,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_init_valid(self):
        """Test creating a valid result."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.error is None

    def test_init_invalid_with_error(self):
        """Test creating an invalid result with error."""
        result = ValidationResult(valid=False, error="Test error")
        assert result.valid is False
        assert result.error == "Test error"

    def test_init_with_field_and_value(self):
        """Test creating result with field and value."""
        result = ValidationResult(
            valid=False,
            error="Invalid",
            field="email",
            value="bad@email",
        )
        assert result.field == "email"
        assert result.value == "bad@email"

    def test_bool_valid(self):
        """Test boolean conversion for valid result."""
        result = ValidationResult(valid=True)
        assert bool(result) is True

    def test_bool_invalid(self):
        """Test boolean conversion for invalid result."""
        result = ValidationResult(valid=False)
        assert bool(result) is False

    def test_success_factory(self):
        """Test success factory method."""
        result = ValidationResult.success(field="test", value="value")
        assert result.valid is True
        assert result.field == "test"
        assert result.value == "value"

    def test_failure_factory(self):
        """Test failure factory method."""
        result = ValidationResult.failure(
            error="Error message",
            field="test",
            value="bad_value",
        )
        assert result.valid is False
        assert result.error == "Error message"
        assert result.field == "test"
        assert result.value == "bad_value"


class TestValidationResults:
    """Tests for ValidationResults collection."""

    def test_init_empty(self):
        """Test empty initialization."""
        results = ValidationResults()
        assert len(results.results) == 0
        assert results.valid is True

    def test_add_result(self):
        """Test adding results."""
        results = ValidationResults()
        results.add(ValidationResult(valid=True))
        assert len(results.results) == 1

    def test_valid_all_pass(self):
        """Test valid property when all pass."""
        results = ValidationResults()
        results.add(ValidationResult.success())
        results.add(ValidationResult.success())
        assert results.valid is True

    def test_valid_one_fails(self):
        """Test valid property when one fails."""
        results = ValidationResults()
        results.add(ValidationResult.success())
        results.add(ValidationResult.failure("Error"))
        assert results.valid is False

    def test_errors_property(self):
        """Test errors property returns failed results."""
        results = ValidationResults()
        results.add(ValidationResult.success())
        results.add(ValidationResult.failure("Error 1"))
        results.add(ValidationResult.failure("Error 2"))

        errors = results.errors
        assert len(errors) == 2

    def test_error_messages_property(self):
        """Test error_messages property."""
        results = ValidationResults()
        results.add(ValidationResult.failure("Error 1"))
        results.add(ValidationResult.failure("Error 2"))

        messages = results.error_messages
        assert "Error 1" in messages
        assert "Error 2" in messages

    def test_bool_all_valid(self):
        """Test boolean conversion when all valid."""
        results = ValidationResults()
        results.add(ValidationResult.success())
        assert bool(results) is True

    def test_bool_some_invalid(self):
        """Test boolean conversion when some invalid."""
        results = ValidationResults()
        results.add(ValidationResult.failure("Error"))
        assert bool(results) is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        results = ValidationResults()
        results.add(ValidationResult.success(field="field1"))
        results.add(ValidationResult.failure("Error", field="field2", value="bad"))

        d = results.to_dict()
        assert d["valid"] is False
        assert d["total_checks"] == 2
        assert len(d["errors"]) == 1
        assert d["errors"][0]["field"] == "field2"


class TestValidateEmail:
    """Tests for email validation."""

    def test_valid_simple_email(self):
        """Test valid simple email."""
        assert validate_email("user@example.com") is True

    def test_valid_email_with_dots(self):
        """Test valid email with dots."""
        assert validate_email("first.last@example.com") is True

    def test_valid_email_with_plus(self):
        """Test valid email with plus."""
        assert validate_email("user+tag@example.com") is True

    def test_valid_email_subdomain(self):
        """Test valid email with subdomain."""
        assert validate_email("user@mail.example.com") is True

    def test_invalid_no_at(self):
        """Test invalid email without @."""
        assert validate_email("userexample.com") is False

    def test_invalid_no_domain(self):
        """Test invalid email without domain."""
        assert validate_email("user@") is False

    def test_invalid_no_tld(self):
        """Test invalid email without TLD."""
        assert validate_email("user@example") is False

    def test_invalid_empty(self):
        """Test invalid empty email."""
        assert validate_email("") is False

    def test_invalid_none(self):
        """Test invalid None email."""
        assert validate_email(None) is False

    def test_valid_email_with_whitespace_stripped(self):
        """Test email with whitespace is stripped."""
        assert validate_email("  user@example.com  ") is True


class TestValidateStateCode:
    """Tests for state code validation."""

    def test_valid_state_fl(self):
        """Test valid state FL."""
        assert validate_state_code("FL") is True

    def test_valid_state_ca(self):
        """Test valid state CA."""
        assert validate_state_code("CA") is True

    def test_valid_state_lowercase(self):
        """Test lowercase state is valid."""
        assert validate_state_code("ny") is True

    def test_valid_dc(self):
        """Test DC is valid."""
        assert validate_state_code("DC") is True

    def test_valid_territory_pr(self):
        """Test territory PR is valid."""
        assert validate_state_code("PR") is True

    def test_invalid_state(self):
        """Test invalid state code."""
        assert validate_state_code("XX") is False

    def test_empty_is_valid(self):
        """Test empty state is valid (optional field)."""
        assert validate_state_code("") is True

    def test_none_is_valid(self):
        """Test None state is valid (optional field)."""
        assert validate_state_code(None) is True

    def test_all_us_states(self):
        """Test all US states are valid."""
        for state in US_STATES:
            assert validate_state_code(state) is True


class TestValidateCountryCode:
    """Tests for country code validation."""

    def test_valid_us(self):
        """Test valid US country code."""
        assert validate_country_code("US") is True

    def test_valid_ca(self):
        """Test valid CA country code."""
        assert validate_country_code("CA") is True

    def test_valid_lowercase(self):
        """Test lowercase country code."""
        assert validate_country_code("gb") is True

    def test_invalid_country(self):
        """Test invalid country code."""
        assert validate_country_code("ZZ") is False

    def test_empty_is_valid(self):
        """Test empty is valid (optional field)."""
        assert validate_country_code("") is True

    def test_none_is_valid(self):
        """Test None is valid (optional field)."""
        assert validate_country_code(None) is True


class TestValidatePhone:
    """Tests for phone validation."""

    def test_valid_10_digit(self):
        """Test valid 10-digit phone."""
        assert validate_phone("5551234567") is True

    def test_valid_formatted(self):
        """Test valid formatted phone."""
        assert validate_phone("555-123-4567") is True

    def test_valid_with_area_code_parens(self):
        """Test valid with area code in parentheses."""
        assert validate_phone("(555) 123-4567") is True

    def test_valid_with_country_code(self):
        """Test valid with country code."""
        assert validate_phone("+1 555 123 4567") is True

    def test_invalid_too_short(self):
        """Test invalid too short phone."""
        assert validate_phone("555123") is False

    def test_empty_is_valid(self):
        """Test empty is valid (optional field)."""
        assert validate_phone("") is True

    def test_none_is_valid(self):
        """Test None is valid (optional field)."""
        assert validate_phone(None) is True


class TestValidateEmployeeNumber:
    """Tests for employee number validation."""

    def test_valid_numeric(self):
        """Test valid numeric employee number."""
        assert validate_employee_number("12345") is True

    def test_valid_alphanumeric(self):
        """Test valid alphanumeric employee number."""
        assert validate_employee_number("EMP001") is True

    def test_valid_mixed_case(self):
        """Test valid mixed case."""
        assert validate_employee_number("emp001ABC") is True

    def test_valid_max_length(self):
        """Test valid at max length."""
        assert validate_employee_number("A" * 20) is True

    def test_invalid_too_long(self):
        """Test invalid - too long."""
        assert validate_employee_number("A" * 21) is False

    def test_invalid_empty(self):
        """Test invalid empty."""
        assert validate_employee_number("") is False

    def test_invalid_none(self):
        """Test invalid None."""
        assert validate_employee_number(None) is False

    def test_invalid_special_chars(self):
        """Test invalid with special characters."""
        assert validate_employee_number("EMP-001") is False


class TestValidateDateString:
    """Tests for date string validation."""

    def test_valid_iso_format(self):
        """Test valid ISO format."""
        assert validate_date_string("2024-03-15") is True

    def test_valid_us_format(self):
        """Test valid US format."""
        assert validate_date_string("03/15/2024") is True

    def test_valid_iso_with_time(self):
        """Test valid ISO with time."""
        assert validate_date_string("2024-03-15T10:30:00") is True

    def test_valid_iso_with_z(self):
        """Test valid ISO with Z timezone."""
        assert validate_date_string("2024-03-15T10:30:00Z") is True

    def test_valid_iso_with_milliseconds(self):
        """Test valid ISO with milliseconds."""
        assert validate_date_string("2024-03-15T10:30:00.123Z") is True

    def test_invalid_format(self):
        """Test invalid format."""
        assert validate_date_string("March 15, 2024") is False

    def test_empty_is_valid(self):
        """Test empty is valid (optional field)."""
        assert validate_date_string("") is True

    def test_none_is_valid(self):
        """Test None is valid (optional field)."""
        assert validate_date_string(None) is True


class TestValidateRequired:
    """Tests for required field validation."""

    def test_valid_string(self):
        """Test valid string."""
        assert validate_required("value") is True

    def test_valid_number(self):
        """Test valid number."""
        assert validate_required(123) is True

    def test_valid_list(self):
        """Test valid list."""
        assert validate_required([1, 2, 3]) is True

    def test_invalid_none(self):
        """Test invalid None."""
        assert validate_required(None) is False

    def test_invalid_empty_string(self):
        """Test invalid empty string."""
        assert validate_required("") is False

    def test_invalid_whitespace_only(self):
        """Test invalid whitespace only."""
        assert validate_required("   ") is False

    def test_empty_string_allowed(self):
        """Test empty string allowed when flag set."""
        assert validate_required("", allow_empty_string=True) is True


class TestValidateLength:
    """Tests for length validation."""

    def test_valid_within_range(self):
        """Test valid within range."""
        assert validate_length("hello", min_length=1, max_length=10) is True

    def test_valid_at_min(self):
        """Test valid at minimum."""
        assert validate_length("a", min_length=1, max_length=10) is True

    def test_valid_at_max(self):
        """Test valid at maximum."""
        assert validate_length("a" * 10, min_length=1, max_length=10) is True

    def test_invalid_below_min(self):
        """Test invalid below minimum."""
        assert validate_length("ab", min_length=5) is False

    def test_invalid_above_max(self):
        """Test invalid above maximum."""
        assert validate_length("hello world", max_length=5) is False

    def test_empty_with_zero_min(self):
        """Test empty with zero minimum is valid."""
        assert validate_length("", min_length=0) is True

    def test_empty_with_nonzero_min(self):
        """Test empty with nonzero minimum is invalid."""
        assert validate_length("", min_length=1) is False


class TestValidateEmailDetailed:
    """Tests for detailed email validation."""

    def test_valid_returns_success(self):
        """Test valid email returns success."""
        result = validate_email_detailed("user@example.com")
        assert result.valid is True
        assert result.field == "email"

    def test_empty_returns_failure(self):
        """Test empty email returns failure."""
        result = validate_email_detailed("")
        assert result.valid is False
        assert "required" in result.error.lower()

    def test_invalid_returns_failure(self):
        """Test invalid email returns failure."""
        result = validate_email_detailed("invalid-email")
        assert result.valid is False
        assert "format" in result.error.lower()


class TestValidateStateCodeDetailed:
    """Tests for detailed state code validation."""

    def test_valid_returns_success(self):
        """Test valid state returns success."""
        result = validate_state_code_detailed("FL")
        assert result.valid is True

    def test_empty_returns_success(self):
        """Test empty state returns success (optional)."""
        result = validate_state_code_detailed("")
        assert result.valid is True

    def test_invalid_returns_failure(self):
        """Test invalid state returns failure."""
        result = validate_state_code_detailed("XX")
        assert result.valid is False
        assert "Invalid state code" in result.error


class TestValidateEmployeeNumberDetailed:
    """Tests for detailed employee number validation."""

    def test_valid_returns_success(self):
        """Test valid employee number returns success."""
        result = validate_employee_number_detailed("12345")
        assert result.valid is True

    def test_empty_returns_failure(self):
        """Test empty returns failure."""
        result = validate_employee_number_detailed("")
        assert result.valid is False
        assert "required" in result.error.lower()

    def test_invalid_format_returns_failure(self):
        """Test invalid format returns failure."""
        result = validate_employee_number_detailed("EMP-001!")
        assert result.valid is False
        assert "format" in result.error.lower()


class TestEntityValidator:
    """Tests for EntityValidator class."""

    @pytest.fixture
    def validator(self):
        """Create entity validator."""
        return EntityValidator()

    @pytest.fixture
    def valid_employee(self):
        """Create valid employee data."""
        return {
            "employee_number": "12345",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "state": "FL",
            "country": "US",
            "phone": "5551234567",
        }

    def test_validate_employee_valid(self, validator, valid_employee):
        """Test validating valid employee."""
        result = validator.validate_employee(valid_employee)
        assert result.valid is True

    def test_validate_employee_missing_emp_number(self, validator, valid_employee):
        """Test validating employee without number."""
        del valid_employee["employee_number"]
        result = validator.validate_employee(valid_employee)
        assert result.valid is False

    def test_validate_employee_missing_first_name(self, validator, valid_employee):
        """Test validating employee without first name."""
        del valid_employee["first_name"]
        result = validator.validate_employee(valid_employee)
        assert result.valid is False

    def test_validate_employee_invalid_state(self, validator, valid_employee):
        """Test validating employee with invalid state."""
        valid_employee["state"] = "XX"
        result = validator.validate_employee(valid_employee)
        assert result.valid is False

    def test_validate_employee_invalid_phone(self, validator, valid_employee):
        """Test validating employee with invalid phone."""
        valid_employee["phone"] = "123"
        result = validator.validate_employee(valid_employee)
        assert result.valid is False

    def test_validate_bill_entity_requires_email(self, validator, valid_employee):
        """Test BILL.com entity requires email."""
        del valid_employee["email"]
        result = validator.validate_bill_entity(valid_employee)
        assert result.valid is False
        assert any("email" in e.lower() for e in result.error_messages)

    def test_validate_bill_entity_valid_role(self, validator, valid_employee):
        """Test BILL.com entity with valid role."""
        valid_employee["role"] = "User"
        result = validator.validate_bill_entity(valid_employee)
        assert result.valid is True

    def test_validate_bill_entity_invalid_role(self, validator, valid_employee):
        """Test BILL.com entity with invalid role."""
        valid_employee["role"] = "InvalidRole"
        result = validator.validate_bill_entity(valid_employee)
        assert result.valid is False

    def test_validate_motus_driver_requires_email(self, validator, valid_employee):
        """Test Motus driver requires email."""
        del valid_employee["email"]
        result = validator.validate_motus_driver(valid_employee)
        assert result.valid is False

    def test_validate_motus_driver_requires_address(self, validator, valid_employee):
        """Test Motus driver requires address."""
        result = validator.validate_motus_driver(valid_employee)
        assert result.valid is False
        assert any("address" in e.lower() for e in result.error_messages)

    def test_validate_motus_driver_with_address(self, validator, valid_employee):
        """Test Motus driver with address."""
        valid_employee["address1"] = "123 Main St"
        result = validator.validate_motus_driver(valid_employee)
        assert result.valid is True

    def test_validate_travelperk_requires_email(self, validator, valid_employee):
        """Test TravelPerk user requires email."""
        del valid_employee["email"]
        result = validator.validate_travelperk_user(valid_employee)
        assert result.valid is False

    def test_validate_travelperk_valid_gender(self, validator, valid_employee):
        """Test TravelPerk user with valid gender."""
        valid_employee["gender"] = "M"
        result = validator.validate_travelperk_user(valid_employee)
        assert result.valid is True

    def test_validate_travelperk_invalid_gender(self, validator, valid_employee):
        """Test TravelPerk user with invalid gender."""
        valid_employee["gender"] = "Invalid"
        result = validator.validate_travelperk_user(valid_employee)
        assert result.valid is False


class TestValidateBatch:
    """Tests for batch validation."""

    @pytest.fixture
    def validator(self):
        """Create entity validator."""
        return EntityValidator()

    def test_validate_batch_all_valid(self, validator):
        """Test batch validation with all valid records."""
        records = [
            {"employee_number": "12345", "first_name": "John", "last_name": "Doe"},
            {"employee_number": "12346", "first_name": "Jane", "last_name": "Smith"},
        ]
        result = validate_batch(records, validator.validate_employee)

        assert result["total"] == 2
        assert result["valid"] == 2
        assert result["invalid"] == 0
        assert result["validation_rate"] == 100.0

    def test_validate_batch_some_invalid(self, validator):
        """Test batch validation with some invalid records."""
        records = [
            {"employee_number": "12345", "first_name": "John", "last_name": "Doe"},
            {"employee_number": "", "first_name": "Jane", "last_name": "Smith"},
        ]
        result = validate_batch(records, validator.validate_employee)

        assert result["total"] == 2
        assert result["valid"] == 1
        assert result["invalid"] == 1
        assert len(result["errors"]) == 1

    def test_validate_batch_stop_on_first_error(self, validator):
        """Test batch validation stops on first error."""
        records = [
            {"employee_number": "", "first_name": "John", "last_name": "Doe"},
            {"employee_number": "", "first_name": "Jane", "last_name": "Smith"},
        ]
        result = validate_batch(
            records, validator.validate_employee, stop_on_first_error=True
        )

        assert result["invalid"] == 1
        assert len(result["errors"]) == 1

    def test_validate_batch_empty(self, validator):
        """Test batch validation with empty list."""
        result = validate_batch([], validator.validate_employee)

        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["invalid"] == 0
        assert result["validation_rate"] == 0

    def test_validate_batch_error_includes_identifier(self, validator):
        """Test batch errors include record identifier."""
        records = [
            {"employee_number": "12345", "first_name": "", "last_name": "Doe"},
        ]
        result = validate_batch(records, validator.validate_employee)

        assert result["errors"][0]["identifier"] == "12345"
