"""
Unit tests for validators module.
Tests for SOW Requirements 3.6, 3.7 - Input validation.
"""
import sys
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.validators import (
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
    ValidationResult,
    ValidationResults,
    EntityValidator,
    validate_batch,
    US_STATES,
    COUNTRY_CODES,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_success_creates_valid_result(self):
        """Test success factory creates valid result."""
        result = ValidationResult.success("email", "test@example.com")
        assert result.valid is True
        assert result.error is None
        assert result.field == "email"
        assert result.value == "test@example.com"

    def test_failure_creates_invalid_result(self):
        """Test failure factory creates invalid result."""
        result = ValidationResult.failure("Invalid email", "email", "bad-email")
        assert result.valid is False
        assert result.error == "Invalid email"
        assert result.field == "email"
        assert result.value == "bad-email"

    def test_bool_returns_valid_state(self):
        """Test __bool__ returns valid state."""
        assert bool(ValidationResult.success()) is True
        assert bool(ValidationResult.failure("error")) is False

    def test_success_with_no_args(self):
        """Test success factory with no arguments."""
        result = ValidationResult.success()
        assert result.valid is True
        assert result.field is None
        assert result.value is None


class TestValidationResults:
    """Tests for ValidationResults collection class."""

    def test_init_empty(self):
        """Test empty results collection."""
        results = ValidationResults()
        assert results.valid is True
        assert len(results.results) == 0
        assert len(results.errors) == 0

    def test_add_success_result(self):
        """Test adding success result."""
        results = ValidationResults()
        results.add(ValidationResult.success("email", "test@test.com"))
        assert results.valid is True
        assert len(results.results) == 1

    def test_add_failure_makes_invalid(self):
        """Test adding failure makes collection invalid."""
        results = ValidationResults()
        results.add(ValidationResult.success("name"))
        results.add(ValidationResult.failure("Invalid email", "email"))
        assert results.valid is False
        assert len(results.errors) == 1

    def test_errors_property(self):
        """Test errors property returns only failures."""
        results = ValidationResults()
        results.add(ValidationResult.success("name"))
        results.add(ValidationResult.failure("Error 1", "email"))
        results.add(ValidationResult.success("phone"))
        results.add(ValidationResult.failure("Error 2", "state"))

        errors = results.errors
        assert len(errors) == 2
        assert all(not e.valid for e in errors)

    def test_error_messages_property(self):
        """Test error_messages returns list of error strings."""
        results = ValidationResults()
        results.add(ValidationResult.failure("Error 1", "email"))
        results.add(ValidationResult.failure("Error 2", "state"))

        messages = results.error_messages
        assert messages == ["Error 1", "Error 2"]

    def test_bool_returns_valid_state(self):
        """Test __bool__ returns valid state."""
        results = ValidationResults()
        assert bool(results) is True

        results.add(ValidationResult.failure("Error"))
        assert bool(results) is False

    def test_to_dict(self):
        """Test to_dict serialization."""
        results = ValidationResults()
        results.add(ValidationResult.success("name", "John"))
        results.add(ValidationResult.failure("Invalid email", "email", "bad"))

        d = results.to_dict()
        assert d["valid"] is False
        assert d["total_checks"] == 2
        assert len(d["errors"]) == 1
        assert d["errors"][0]["field"] == "email"
        assert d["errors"][0]["error"] == "Invalid email"

    def test_to_dict_all_valid(self):
        """Test to_dict with all valid results."""
        results = ValidationResults()
        results.add(ValidationResult.success("name"))
        results.add(ValidationResult.success("email"))

        d = results.to_dict()
        assert d["valid"] is True
        assert d["total_checks"] == 2
        assert d["errors"] == []


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_simple_email(self):
        """Test valid simple email."""
        assert validate_email("user@example.com") is True

    def test_valid_email_with_subdomain(self):
        """Test valid email with subdomain."""
        assert validate_email("user@mail.example.com") is True

    def test_valid_email_with_plus(self):
        """Test valid email with plus sign."""
        assert validate_email("user+tag@example.com") is True

    def test_valid_email_with_dots(self):
        """Test valid email with dots in local part."""
        assert validate_email("first.last@example.com") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @."""
        assert validate_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert validate_email("user@") is False

    def test_invalid_email_no_tld(self):
        """Test invalid email without TLD."""
        assert validate_email("user@example") is False

    def test_empty_email(self):
        """Test empty email returns False."""
        assert validate_email("") is False

    def test_none_email(self):
        """Test None email returns False."""
        assert validate_email(None) is False

    def test_email_with_whitespace_trimmed(self):
        """Test email with whitespace is trimmed."""
        assert validate_email("  user@example.com  ") is True


class TestValidateStateCode:
    """Tests for validate_state_code function."""

    def test_valid_state_uppercase(self):
        """Test valid state code uppercase."""
        assert validate_state_code("FL") is True
        assert validate_state_code("CA") is True
        assert validate_state_code("NY") is True

    def test_valid_state_lowercase(self):
        """Test valid state code lowercase."""
        assert validate_state_code("fl") is True
        assert validate_state_code("ca") is True

    def test_valid_state_mixed_case(self):
        """Test valid state code mixed case."""
        assert validate_state_code("Fl") is True
        assert validate_state_code("cA") is True

    def test_valid_territories(self):
        """Test valid territory codes."""
        assert validate_state_code("DC") is True
        assert validate_state_code("PR") is True
        assert validate_state_code("VI") is True
        assert validate_state_code("GU") is True

    def test_invalid_state_code(self):
        """Test invalid state code."""
        assert validate_state_code("XX") is False
        assert validate_state_code("ZZ") is False

    def test_empty_state_is_valid(self):
        """Test empty state is valid (optional field)."""
        assert validate_state_code("") is True
        assert validate_state_code(None) is True

    def test_state_with_whitespace(self):
        """Test state code with whitespace is trimmed."""
        assert validate_state_code("  FL  ") is True

    def test_all_us_states_valid(self):
        """Test all defined US states are valid."""
        for state in US_STATES:
            assert validate_state_code(state) is True


class TestValidateCountryCode:
    """Tests for validate_country_code function."""

    def test_valid_country_us(self):
        """Test valid US country code."""
        assert validate_country_code("US") is True

    def test_valid_country_lowercase(self):
        """Test valid country code lowercase."""
        assert validate_country_code("us") is True
        assert validate_country_code("ca") is True

    def test_invalid_country_code(self):
        """Test invalid country code."""
        assert validate_country_code("XX") is False
        assert validate_country_code("ZZ") is False

    def test_empty_country_is_valid(self):
        """Test empty country is valid (optional field)."""
        assert validate_country_code("") is True
        assert validate_country_code(None) is True

    def test_all_defined_countries_valid(self):
        """Test all defined country codes are valid."""
        for country in COUNTRY_CODES:
            assert validate_country_code(country) is True


class TestValidatePhone:
    """Tests for validate_phone function."""

    def test_valid_phone_10_digits(self):
        """Test valid 10-digit phone."""
        assert validate_phone("5551234567") is True

    def test_valid_phone_with_dashes(self):
        """Test valid phone with dashes."""
        assert validate_phone("555-123-4567") is True

    def test_valid_phone_with_dots(self):
        """Test valid phone with dots."""
        assert validate_phone("555.123.4567") is True

    def test_valid_phone_with_spaces(self):
        """Test valid phone with spaces."""
        assert validate_phone("555 123 4567") is True

    def test_valid_phone_with_country_code(self):
        """Test valid phone with country code."""
        assert validate_phone("+1-555-123-4567") is True
        assert validate_phone("+15551234567") is True

    def test_valid_phone_with_parens(self):
        """Test valid phone with parentheses."""
        assert validate_phone("(555) 123-4567") is True

    def test_invalid_phone_too_short(self):
        """Test invalid phone - too short."""
        assert validate_phone("12345") is False
        assert validate_phone("555123") is False

    def test_invalid_phone_with_letters(self):
        """Test invalid phone with letters."""
        assert validate_phone("555-ABC-1234") is False

    def test_empty_phone_is_valid(self):
        """Test empty phone is valid (optional field)."""
        assert validate_phone("") is True
        assert validate_phone(None) is True


class TestValidateEmployeeNumber:
    """Tests for validate_employee_number function."""

    def test_valid_numeric_employee_number(self):
        """Test valid numeric employee number."""
        assert validate_employee_number("12345") is True
        assert validate_employee_number("1") is True

    def test_valid_alphanumeric_employee_number(self):
        """Test valid alphanumeric employee number."""
        assert validate_employee_number("EMP001") is True
        assert validate_employee_number("A1B2C3") is True

    def test_valid_long_employee_number(self):
        """Test valid 20-char employee number."""
        assert validate_employee_number("12345678901234567890") is True

    def test_invalid_too_long(self):
        """Test invalid employee number - too long."""
        assert validate_employee_number("123456789012345678901") is False

    def test_invalid_special_chars(self):
        """Test invalid employee number with special chars."""
        assert validate_employee_number("EMP-001") is False
        assert validate_employee_number("EMP_001") is False
        assert validate_employee_number("EMP 001") is False

    def test_empty_employee_number_invalid(self):
        """Test empty employee number is invalid (required)."""
        assert validate_employee_number("") is False
        assert validate_employee_number(None) is False

    def test_whitespace_trimmed(self):
        """Test employee number whitespace is trimmed."""
        assert validate_employee_number("  12345  ") is True


class TestValidateDateString:
    """Tests for validate_date_string function."""

    def test_valid_iso_date(self):
        """Test valid ISO date format."""
        assert validate_date_string("2024-01-15") is True

    def test_valid_us_date(self):
        """Test valid US date format."""
        assert validate_date_string("01/15/2024") is True

    def test_valid_iso_datetime(self):
        """Test valid ISO datetime format."""
        assert validate_date_string("2024-01-15T10:30:00") is True

    def test_valid_iso_datetime_with_z(self):
        """Test valid ISO datetime with Z suffix."""
        assert validate_date_string("2024-01-15T10:30:00Z") is True

    def test_valid_iso_datetime_with_ms(self):
        """Test valid ISO datetime with milliseconds."""
        assert validate_date_string("2024-01-15T10:30:00.123Z") is True

    def test_invalid_date_format(self):
        """Test invalid date format."""
        assert validate_date_string("15-01-2024") is False
        assert validate_date_string("2024/01/15") is False

    def test_invalid_date_values(self):
        """Test invalid date values."""
        assert validate_date_string("2024-13-01") is False  # Invalid month
        assert validate_date_string("2024-01-32") is False  # Invalid day

    def test_empty_date_is_valid(self):
        """Test empty date is valid (optional field)."""
        assert validate_date_string("") is True
        assert validate_date_string(None) is True

    def test_custom_formats(self):
        """Test custom date formats."""
        assert validate_date_string("15/01/2024", formats=["%d/%m/%Y"]) is True
        assert validate_date_string("2024.01.15", formats=["%Y.%m.%d"]) is True


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_none_is_not_valid(self):
        """Test None is not valid."""
        assert validate_required(None) is False

    def test_empty_string_not_valid_by_default(self):
        """Test empty string is not valid by default."""
        assert validate_required("") is False
        assert validate_required("   ") is False

    def test_empty_string_valid_when_allowed(self):
        """Test empty string is valid when allowed."""
        assert validate_required("", allow_empty_string=True) is True

    def test_non_empty_string_is_valid(self):
        """Test non-empty string is valid."""
        assert validate_required("value") is True
        assert validate_required("  value  ") is True

    def test_non_string_values(self):
        """Test non-string values."""
        assert validate_required(0) is True  # Zero is valid
        assert validate_required(False) is True  # False is valid
        assert validate_required([]) is True  # Empty list is valid
        assert validate_required({}) is True  # Empty dict is valid


class TestValidateLength:
    """Tests for validate_length function."""

    def test_within_bounds(self):
        """Test string within bounds."""
        assert validate_length("hello", min_length=1, max_length=10) is True

    def test_exact_min_length(self):
        """Test string at exact min length."""
        assert validate_length("abc", min_length=3) is True

    def test_exact_max_length(self):
        """Test string at exact max length."""
        assert validate_length("abc", max_length=3) is True

    def test_below_min_length(self):
        """Test string below min length."""
        assert validate_length("ab", min_length=3) is False

    def test_above_max_length(self):
        """Test string above max length."""
        assert validate_length("abcdef", max_length=5) is False

    def test_empty_string_with_zero_min(self):
        """Test empty string with zero min length."""
        assert validate_length("", min_length=0) is True
        assert validate_length(None, min_length=0) is True

    def test_empty_string_with_positive_min(self):
        """Test empty string with positive min length."""
        assert validate_length("", min_length=1) is False

    def test_no_max_length(self):
        """Test with no max length constraint."""
        assert validate_length("a" * 1000, min_length=1) is True


class TestValidateEmailDetailed:
    """Tests for validate_email_detailed function."""

    def test_valid_email_success(self):
        """Test valid email returns success result."""
        result = validate_email_detailed("user@example.com")
        assert result.valid is True
        assert result.error is None
        assert result.field == "email"

    def test_invalid_email_failure(self):
        """Test invalid email returns failure result."""
        result = validate_email_detailed("invalid-email")
        assert result.valid is False
        assert "Invalid email format" in result.error
        assert result.field == "email"

    def test_empty_email_failure(self):
        """Test empty email returns failure result."""
        result = validate_email_detailed("")
        assert result.valid is False
        assert "required" in result.error.lower()

    def test_custom_field_name(self):
        """Test custom field name is used."""
        result = validate_email_detailed("test@test.com", field="work_email")
        assert result.field == "work_email"


class TestValidateStateCodeDetailed:
    """Tests for validate_state_code_detailed function."""

    def test_valid_state_success(self):
        """Test valid state returns success result."""
        result = validate_state_code_detailed("FL")
        assert result.valid is True
        assert result.error is None

    def test_invalid_state_failure(self):
        """Test invalid state returns failure result."""
        result = validate_state_code_detailed("XX")
        assert result.valid is False
        assert "Invalid state code" in result.error
        assert "XX" in result.error

    def test_empty_state_success(self):
        """Test empty state returns success (optional field)."""
        result = validate_state_code_detailed("")
        assert result.valid is True

    def test_custom_field_name(self):
        """Test custom field name is used."""
        result = validate_state_code_detailed("FL", field="work_state")
        assert result.field == "work_state"


class TestValidateEmployeeNumberDetailed:
    """Tests for validate_employee_number_detailed function."""

    def test_valid_number_success(self):
        """Test valid employee number returns success."""
        result = validate_employee_number_detailed("12345")
        assert result.valid is True
        assert result.error is None

    def test_invalid_number_failure(self):
        """Test invalid employee number returns failure."""
        result = validate_employee_number_detailed("EMP-001")
        assert result.valid is False
        assert "Invalid employee number format" in result.error

    def test_empty_number_failure(self):
        """Test empty employee number returns failure."""
        result = validate_employee_number_detailed("")
        assert result.valid is False
        assert "required" in result.error.lower()

    def test_custom_field_name(self):
        """Test custom field name is used."""
        result = validate_employee_number_detailed("12345", field="emp_id")
        assert result.field == "emp_id"


class TestEntityValidator:
    """Tests for EntityValidator class."""

    def test_init_default_not_strict(self):
        """Test default init is not strict."""
        validator = EntityValidator()
        assert validator.strict is False

    def test_init_strict_mode(self):
        """Test strict mode initialization."""
        validator = EntityValidator(strict=True)
        assert validator.strict is True

    def test_validate_employee_valid(self):
        """Test validate_employee with valid data."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "state": "FL",
        }
        results = validator.validate_employee(employee)
        assert results.valid is True

    def test_validate_employee_missing_required(self):
        """Test validate_employee with missing required fields."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "",
            "firstName": "",
            "lastName": "",
        }
        results = validator.validate_employee(employee)
        assert results.valid is False
        assert len(results.errors) >= 3

    def test_validate_employee_invalid_email(self):
        """Test validate_employee with invalid email."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "invalid-email",
        }
        results = validator.validate_employee(employee)
        assert results.valid is False
        errors = [e.field for e in results.errors]
        assert "email" in errors

    def test_validate_employee_invalid_state(self):
        """Test validate_employee with invalid state."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "state": "XX",
        }
        results = validator.validate_employee(employee)
        assert results.valid is False

    def test_validate_employee_invalid_phone(self):
        """Test validate_employee with invalid phone."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "phone": "123",  # Too short
        }
        results = validator.validate_employee(employee)
        assert results.valid is False

    def test_validate_employee_invalid_date(self):
        """Test validate_employee with invalid hire date."""
        validator = EntityValidator()
        employee = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "hireDate": "invalid-date",
        }
        results = validator.validate_employee(employee)
        assert results.valid is False

    def test_validate_employee_alternate_field_names(self):
        """Test validate_employee with alternate field names."""
        validator = EntityValidator()
        employee = {
            "employee_number": "12345",
            "first_name": "John",
            "last_name": "Doe",
            "primaryEmail": "john@example.com",
            "stateCode": "FL",
            "countryCode": "US",
            "phoneNumber": "555-123-4567",
            "hire_date": "2024-01-15",
        }
        results = validator.validate_employee(employee)
        assert results.valid is True


class TestEntityValidatorTravelPerk:
    """Tests for EntityValidator.validate_travelperk_user method."""

    def test_valid_travelperk_user(self):
        """Test valid TravelPerk user validation."""
        validator = EntityValidator()
        user = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
        }
        results = validator.validate_travelperk_user(user)
        assert results.valid is True

    def test_missing_email_required(self):
        """Test TravelPerk user requires email."""
        validator = EntityValidator()
        user = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
        }
        results = validator.validate_travelperk_user(user)
        assert results.valid is False
        error_messages = " ".join(results.error_messages)
        assert "email" in error_messages.lower()

    def test_valid_gender_male(self):
        """Test valid gender value - Male."""
        validator = EntityValidator()
        user = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "gender": "M",
        }
        results = validator.validate_travelperk_user(user)
        assert results.valid is True

    def test_valid_gender_female(self):
        """Test valid gender value - Female."""
        validator = EntityValidator()
        user = {
            "employeeNumber": "12345",
            "firstName": "Jane",
            "lastName": "Doe",
            "email": "jane@example.com",
            "gender": "FEMALE",
        }
        results = validator.validate_travelperk_user(user)
        assert results.valid is True

    def test_invalid_gender(self):
        """Test invalid gender value."""
        validator = EntityValidator()
        user = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "gender": "invalid",
        }
        results = validator.validate_travelperk_user(user)
        assert results.valid is False
        error_messages = " ".join(results.error_messages)
        assert "gender" in error_messages.lower()


class TestEntityValidatorBill:
    """Tests for EntityValidator.validate_bill_entity method."""

    def test_valid_bill_entity(self):
        """Test valid BILL entity validation."""
        validator = EntityValidator()
        entity = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "role": "User",
        }
        results = validator.validate_bill_entity(entity)
        assert results.valid is True

    def test_missing_email_required(self):
        """Test BILL entity requires email."""
        validator = EntityValidator()
        entity = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
        }
        results = validator.validate_bill_entity(entity)
        assert results.valid is False

    def test_invalid_role(self):
        """Test invalid BILL role."""
        validator = EntityValidator()
        entity = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "role": "InvalidRole",
        }
        results = validator.validate_bill_entity(entity)
        assert results.valid is False
        error_messages = " ".join(results.error_messages)
        assert "role" in error_messages.lower()

    def test_valid_roles(self):
        """Test all valid BILL roles."""
        validator = EntityValidator()
        valid_roles = ["User", "Administrator", "Accountant", "Auditor"]
        for role in valid_roles:
            entity = {
                "employeeNumber": "12345",
                "firstName": "John",
                "lastName": "Doe",
                "email": "john@example.com",
                "role": role,
            }
            results = validator.validate_bill_entity(entity)
            assert results.valid is True, f"Role {role} should be valid"


class TestEntityValidatorMotus:
    """Tests for EntityValidator.validate_motus_driver method."""

    def test_valid_motus_driver(self):
        """Test valid Motus driver validation."""
        validator = EntityValidator()
        driver = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "address1": "123 Main St",
        }
        results = validator.validate_motus_driver(driver)
        assert results.valid is True

    def test_missing_email_required(self):
        """Test Motus driver requires email."""
        validator = EntityValidator()
        driver = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "address1": "123 Main St",
        }
        results = validator.validate_motus_driver(driver)
        assert results.valid is False

    def test_missing_address_required(self):
        """Test Motus driver requires address."""
        validator = EntityValidator()
        driver = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
        }
        results = validator.validate_motus_driver(driver)
        assert results.valid is False
        error_messages = " ".join(results.error_messages)
        assert "address" in error_messages.lower()

    def test_valid_with_line1_instead_of_address1(self):
        """Test valid Motus driver with 'line1' field."""
        validator = EntityValidator()
        driver = {
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "line1": "123 Main St",
        }
        results = validator.validate_motus_driver(driver)
        assert results.valid is True


class TestValidateBatch:
    """Tests for validate_batch function."""

    def test_all_valid_records(self):
        """Test batch with all valid records."""
        validator = EntityValidator()
        records = [
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"},
            {"employeeNumber": "67890", "firstName": "Jane", "lastName": "Smith"},
        ]
        result = validate_batch(records, validator.validate_employee)
        assert result["total"] == 2
        assert result["valid"] == 2
        assert result["invalid"] == 0
        assert result["validation_rate"] == 100.0

    def test_mixed_records(self):
        """Test batch with mixed valid/invalid records."""
        validator = EntityValidator()
        records = [
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"},
            {"employeeNumber": "", "firstName": "", "lastName": ""},  # Invalid
        ]
        result = validate_batch(records, validator.validate_employee)
        assert result["total"] == 2
        assert result["valid"] == 1
        assert result["invalid"] == 1
        assert result["validation_rate"] == 50.0

    def test_stop_on_first_error(self):
        """Test batch stops on first error when flag is set."""
        validator = EntityValidator()
        records = [
            {"employeeNumber": "", "firstName": "", "lastName": ""},  # Invalid
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"},
            {"employeeNumber": "", "firstName": "", "lastName": ""},  # Invalid
        ]
        result = validate_batch(
            records, validator.validate_employee, stop_on_first_error=True
        )
        # Should stop after first error
        assert result["invalid"] == 1

    def test_error_identifier_uses_employee_number(self):
        """Test error identifier uses employee_number."""
        validator = EntityValidator()
        records = [
            {"employeeNumber": "EMP001", "firstName": "", "lastName": ""},
        ]
        result = validate_batch(records, validator.validate_employee)
        assert result["errors"][0]["identifier"] == "EMP001"

    def test_error_identifier_fallback_to_index(self):
        """Test error identifier falls back to index."""
        validator = EntityValidator()
        records = [
            {"firstName": "", "lastName": ""},  # No employee number
        ]
        result = validate_batch(records, validator.validate_employee)
        assert result["errors"][0]["identifier"] == "record_0"

    def test_empty_batch(self):
        """Test empty batch."""
        validator = EntityValidator()
        result = validate_batch([], validator.validate_employee)
        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["invalid"] == 0
        assert result["validation_rate"] == 0

    def test_errors_limited_to_100(self):
        """Test errors are limited to 100 in summary."""
        validator = EntityValidator()
        records = [
            {"employeeNumber": "", "firstName": "", "lastName": ""}
            for _ in range(150)
        ]
        result = validate_batch(records, validator.validate_employee)
        assert len(result["errors"]) == 100
        assert result["invalid"] == 150
