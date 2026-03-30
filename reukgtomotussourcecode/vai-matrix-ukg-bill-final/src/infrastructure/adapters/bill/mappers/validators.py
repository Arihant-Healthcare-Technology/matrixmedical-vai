"""
Validation mappers.

Provides validation functions for API submissions and error extraction.
"""

import re
from typing import Any, Dict, List

from src.domain.models.invoice import Invoice
from src.domain.models.payment import Payment
from src.domain.models.vendor import Vendor


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
