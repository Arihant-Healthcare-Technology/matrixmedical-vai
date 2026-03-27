"""
Business logic exceptions for UKG-BILL integration.

These exceptions represent business-level errors that occur during
synchronization and data processing operations.
"""

from typing import Any, Dict, Optional

from src.domain.exceptions.base import IntegrationError, ValidationError


class EmployeeValidationError(ValidationError):
    """
    Raised when employee data validation fails.

    Examples:
        - Missing required employee fields
        - Invalid employee email format
        - Employee number format invalid
    """

    def __init__(
        self,
        message: str,
        employee_id: Optional[str] = None,
        employee_number: Optional[str] = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "employee_id": employee_id,
            "employee_number": employee_number,
        }
        super().__init__(
            message=message,
            field=field,
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.employee_id = employee_id
        self.employee_number = employee_number


class EmployeeSyncError(IntegrationError):
    """
    Raised when employee sync to BILL fails.

    Examples:
        - Failed to create user in BILL
        - Failed to update user in BILL
        - Network error during sync
    """

    def __init__(
        self,
        message: str,
        employee_id: Optional[str] = None,
        email: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "employee_id": employee_id,
            "action": action,
        }
        super().__init__(
            message=message,
            code="EMPLOYEE_SYNC_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.employee_id = employee_id
        self.email = email
        self.action = action


class VendorCreationError(IntegrationError):
    """
    Raised when vendor creation fails.

    Examples:
        - Duplicate vendor name
        - Invalid vendor data
        - API rejection
    """

    def __init__(
        self,
        message: str,
        vendor_name: Optional[str] = None,
        external_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "vendor_name": vendor_name,
            "external_id": external_id,
        }
        super().__init__(
            message=message,
            code="VENDOR_CREATION_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.vendor_name = vendor_name
        self.external_id = external_id


class InvoiceProcessingError(IntegrationError):
    """
    Raised when invoice processing fails.

    Examples:
        - Invalid invoice data
        - Vendor not found
        - Duplicate invoice number
    """

    def __init__(
        self,
        message: str,
        invoice_number: Optional[str] = None,
        vendor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "invoice_number": invoice_number,
            "vendor_id": vendor_id,
        }
        super().__init__(
            message=message,
            code="INVOICE_PROCESSING_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.invoice_number = invoice_number
        self.vendor_id = vendor_id


class PaymentAuthorizationError(IntegrationError):
    """
    Raised when payment authorization fails.

    Examples:
        - Insufficient funds
        - Payment method rejected
        - Authorization timeout
    """

    def __init__(
        self,
        message: str,
        payment_id: Optional[str] = None,
        amount: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "payment_id": payment_id,
        }
        super().__init__(
            message=message,
            code="PAYMENT_AUTH_ERROR",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.payment_id = payment_id
        self.amount = amount


class BudgetAssignmentError(ValidationError):
    """
    Raised when budget assignment (Direct/Indirect) fails.

    Examples:
        - Cannot determine direct labor status
        - Missing directLabor field
        - Invalid cost center for budget assignment
    """

    def __init__(
        self,
        message: str,
        employee_id: Optional[str] = None,
        cost_center: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "employee_id": employee_id,
            "cost_center": cost_center,
        }
        super().__init__(
            message=message,
            field="direct_labor",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.employee_id = employee_id
        self.cost_center = cost_center


class CostCenterMappingError(ValidationError):
    """
    Raised when cost center mapping fails.

    Examples:
        - Invalid cost center code
        - Cost center not found in mapping table
        - Missing cost center description
    """

    def __init__(
        self,
        message: str,
        cost_center_code: Optional[str] = None,
        employee_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details = {
            "cost_center_code": cost_center_code,
            "employee_id": employee_id,
        }
        super().__init__(
            message=message,
            field="cost_center",
            details={**(details or {}), **{k: v for k, v in extra_details.items() if v is not None}},
        )
        self.cost_center_code = cost_center_code
        self.employee_id = employee_id
