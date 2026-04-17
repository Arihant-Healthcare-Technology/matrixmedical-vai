"""
Unit tests for Employee domain model.
"""

import pytest
from datetime import date

from src.domain.models.employee import (
    Address,
    Employee,
    EmployeeStatus,
    EmployeeType,
)


class TestEmployeeStatus:
    """Tests for EmployeeStatus enum."""

    def test_from_code_active(self):
        """Test converting active status code."""
        assert EmployeeStatus.from_code("A") == EmployeeStatus.ACTIVE
        assert EmployeeStatus.from_code("a") == EmployeeStatus.ACTIVE

    def test_from_code_terminated(self):
        """Test converting terminated status code."""
        assert EmployeeStatus.from_code("T") == EmployeeStatus.TERMINATED

    def test_from_code_unknown_defaults_to_active(self):
        """Test unknown code defaults to active."""
        assert EmployeeStatus.from_code("X") == EmployeeStatus.ACTIVE
        assert EmployeeStatus.from_code("") == EmployeeStatus.ACTIVE

    def test_is_active_property(self):
        """Test is_active property."""
        assert EmployeeStatus.ACTIVE.is_active is True
        assert EmployeeStatus.TERMINATED.is_active is False
        assert EmployeeStatus.LEAVE.is_active is False


class TestAddress:
    """Tests for Address dataclass."""

    def test_is_complete_with_all_fields(self):
        """Test is_complete with all required fields."""
        address = Address(
            line1="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
        )
        assert address.is_complete() is True

    def test_is_complete_missing_line1(self):
        """Test is_complete with missing line1."""
        address = Address(
            city="San Francisco",
            state="CA",
            zip_code="94105",
        )
        assert address.is_complete() is False

    def test_is_complete_missing_city(self):
        """Test is_complete with missing city."""
        address = Address(
            line1="123 Main St",
            state="CA",
            zip_code="94105",
        )
        assert address.is_complete() is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        address = Address(
            line1="123 Main St",
            line2="Suite 100",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            country="US",
        )
        result = address.to_dict()
        assert result == {
            "line1": "123 Main St",
            "line2": "Suite 100",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "country": "US",
        }

    def test_from_ukg(self):
        """Test creation from UKG data."""
        data = {
            "address1": "123 Main St",
            "address2": "Apt 4",
            "city": "Los Angeles",
            "stateCode": "CA",
            "postalCode": "90001",
            "countryCode": "US",
        }
        address = Address.from_ukg(data)
        assert address.line1 == "123 Main St"
        assert address.line2 == "Apt 4"
        assert address.city == "Los Angeles"
        assert address.state == "CA"
        assert address.zip_code == "90001"


class TestEmployee:
    """Tests for Employee domain model."""

    def test_basic_creation(self):
        """Test basic employee creation."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )
        assert emp.employee_id == "EMP001"
        assert emp.full_name == "John Doe"
        assert emp.is_active is True

    def test_email_normalization(self):
        """Test email is normalized to lowercase."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="JOHN.DOE@EXAMPLE.COM",
        )
        assert emp.email == "john.doe@example.com"

    def test_name_stripping(self):
        """Test names are stripped of whitespace."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="  John  ",
            last_name="  Doe  ",
            email="john@example.com",
        )
        assert emp.first_name == "John"
        assert emp.last_name == "Doe"

    def test_phone_normalization(self):
        """Test phone number normalization."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="(415) 555-1234",
        )
        assert emp.phone == "4155551234"

    def test_phone_normalization_with_country_code(self):
        """Test phone with country code keeps last 10 digits."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+1 415 555 1234",
        )
        assert emp.phone == "4155551234"

    def test_has_supervisor_with_email(self):
        """Test has_supervisor with email."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            supervisor_email="boss@example.com",
        )
        assert emp.has_supervisor is True

    def test_has_supervisor_with_id(self):
        """Test has_supervisor with supervisor ID."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            supervisor_id="SUP001",
        )
        assert emp.has_supervisor is True

    def test_has_supervisor_none(self):
        """Test has_supervisor with no supervisor."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )
        assert emp.has_supervisor is False

    def test_validate_valid_employee(self):
        """Test validation of valid employee."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )
        errors = emp.validate()
        assert len(errors) == 0
        assert emp.is_valid() is True

    def test_validate_missing_employee_id(self):
        """Test validation catches missing employee_id."""
        emp = Employee(
            employee_id="",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )
        errors = emp.validate()
        assert "employee_id is required" in errors

    def test_validate_invalid_email(self):
        """Test validation catches invalid email."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="invalid-email",
        )
        errors = emp.validate()
        assert any("Invalid email" in e for e in errors)

    def test_validate_invalid_phone_length(self):
        """Test validation catches invalid phone length."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="12345",  # Only 5 digits
        )
        errors = emp.validate()
        assert any("Phone must be 10 digits" in e for e in errors)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            department="Engineering",
            job_title="Developer",
        )
        result = emp.to_dict()
        assert result["employee_id"] == "EMP001"
        assert result["full_name"] == "John Doe"
        assert result["is_active"] is True
        assert result["department"] == "Engineering"

    def test_from_ukg(self):
        """Test creation from UKG API data."""
        data = {
            "employeeId": "abc-123",
            "employeeNumber": "12345",
            "firstName": "Jane",
            "lastName": "Smith",
            "emailAddress": "jane.smith@example.com",
            "employeeStatusCode": "A",
            "departmentDescription": "Sales",
            "originalHireDate": "2020-01-15",
        }
        emp = Employee.from_ukg(data)
        assert emp.employee_id == "abc-123"
        assert emp.employee_number == "12345"
        assert emp.first_name == "Jane"
        assert emp.last_name == "Smith"
        assert emp.is_active is True
        assert emp.hire_date == date(2020, 1, 15)

    def test_from_ukg_with_person_data(self):
        """Test creation from UKG with separate person data."""
        employment_data = {
            "employeeId": "abc-123",
            "employeeNumber": "12345",
            "employeeStatusCode": "A",
        }
        person_data = {
            "firstName": "Jane",
            "lastName": "Smith",
            "emailAddress": "jane.smith@example.com",
            "workPhone": "5551234567",
        }
        emp = Employee.from_ukg(employment_data, person_data)
        assert emp.first_name == "Jane"
        assert emp.last_name == "Smith"
        assert emp.phone == "5551234567"

    def test_status_string_conversion(self):
        """Test status string is converted to enum."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            status="T",  # type: ignore
        )
        assert emp.status == EmployeeStatus.TERMINATED
        assert emp.is_active is False

    def test_is_full_time_with_full_time(self):
        """Test is_full_time returns True for Full Time employees."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            full_or_part_time="Full Time",
        )
        assert emp.is_full_time is True

    def test_is_full_time_with_part_time(self):
        """Test is_full_time returns False for Part Time employees."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            full_or_part_time="Part Time",
        )
        assert emp.is_full_time is False

    def test_is_full_time_defaults_to_true_when_empty(self):
        """Test is_full_time defaults to True when field is empty."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            full_or_part_time="",
        )
        assert emp.is_full_time is True

    def test_should_sync_to_bill_prd_full_time(self):
        """Test should_sync_to_bill returns True for PRD + Full Time."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            employee_type_code="PRD",
            full_or_part_time="Full Time",
        )
        assert emp.should_sync_to_bill is True

    def test_should_sync_to_bill_prd_part_time(self):
        """Test should_sync_to_bill returns False for PRD + Part Time."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            employee_type_code="PRD",
            full_or_part_time="Part Time",
        )
        assert emp.should_sync_to_bill is False

    def test_should_sync_to_bill_ftc_full_time(self):
        """Test should_sync_to_bill returns False for FTC (non-PRD)."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            employee_type_code="FTC",
            full_or_part_time="Full Time",
        )
        assert emp.should_sync_to_bill is False
