"""
Domain models - Core business entities.

This module exports all domain models for the UKG to BILL.com integration.
"""

from src.domain.models.employee import (
    Address,
    Employee,
    EmployeeStatus,
    EmployeeType,
)
from src.domain.models.bill_user import (
    BillRole,
    BillUser,
)
from src.domain.models.vendor import (
    PaymentMethod as VendorPaymentMethod,
    Vendor,
    VendorAddress,
    VendorStatus,
)
from src.domain.models.invoice import (
    BillStatus,
    Invoice,
    InvoiceLineItem,
)
from src.domain.models.payment import (
    BulkPaymentRequest,
    ExternalPayment,
    FundingAccount,
    FundingAccountType,
    Payment,
    PaymentMethod,
    PaymentStatus,
)

__all__ = [
    # Employee (UKG)
    "Address",
    "Employee",
    "EmployeeStatus",
    "EmployeeType",
    # BillUser (BILL S&E)
    "BillRole",
    "BillUser",
    # Vendor (BILL AP)
    "Vendor",
    "VendorAddress",
    "VendorPaymentMethod",
    "VendorStatus",
    # Invoice (BILL AP)
    "BillStatus",
    "Invoice",
    "InvoiceLineItem",
    # Payment (BILL AP)
    "BulkPaymentRequest",
    "ExternalPayment",
    "FundingAccount",
    "FundingAccountType",
    "Payment",
    "PaymentMethod",
    "PaymentStatus",
]
