"""Tests for business exceptions."""

import pytest

from src.domain.exceptions.business_exceptions import (
    UserValidationError,
    EmployeeNotFoundError,
    SupervisorNotFoundError,
)


class TestUserValidationError:
    """Test cases for UserValidationError."""

    def test_create_basic(self):
        """Test creating basic UserValidationError."""
        errors = ["Missing email"]
        error = UserValidationError(errors)

        assert error.errors == errors
        assert error.external_id is None
        assert "Missing email" in str(error)

    def test_create_with_multiple_errors(self):
        """Test creating UserValidationError with multiple errors."""
        errors = ["Missing email", "Invalid name"]
        error = UserValidationError(errors)

        assert len(error.errors) == 2
        assert "Missing email" in str(error)
        assert "Invalid name" in str(error)

    def test_create_with_external_id(self):
        """Test creating UserValidationError with external ID."""
        errors = ["Missing email"]
        error = UserValidationError(errors, external_id="12345")

        assert error.external_id == "12345"
        assert "[12345]" in str(error)

    def test_message_format_without_id(self):
        """Test message format without external ID."""
        error = UserValidationError(["Error 1", "Error 2"])
        message = str(error)

        assert "User validation failed:" in message
        assert "Error 1" in message
        assert "Error 2" in message

    def test_message_format_with_id(self):
        """Test message format with external ID."""
        error = UserValidationError(["Error 1"], external_id="12345")
        message = str(error)

        assert "[12345]" in message
        assert "User validation failed:" in message

    def test_is_exception(self):
        """Test UserValidationError is an Exception."""
        error = UserValidationError(["Test"])
        assert isinstance(error, Exception)


class TestEmployeeNotFoundError:
    """Test cases for EmployeeNotFoundError."""

    def test_create_basic(self):
        """Test creating basic EmployeeNotFoundError."""
        error = EmployeeNotFoundError("12345")

        assert error.employee_number == "12345"
        assert error.company_id is None
        assert "12345" in str(error)

    def test_create_with_company_id(self):
        """Test creating EmployeeNotFoundError with company ID."""
        error = EmployeeNotFoundError("12345", company_id="J9A6Y")

        assert error.employee_number == "12345"
        assert error.company_id == "J9A6Y"
        assert "J9A6Y" in str(error)

    def test_message_format(self):
        """Test message format."""
        error = EmployeeNotFoundError("12345", company_id="J9A6Y")
        message = str(error)

        assert "Employee not found: 12345" in message
        assert "(company: J9A6Y)" in message

    def test_message_format_without_company(self):
        """Test message format without company ID."""
        error = EmployeeNotFoundError("12345")
        message = str(error)

        assert "Employee not found: 12345" in message
        assert "company" not in message

    def test_is_exception(self):
        """Test EmployeeNotFoundError is an Exception."""
        error = EmployeeNotFoundError("12345")
        assert isinstance(error, Exception)


class TestSupervisorNotFoundError:
    """Test cases for SupervisorNotFoundError."""

    def test_create(self):
        """Test creating SupervisorNotFoundError."""
        error = SupervisorNotFoundError(
            supervisor_employee_number="99999",
            employee_number="12345",
        )

        assert error.supervisor_employee_number == "99999"
        assert error.employee_number == "12345"

    def test_message_format(self):
        """Test message format."""
        error = SupervisorNotFoundError(
            supervisor_employee_number="99999",
            employee_number="12345",
        )
        message = str(error)

        assert "Supervisor 99999 not found" in message
        assert "for employee 12345" in message

    def test_is_exception(self):
        """Test SupervisorNotFoundError is an Exception."""
        error = SupervisorNotFoundError(
            supervisor_employee_number="99999",
            employee_number="12345",
        )
        assert isinstance(error, Exception)


class TestExceptionCatching:
    """Test exception catching scenarios."""

    def test_catch_user_validation_error(self):
        """Test catching UserValidationError."""
        try:
            raise UserValidationError(["error1"])
        except UserValidationError as e:
            assert e.errors == ["error1"]

    def test_catch_employee_not_found_error(self):
        """Test catching EmployeeNotFoundError."""
        try:
            raise EmployeeNotFoundError("12345", company_id="J9A6Y")
        except EmployeeNotFoundError as e:
            assert e.employee_number == "12345"
            assert e.company_id == "J9A6Y"

    def test_catch_supervisor_not_found_error(self):
        """Test catching SupervisorNotFoundError."""
        try:
            raise SupervisorNotFoundError(
                supervisor_employee_number="99999",
                employee_number="12345",
            )
        except SupervisorNotFoundError as e:
            assert e.supervisor_employee_number == "99999"

    def test_exceptions_are_independent(self):
        """Test exceptions don't catch each other."""
        with pytest.raises(EmployeeNotFoundError):
            try:
                raise EmployeeNotFoundError("12345")
            except UserValidationError:
                pytest.fail("Should not catch unrelated exception")

    def test_catch_exception_catches_all(self):
        """Test catching Exception catches all business errors."""
        errors = [
            UserValidationError(["Test"]),
            EmployeeNotFoundError("12345"),
            SupervisorNotFoundError("99999", "12345"),
        ]

        for error in errors:
            try:
                raise error
            except Exception as e:
                assert e is error
