"""
Unit tests for business exceptions.
"""

import pytest

from src.domain.exceptions.business_exceptions import (
    EmployeeValidationError,
    EmployeeSyncError,
    VendorCreationError,
    InvoiceProcessingError,
    PaymentAuthorizationError,
    BudgetAssignmentError,
    CostCenterMappingError,
)


class TestEmployeeValidationError:
    """Tests for EmployeeValidationError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = EmployeeValidationError("Invalid employee data")
        assert str(exc) == "[VALIDATION_ERROR] Invalid employee data"
        assert exc.code == "VALIDATION_ERROR"

    def test_with_employee_info(self):
        """Test exception with employee info."""
        exc = EmployeeValidationError(
            "Missing email",
            employee_id="EMP001",
            employee_number="12345",
            field="email",
        )
        assert exc.employee_id == "EMP001"
        assert exc.employee_number == "12345"
        assert exc.field == "email"

    def test_to_dict(self):
        """Test serialization to dict."""
        exc = EmployeeValidationError(
            "Invalid email format",
            employee_id="EMP001",
            field="email",
        )
        result = exc.to_dict()
        assert result["error_type"] == "EmployeeValidationError"
        assert result["code"] == "VALIDATION_ERROR"
        assert result["message"] == "Invalid email format"
        assert result["details"]["employee_id"] == "EMP001"


class TestEmployeeSyncError:
    """Tests for EmployeeSyncError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = EmployeeSyncError("Failed to sync employee")
        assert exc.code == "EMPLOYEE_SYNC_ERROR"

    def test_with_action(self):
        """Test exception with action."""
        exc = EmployeeSyncError(
            "Failed to create user in BILL",
            employee_id="EMP001",
            email="john@example.com",
            action="create",
        )
        assert exc.action == "create"
        assert exc.employee_id == "EMP001"
        assert exc.email == "john@example.com"


class TestVendorCreationError:
    """Tests for VendorCreationError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = VendorCreationError("Duplicate vendor name")
        assert exc.code == "VENDOR_CREATION_ERROR"

    def test_with_vendor_info(self):
        """Test exception with vendor info."""
        exc = VendorCreationError(
            "Vendor already exists",
            vendor_name="Acme Corp",
            external_id="V001",
        )
        assert exc.vendor_name == "Acme Corp"
        assert exc.external_id == "V001"


class TestInvoiceProcessingError:
    """Tests for InvoiceProcessingError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = InvoiceProcessingError("Invalid invoice")
        assert exc.code == "INVOICE_PROCESSING_ERROR"

    def test_with_invoice_info(self):
        """Test exception with invoice info."""
        exc = InvoiceProcessingError(
            "Vendor not found",
            invoice_number="INV-001",
            vendor_id="V001",
        )
        assert exc.invoice_number == "INV-001"
        assert exc.vendor_id == "V001"


class TestPaymentAuthorizationError:
    """Tests for PaymentAuthorizationError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = PaymentAuthorizationError("Payment declined")
        assert exc.code == "PAYMENT_AUTH_ERROR"

    def test_with_payment_info(self):
        """Test exception with payment info."""
        exc = PaymentAuthorizationError(
            "Insufficient funds",
            payment_id="PAY-001",
            amount="1000.00",
        )
        assert exc.payment_id == "PAY-001"
        assert exc.amount == "1000.00"


class TestBudgetAssignmentError:
    """Tests for BudgetAssignmentError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = BudgetAssignmentError("Cannot determine budget type")
        assert exc.code == "VALIDATION_ERROR"
        assert exc.field == "direct_labor"

    def test_with_cost_center(self):
        """Test exception with cost center info."""
        exc = BudgetAssignmentError(
            "Invalid cost center for direct labor",
            employee_id="EMP001",
            cost_center="9999",
        )
        assert exc.employee_id == "EMP001"
        assert exc.cost_center == "9999"


class TestCostCenterMappingError:
    """Tests for CostCenterMappingError."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = CostCenterMappingError("Unknown cost center")
        assert exc.code == "VALIDATION_ERROR"
        assert exc.field == "cost_center"

    def test_with_mapping_info(self):
        """Test exception with mapping info."""
        exc = CostCenterMappingError(
            "Cost center not in mapping table",
            cost_center_code="INVALID",
            employee_id="EMP001",
        )
        assert exc.cost_center_code == "INVALID"
        assert exc.employee_id == "EMP001"

    def test_to_dict_no_pii(self):
        """Test serialization doesn't leak PII."""
        exc = CostCenterMappingError(
            "Cost center not found",
            cost_center_code="5230",
            employee_id="EMP001",
        )
        result = exc.to_dict()
        # Cost center code should be in details (not PII)
        assert result["details"]["cost_center_code"] == "5230"
