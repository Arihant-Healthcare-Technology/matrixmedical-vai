"""
BILL.com data mappers.

Provides mapping functions to transform between domain models and BILL API formats.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.models.bill_user import BillRole, BillUser
from src.domain.models.employee import Employee
from src.domain.models.invoice import BillStatus, Invoice, InvoiceLineItem
from src.domain.models.payment import (
    FundingAccount,
    FundingAccountType,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from src.domain.models.vendor import PaymentMethod as VendorPaymentMethod
from src.domain.models.vendor import Vendor, VendorAddress, VendorStatus


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse BILL date string to date object.

    Handles formats:
    - ISO 8601: 2024-01-15T00:00:00Z
    - ISO date: 2024-01-15

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date or None
    """
    if not date_str:
        return None

    try:
        # Handle ISO 8601 with timezone
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.date()
    except Exception:
        try:
            # Handle plain date
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def format_date(d: Optional[date]) -> str:
    """
    Format date to BILL API format (YYYY-MM-DD).

    Args:
        d: Date to format

    Returns:
        Formatted date string or empty string
    """
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def parse_decimal(value: Any) -> Decimal:
    """
    Parse value to Decimal for monetary amounts.

    Args:
        value: Value to parse (str, int, float, Decimal)

    Returns:
        Decimal value
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def normalize_email(email: Optional[str]) -> str:
    """
    Normalize email address.

    Args:
        email: Email to normalize

    Returns:
        Lowercase trimmed email
    """
    if not email:
        return ""
    return email.lower().strip()


def format_cost_center(code: str, description: str) -> str:
    """
    Format cost center as 'CODE – Description'.

    Client expects format: "5230 – Cost Center Name"

    Args:
        code: Cost center code
        description: Cost center description

    Returns:
        Formatted cost center string
    """
    if not code:
        return ""
    if not description:
        return code
    return f"{code} – {description}"


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize phone number to XXX-XXX-XXXX format for US numbers.

    Args:
        phone: Phone string to normalize

    Returns:
        Normalized phone string
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"{digits[1:4]}-{digits[4:7]}-{digits[7:11]}"
    return phone


# =============================================================================
# BillUser Mappers
# =============================================================================


def map_bill_user_from_api(data: Dict[str, Any]) -> BillUser:
    """
    Map BILL S&E API response to BillUser domain model.

    Args:
        data: API response data

    Returns:
        BillUser domain model
    """
    return BillUser.from_bill_api(data)


def map_bill_user_to_api(user: BillUser) -> Dict[str, Any]:
    """
    Map BillUser domain model to API payload.

    Args:
        user: BillUser domain model

    Returns:
        API payload dict
    """
    return user.to_api_payload()


def map_employee_to_bill_user(
    employee: Employee,
    role: Optional[BillRole] = None,
    manager_email: Optional[str] = None,
) -> BillUser:
    """
    Map Employee domain model to BillUser for S&E provisioning.

    Args:
        employee: Source Employee
        role: Optional role override (defaults to MEMBER)
        manager_email: Optional manager email override

    Returns:
        BillUser domain model
    """
    return BillUser.from_employee(
        employee,
        role=role,
        manager_email=manager_email,
    )


def build_bill_user_csv_row(user: BillUser) -> Dict[str, str]:
    """
    Build CSV row for BILL bulk import.

    Uses BillUser.to_csv_row() which includes cost center and budget assignment.

    Args:
        user: BillUser to export

    Returns:
        Dict suitable for csv.DictWriter with columns:
        - first name, last name, email address, role, manager
        - cost center (formatted as "CODE – Description")
        - budget count ("Direct" or "Indirect")
    """
    return user.to_csv_row()


# =============================================================================
# Vendor Mappers
# =============================================================================


def map_vendor_from_api(data: Dict[str, Any]) -> Vendor:
    """
    Map BILL AP API response to Vendor domain model.

    Args:
        data: API response data

    Returns:
        Vendor domain model
    """
    return Vendor.from_bill_api(data)


def map_vendor_to_api(vendor: Vendor) -> Dict[str, Any]:
    """
    Map Vendor domain model to API payload.

    Args:
        vendor: Vendor domain model

    Returns:
        API payload dict
    """
    return vendor.to_api_payload()


def map_vendor_status(status_str: Optional[str]) -> VendorStatus:
    """
    Map API status string to VendorStatus enum.

    Args:
        status_str: Status from API (active, inactive, archived)

    Returns:
        VendorStatus enum value
    """
    if not status_str:
        return VendorStatus.ACTIVE

    status_lower = status_str.lower().strip()

    if status_lower in ("inactive", "retired"):
        return VendorStatus.INACTIVE
    elif status_lower == "archived":
        return VendorStatus.ARCHIVED
    else:
        return VendorStatus.ACTIVE


def map_vendor_payment_method(method_str: Optional[str]) -> VendorPaymentMethod:
    """
    Map API payment method string to enum.

    Args:
        method_str: Payment method from API

    Returns:
        PaymentMethod enum value
    """
    if not method_str:
        return VendorPaymentMethod.CHECK

    method_upper = method_str.upper().strip()

    method_map = {
        "ACH": VendorPaymentMethod.ACH,
        "CHECK": VendorPaymentMethod.CHECK,
        "WIRE": VendorPaymentMethod.WIRE,
        "CARD_ACCOUNT": VendorPaymentMethod.CARD_ACCOUNT,
        "CARD": VendorPaymentMethod.CARD_ACCOUNT,
        "VIRTUAL_CARD": VendorPaymentMethod.CARD_ACCOUNT,
    }

    return method_map.get(method_upper, VendorPaymentMethod.CHECK)


# =============================================================================
# Invoice/Bill Mappers
# =============================================================================


def map_invoice_from_api(data: Dict[str, Any]) -> Invoice:
    """
    Map BILL AP API response to Invoice domain model.

    Args:
        data: API response data

    Returns:
        Invoice domain model
    """
    return Invoice.from_bill_api(data)


def map_invoice_to_api(invoice: Invoice) -> Dict[str, Any]:
    """
    Map Invoice domain model to API payload.

    Args:
        invoice: Invoice domain model

    Returns:
        API payload dict
    """
    return invoice.to_api_payload()


def map_bill_status(status_str: Optional[str]) -> BillStatus:
    """
    Map API status string to BillStatus enum.

    Args:
        status_str: Status from API

    Returns:
        BillStatus enum value
    """
    if not status_str:
        return BillStatus.OPEN

    status_lower = status_str.lower().strip()

    status_map = {
        "open": BillStatus.OPEN,
        "approved": BillStatus.APPROVED,
        "scheduled": BillStatus.SCHEDULED,
        "processing": BillStatus.PROCESSING,
        "paid": BillStatus.PAID,
        "partial": BillStatus.PARTIAL,
        "voided": BillStatus.VOIDED,
        "void": BillStatus.VOIDED,
    }

    return status_map.get(status_lower, BillStatus.OPEN)


def map_line_items_from_api(items_data: List[Dict[str, Any]]) -> List[InvoiceLineItem]:
    """
    Map API line items to domain models.

    Args:
        items_data: List of line item dicts from API

    Returns:
        List of InvoiceLineItem domain models
    """
    result = []
    for item in items_data:
        line = InvoiceLineItem.from_dict(item)
        result.append(line)
    return result


def map_line_items_to_api(items: List[InvoiceLineItem]) -> List[Dict[str, Any]]:
    """
    Map domain line items to API format.

    Args:
        items: List of InvoiceLineItem domain models

    Returns:
        List of dicts for API payload
    """
    return [item.to_api_payload() for item in items]


# =============================================================================
# Payment Mappers
# =============================================================================


def map_payment_from_api(data: Dict[str, Any]) -> Payment:
    """
    Map BILL AP API response to Payment domain model.

    Args:
        data: API response data

    Returns:
        Payment domain model
    """
    return Payment.from_bill_api(data)


def map_payment_to_api(payment: Payment) -> Dict[str, Any]:
    """
    Map Payment domain model to API payload.

    Args:
        payment: Payment domain model

    Returns:
        API payload dict
    """
    return payment.to_api_payload()


def map_payment_status(status_str: Optional[str]) -> PaymentStatus:
    """
    Map API status string to PaymentStatus enum.

    Args:
        status_str: Status from API

    Returns:
        PaymentStatus enum value
    """
    if not status_str:
        return PaymentStatus.PENDING

    status_upper = status_str.upper().strip()

    status_map = {
        "PENDING": PaymentStatus.PENDING,
        "SCHEDULED": PaymentStatus.SCHEDULED,
        "PROCESSING": PaymentStatus.PROCESSING,
        "IN_PROGRESS": PaymentStatus.PROCESSING,
        "COMPLETED": PaymentStatus.COMPLETED,
        "PAID": PaymentStatus.COMPLETED,
        "FAILED": PaymentStatus.FAILED,
        "ERROR": PaymentStatus.FAILED,
        "CANCELLED": PaymentStatus.CANCELLED,
        "CANCELED": PaymentStatus.CANCELLED,
        "VOIDED": PaymentStatus.VOIDED,
        "VOID": PaymentStatus.VOIDED,
    }

    return status_map.get(status_upper, PaymentStatus.PENDING)


def map_payment_method(method_str: Optional[str]) -> PaymentMethod:
    """
    Map API payment method string to enum.

    Args:
        method_str: Payment method from API

    Returns:
        PaymentMethod enum value
    """
    if not method_str:
        return PaymentMethod.CHECK

    method_upper = method_str.upper().strip()

    method_map = {
        "ACH": PaymentMethod.ACH,
        "CHECK": PaymentMethod.CHECK,
        "WIRE": PaymentMethod.WIRE,
        "CARD_ACCOUNT": PaymentMethod.CARD_ACCOUNT,
        "CARD": PaymentMethod.CARD_ACCOUNT,
        "VIRTUAL_CARD": PaymentMethod.CARD_ACCOUNT,
    }

    return method_map.get(method_upper, PaymentMethod.CHECK)


def map_funding_account_from_api(data: Dict[str, Any]) -> Optional[FundingAccount]:
    """
    Map API funding account data to domain model.

    Args:
        data: Funding account data from API

    Returns:
        FundingAccount or None
    """
    if not data:
        return None

    account_id = data.get("id") or data.get("accountId")
    if not account_id:
        return None

    account_type_str = data.get("type", "BANK_ACCOUNT")
    try:
        account_type = FundingAccountType(account_type_str)
    except ValueError:
        account_type = FundingAccountType.BANK_ACCOUNT

    return FundingAccount(
        id=account_id,
        account_type=account_type,
    )


# =============================================================================
# Bulk/Batch Mappers
# =============================================================================


def build_bulk_payment_payload(payments: List[Payment]) -> Dict[str, Any]:
    """
    Build bulk payment API payload.

    Args:
        payments: List of Payment domain models

    Returns:
        Bulk payment API payload
    """
    return {
        "payments": [p.to_api_payload() for p in payments],
    }


def parse_bulk_payment_results(
    data: Dict[str, Any],
) -> List[Payment]:
    """
    Parse bulk payment API response.

    Args:
        data: API response data

    Returns:
        List of created Payment domain models
    """
    results = data.get("results", [])
    payments = []

    for result in results:
        if result.get("id"):
            payment = Payment.from_bill_api(result)
            payments.append(payment)

    return payments


# =============================================================================
# CSV Export Mappers
# =============================================================================


def build_vendor_csv_row(vendor: Vendor) -> Dict[str, str]:
    """
    Build CSV row for vendor export.

    Args:
        vendor: Vendor to export

    Returns:
        Dict suitable for csv.DictWriter
    """
    return {
        "name": vendor.name,
        "short_name": vendor.short_name or "",
        "email": vendor.email or "",
        "phone": vendor.phone or "",
        "address_line1": vendor.address.line1 if vendor.address else "",
        "address_line2": vendor.address.line2 if vendor.address else "",
        "city": vendor.address.city if vendor.address else "",
        "state": vendor.address.state if vendor.address else "",
        "zip": vendor.address.zip_code if vendor.address else "",
        "country": vendor.address.country if vendor.address else "US",
        "payment_method": vendor.payment_method.value if vendor.payment_method else "CHECK",
        "payment_term_days": str(vendor.payment_term_days or 30),
        "external_id": vendor.external_id or "",
    }


def build_invoice_csv_row(invoice: Invoice) -> Dict[str, str]:
    """
    Build CSV row for invoice export.

    Args:
        invoice: Invoice to export

    Returns:
        Dict suitable for csv.DictWriter
    """
    # Get description from first line item if available
    description = ""
    if invoice.line_items:
        description = invoice.line_items[0].description or ""

    # Calculate total from line items if not set
    total_amount = invoice.total_amount
    if total_amount is None and invoice.line_items:
        total_amount = sum(item.amount for item in invoice.line_items)

    return {
        "invoice_number": invoice.invoice_number,
        "vendor_id": invoice.vendor_id,
        "invoice_date": format_date(invoice.invoice_date),
        "due_date": format_date(invoice.due_date),
        "amount": str(total_amount) if total_amount is not None else "0",
        "status": invoice.status.value if invoice.status else "open",
        "description": description,
        "external_id": invoice.external_id or "",
    }


# =============================================================================
# Validation Mappers
# =============================================================================


def extract_api_error(response_data: Dict[str, Any]) -> str:
    """
    Extract error message from BILL API error response.

    Args:
        response_data: API response data

    Returns:
        Human-readable error message
    """
    if not response_data:
        return "Unknown API error"

    # Check for standard error structure
    if "error" in response_data:
        error = response_data["error"]
        if isinstance(error, str):
            return error
        if isinstance(error, dict):
            return error.get("message", str(error))

    # Check for message field
    if "message" in response_data:
        return response_data["message"]

    # Check for errors array
    if "errors" in response_data:
        errors = response_data["errors"]
        if isinstance(errors, list) and errors:
            return "; ".join(
                e.get("message", str(e)) if isinstance(e, dict) else str(e)
                for e in errors
            )

    # Fallback
    return str(response_data)


def validate_vendor_for_api(vendor: Vendor) -> List[str]:
    """
    Validate vendor before API submission.

    Args:
        vendor: Vendor to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not vendor.name or len(vendor.name.strip()) < 2:
        errors.append("Vendor name is required (min 2 characters)")

    if vendor.email:
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, vendor.email):
            errors.append(f"Invalid vendor email format: {vendor.email}")

    return errors


def validate_invoice_for_api(invoice: Invoice) -> List[str]:
    """
    Validate invoice before API submission.

    Args:
        invoice: Invoice to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not invoice.invoice_number:
        errors.append("Invoice number is required")

    if not invoice.vendor_id:
        errors.append("Vendor ID is required")

    if not invoice.line_items:
        errors.append("At least one line item is required")

    # Calculate total from line items if not set
    total_amount = invoice.total_amount
    if total_amount is None and invoice.line_items:
        total_amount = sum(item.amount for item in invoice.line_items)

    if total_amount is None or total_amount <= 0:
        errors.append("Invoice total amount must be positive")

    if invoice.due_date and invoice.invoice_date:
        if invoice.due_date < invoice.invoice_date:
            errors.append("Due date cannot be before invoice date")

    return errors


def validate_payment_for_api(payment: Payment) -> List[str]:
    """
    Validate payment before API submission.

    Args:
        payment: Payment to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not payment.bill_id:
        errors.append("Bill ID is required")

    if payment.amount <= 0:
        errors.append("Payment amount must be positive")

    if not payment.funding_account:
        errors.append("Funding account is required")

    return errors
