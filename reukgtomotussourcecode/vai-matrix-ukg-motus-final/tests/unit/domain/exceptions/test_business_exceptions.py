"""Tests for business exceptions."""

import pytest

from src.domain.exceptions.business_exceptions import (
    DriverValidationError,
    EmployeeNotFoundError,
    ProgramNotFoundError,
)


class TestDriverValidationError:
    """Test cases for DriverValidationError."""

    def test_create_basic(self):
        """Test creating basic DriverValidationError."""
        error = DriverValidationError("Validation failed")

        assert str(error) == "Validation failed"
        assert error.errors == []
        assert error.employee_number is None

    def test_create_with_errors(self):
        """Test creating DriverValidationError with error list."""
        errors = ["Missing email", "Invalid phone number"]
        error = DriverValidationError("Validation failed", errors=errors)

        assert error.errors == errors
        assert len(error.errors) == 2

    def test_create_with_employee_number(self):
        """Test creating DriverValidationError with employee number."""
        error = DriverValidationError(
            "Validation failed",
            employee_number="12345",
        )

        assert error.employee_number == "12345"

    def test_create_with_all_params(self):
        """Test creating DriverValidationError with all parameters."""
        errors = ["Missing email"]
        error = DriverValidationError(
            "Driver 12345 failed validation",
            errors=errors,
            employee_number="12345",
        )

        assert str(error) == "Driver 12345 failed validation"
        assert error.errors == errors
        assert error.employee_number == "12345"

    def test_errors_default_to_empty_list(self):
        """Test errors defaults to empty list, not None."""
        error = DriverValidationError("Test", errors=None)

        assert error.errors == []
        assert isinstance(error.errors, list)

    def test_is_exception(self):
        """Test DriverValidationError is an Exception."""
        error = DriverValidationError("Test")
        assert isinstance(error, Exception)


class TestEmployeeNotFoundError:
    """Test cases for EmployeeNotFoundError."""

    def test_create_basic(self):
        """Test creating basic EmployeeNotFoundError."""
        error = EmployeeNotFoundError("Employee not found")

        assert str(error) == "Employee not found"
        assert error.employee_number is None
        assert error.company_id is None

    def test_create_with_employee_number(self):
        """Test creating EmployeeNotFoundError with employee number."""
        error = EmployeeNotFoundError(
            "Employee not found",
            employee_number="12345",
        )

        assert error.employee_number == "12345"

    def test_create_with_company_id(self):
        """Test creating EmployeeNotFoundError with company ID."""
        error = EmployeeNotFoundError(
            "Employee not found",
            company_id="J9A6Y",
        )

        assert error.company_id == "J9A6Y"

    def test_create_with_all_params(self):
        """Test creating EmployeeNotFoundError with all parameters."""
        error = EmployeeNotFoundError(
            "Employee 12345 not found in company J9A6Y",
            employee_number="12345",
            company_id="J9A6Y",
        )

        assert str(error) == "Employee 12345 not found in company J9A6Y"
        assert error.employee_number == "12345"
        assert error.company_id == "J9A6Y"

    def test_is_exception(self):
        """Test EmployeeNotFoundError is an Exception."""
        error = EmployeeNotFoundError("Test")
        assert isinstance(error, Exception)


class TestProgramNotFoundError:
    """Test cases for ProgramNotFoundError."""

    def test_create_basic(self):
        """Test creating basic ProgramNotFoundError."""
        error = ProgramNotFoundError("Program not found")

        assert str(error) == "Program not found"
        assert error.job_code is None
        assert error.employee_number is None

    def test_create_with_job_code(self):
        """Test creating ProgramNotFoundError with job code."""
        error = ProgramNotFoundError(
            "Program not found",
            job_code="9999",
        )

        assert error.job_code == "9999"

    def test_create_with_employee_number(self):
        """Test creating ProgramNotFoundError with employee number."""
        error = ProgramNotFoundError(
            "Program not found",
            employee_number="12345",
        )

        assert error.employee_number == "12345"

    def test_create_with_all_params(self):
        """Test creating ProgramNotFoundError with all parameters."""
        error = ProgramNotFoundError(
            "No program mapped for job code 9999",
            job_code="9999",
            employee_number="12345",
        )

        assert str(error) == "No program mapped for job code 9999"
        assert error.job_code == "9999"
        assert error.employee_number == "12345"

    def test_is_exception(self):
        """Test ProgramNotFoundError is an Exception."""
        error = ProgramNotFoundError("Test")
        assert isinstance(error, Exception)


class TestExceptionCatching:
    """Test exception catching scenarios."""

    def test_catch_driver_validation_error(self):
        """Test catching DriverValidationError."""
        try:
            raise DriverValidationError("Test", errors=["error1"])
        except DriverValidationError as e:
            assert e.errors == ["error1"]

    def test_catch_employee_not_found_error(self):
        """Test catching EmployeeNotFoundError."""
        try:
            raise EmployeeNotFoundError("Test", employee_number="12345")
        except EmployeeNotFoundError as e:
            assert e.employee_number == "12345"

    def test_catch_program_not_found_error(self):
        """Test catching ProgramNotFoundError."""
        try:
            raise ProgramNotFoundError("Test", job_code="9999")
        except ProgramNotFoundError as e:
            assert e.job_code == "9999"

    def test_exceptions_are_independent(self):
        """Test exceptions don't catch each other."""
        # DriverValidationError should not catch EmployeeNotFoundError
        with pytest.raises(EmployeeNotFoundError):
            try:
                raise EmployeeNotFoundError("Test")
            except DriverValidationError:
                pytest.fail("Should not catch unrelated exception")

    def test_catch_exception_catches_all(self):
        """Test catching Exception catches all business errors."""
        errors = [
            DriverValidationError("Test"),
            EmployeeNotFoundError("Test"),
            ProgramNotFoundError("Test"),
        ]

        for error in errors:
            try:
                raise error
            except Exception as e:
                assert e is error
