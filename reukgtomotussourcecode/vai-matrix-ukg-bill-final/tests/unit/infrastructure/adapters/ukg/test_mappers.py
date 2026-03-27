"""
Unit tests for UKG data mappers.
"""

from datetime import datetime

import pytest

from src.domain.models.employee import Address, EmployeeStatus
from src.infrastructure.adapters.ukg.mappers import (
    extract_supervisor_info,
    map_address,
    map_employee_from_ukg,
    map_employment_status,
    normalize_phone,
    parse_date,
)


class TestNormalizePhone:
    """Tests for normalize_phone function."""

    def test_ten_digit_phone(self):
        """Should format 10-digit phone as XXX-XXX-XXXX."""
        assert normalize_phone("5551234567") == "555-123-4567"

    def test_ten_digit_with_dashes(self):
        """Should normalize phone with existing dashes."""
        assert normalize_phone("555-123-4567") == "555-123-4567"

    def test_ten_digit_with_parens(self):
        """Should normalize phone with parentheses."""
        assert normalize_phone("(555) 123-4567") == "555-123-4567"

    def test_eleven_digit_with_country_code(self):
        """Should handle 11-digit phone with leading 1."""
        assert normalize_phone("15551234567") == "555-123-4567"

    def test_non_standard_format(self):
        """Should return original for non-standard formats."""
        assert normalize_phone("12345") == "12345"

    def test_empty_phone(self):
        """Should return empty string for None/empty."""
        assert normalize_phone(None) == ""
        assert normalize_phone("") == ""

    def test_phone_with_extension(self):
        """Should return original for phone with extension."""
        assert normalize_phone("555-123-4567 x123") == "555-123-4567 x123"


class TestParseDate:
    """Tests for parse_date function."""

    def test_iso_8601_with_z(self):
        """Should parse ISO 8601 date with Z timezone."""
        result = parse_date("2024-01-15T00:00:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_8601_with_offset(self):
        """Should parse ISO 8601 date with offset."""
        result = parse_date("2024-03-20T10:30:00+05:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 20

    def test_plain_date(self):
        """Should parse plain YYYY-MM-DD date."""
        result = parse_date("2024-06-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_empty_date(self):
        """Should return None for empty/None input."""
        assert parse_date(None) is None
        assert parse_date("") is None

    def test_invalid_date(self):
        """Should return None for invalid date format."""
        assert parse_date("not-a-date") is None
        assert parse_date("01/15/2024") is None


class TestMapEmploymentStatus:
    """Tests for map_employment_status function."""

    def test_active_status_code(self):
        """Should map 'A' status code to ACTIVE."""
        data = {"employeeStatusCode": "A"}
        assert map_employment_status(data) == EmployeeStatus.ACTIVE

    def test_terminated_with_date(self):
        """Should map to TERMINATED when terminationDate present."""
        data = {"terminationDate": "2024-01-15", "employeeStatusCode": "A"}
        assert map_employment_status(data) == EmployeeStatus.TERMINATED

    def test_leave_status_code(self):
        """Should map 'L' status code to LEAVE."""
        data = {"employeeStatusCode": "L"}
        assert map_employment_status(data) == EmployeeStatus.LEAVE

    def test_retired_status_code(self):
        """Should map 'R' status code to RETIRED."""
        data = {"employeeStatusCode": "R"}
        assert map_employment_status(data) == EmployeeStatus.RETIRED

    def test_unknown_status_code(self):
        """Should map unknown status to ACTIVE (default)."""
        data = {"employeeStatusCode": "X"}
        assert map_employment_status(data) == EmployeeStatus.ACTIVE

    def test_empty_data(self):
        """Should return ACTIVE (default) for empty data."""
        assert map_employment_status({}) == EmployeeStatus.ACTIVE

    def test_lowercase_status_code(self):
        """Should handle lowercase status codes."""
        data = {"employeeStatusCode": "a"}
        assert map_employment_status(data) == EmployeeStatus.ACTIVE


class TestMapAddress:
    """Tests for map_address function."""

    def test_full_address(self):
        """Should map all address fields."""
        data = {
            "addressLine1": "123 Main St",
            "addressLine2": "Suite 100",
            "addressCity": "San Francisco",
            "addressState": "CA",
            "addressZipCode": "94105",
            "addressCountry": "US",
        }
        address = map_address(data)
        assert address.line1 == "123 Main St"
        assert address.line2 == "Suite 100"
        assert address.city == "San Francisco"
        assert address.state == "CA"
        assert address.zip_code == "94105"
        assert address.country == "US"

    def test_alternate_field_names(self):
        """Should handle alternate field names."""
        data = {
            "address1": "456 Oak Ave",
            "city": "Austin",
            "stateCode": "TX",
            "postalCode": "78701",
            "countryCode": "US",
        }
        address = map_address(data)
        assert address.line1 == "456 Oak Ave"
        assert address.city == "Austin"
        assert address.state == "TX"
        assert address.zip_code == "78701"

    def test_empty_data(self):
        """Should return empty address for empty data."""
        address = map_address({})
        assert address.line1 == ""
        assert address.city == ""
        assert address.state == ""
        assert address.country == "US"  # Default

    def test_partial_address(self):
        """Should handle partial address data."""
        data = {
            "addressLine1": "789 Pine St",
            "addressCity": "Seattle",
        }
        address = map_address(data)
        assert address.line1 == "789 Pine St"
        assert address.city == "Seattle"
        assert address.state == ""
        assert address.zip_code == ""


class TestMapEmployeeFromUkg:
    """Tests for map_employee_from_ukg function."""

    def test_basic_mapping(self):
        """Should map basic employment data."""
        employment_data = {
            "employeeId": "EMP001",
            "employeeNumber": "12345",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
            "employeeStatusCode": "A",
            "departmentDescription": "Engineering",
            "jobDescription": "Software Engineer",
            "companyID": "COMP1",
        }

        employee = map_employee_from_ukg(employment_data)

        assert employee.employee_id == "EMP001"
        assert employee.employee_number == "12345"
        assert employee.first_name == "John"
        assert employee.last_name == "Doe"
        assert employee.email == "john.doe@example.com"
        assert employee.status == EmployeeStatus.ACTIVE
        assert employee.department == "Engineering"
        assert employee.job_title == "Software Engineer"

    def test_with_person_data(self):
        """Should prefer person data for name/email."""
        employment_data = {
            "employeeId": "EMP002",
            "employeeNumber": "67890",
            "firstName": "Jane",
            "lastName": "Smith",
            "employeeStatusCode": "A",
        }
        person_data = {
            "firstName": "Janet",
            "lastName": "Smithson",
            "emailAddress": "janet.smithson@example.com",
            "addressLine1": "100 Park Ave",
            "addressCity": "New York",
            "addressState": "NY",
            "addressZipCode": "10001",
        }

        employee = map_employee_from_ukg(employment_data, person_data)

        assert employee.first_name == "Janet"
        assert employee.last_name == "Smithson"
        assert employee.email == "janet.smithson@example.com"
        assert employee.address.line1 == "100 Park Ave"

    def test_with_employee_employment_data(self):
        """Should use employee-employment data for project code."""
        employment_data = {
            "employeeId": "EMP003",
            "employeeNumber": "11111",
            "firstName": "Bob",
            "lastName": "Wilson",
            "employeeStatusCode": "A",
        }
        employee_employment_data = {
            "primaryProjectCode": "PROJ-001",
            "departmentDescription": "Marketing",
        }

        employee = map_employee_from_ukg(
            employment_data,
            employee_employment_data=employee_employment_data,
        )

        assert employee.cost_center == "PROJ-001"

    def test_supervisor_info(self):
        """Should extract supervisor information."""
        employment_data = {
            "employeeId": "EMP004",
            "employeeNumber": "22222",
            "firstName": "Alice",
            "lastName": "Brown",
            "employeeStatusCode": "A",
            "supervisorEmailAddress": "manager@example.com",
            "supervisorEmployeeId": "SUP001",
        }

        employee = map_employee_from_ukg(employment_data)

        assert employee.supervisor_email == "manager@example.com"
        assert employee.supervisor_id == "SUP001"

    def test_dates_parsing(self):
        """Should parse hire and termination dates."""
        employment_data = {
            "employeeId": "EMP005",
            "employeeNumber": "33333",
            "firstName": "Charlie",
            "lastName": "Davis",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "terminationDate": "2024-06-30T00:00:00Z",
        }

        employee = map_employee_from_ukg(employment_data)

        assert employee.hire_date is not None
        assert employee.hire_date.year == 2020
        assert employee.hire_date.month == 1
        assert employee.termination_date is not None
        assert employee.termination_date.year == 2024

    def test_phone_normalization(self):
        """Should normalize phone number.

        Note: The UKG mapper normalizes phone to XXX-XXX-XXXX format,
        but the Employee model further normalizes to 10 digits only.
        """
        employment_data = {
            "employeeId": "EMP006",
            "employeeNumber": "44444",
            "firstName": "Dave",
            "lastName": "Evans",
            "employeeStatusCode": "A",
        }
        person_data = {
            "workPhone": "(555) 987-6543",
        }

        employee = map_employee_from_ukg(employment_data, person_data)

        # Employee model stores phone as digits only (10 digits for US)
        assert employee.phone == "5559876543"


class TestExtractSupervisorInfo:
    """Tests for extract_supervisor_info function."""

    def test_direct_fields(self):
        """Should extract supervisor info from direct fields."""
        data = {
            "supervisorEmailAddress": "boss@example.com",
            "supervisorEmployeeId": "SUP001",
            "supervisorEmployeeNumber": "99999",
        }

        info = extract_supervisor_info(data)

        assert info["supervisor_email"] == "boss@example.com"
        assert info["supervisor_id"] == "SUP001"
        assert info["supervisor_number"] == "99999"

    def test_nested_supervisor_object(self):
        """Should extract from nested supervisor object."""
        data = {
            "supervisor": {
                "emailAddress": "manager@example.com",
                "employeeId": "MGR001",
                "employeeNumber": "88888",
            }
        }

        info = extract_supervisor_info(data)

        assert info["supervisor_email"] == "manager@example.com"
        assert info["supervisor_id"] == "MGR001"
        assert info["supervisor_number"] == "88888"

    def test_prefers_direct_fields(self):
        """Should prefer direct fields over nested object."""
        data = {
            "supervisorEmailAddress": "direct@example.com",
            "supervisor": {
                "emailAddress": "nested@example.com",
            }
        }

        info = extract_supervisor_info(data)

        assert info["supervisor_email"] == "direct@example.com"

    def test_empty_data(self):
        """Should return empty strings for missing data."""
        info = extract_supervisor_info({})

        assert info["supervisor_email"] == ""
        assert info["supervisor_id"] == ""
        assert info["supervisor_number"] == ""
