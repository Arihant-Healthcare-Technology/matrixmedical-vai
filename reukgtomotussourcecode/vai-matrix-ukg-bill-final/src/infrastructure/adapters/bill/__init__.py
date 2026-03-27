"""
BILL.com API adapters.

Provides API clients and repository implementations for:
- Spend & Expense (S&E) - User provisioning
- Accounts Payable (AP) - Vendor, invoice, and payment management
"""

from src.infrastructure.adapters.bill.client import (
    AccountsPayableClient,
    BillClient,
    SpendExpenseClient,
)
from src.infrastructure.adapters.bill.spend_expense import BillUserRepositoryImpl
from src.infrastructure.adapters.bill.accounts_payable import (
    InvoiceRepositoryImpl,
    PaymentRepositoryImpl,
    VendorRepositoryImpl,
)
from src.infrastructure.adapters.bill.mappers import (
    # Utilities
    format_date,
    normalize_email,
    normalize_phone,
    parse_date,
    parse_decimal,
    # BillUser mappers
    build_bill_user_csv_row,
    map_bill_user_from_api,
    map_bill_user_to_api,
    map_employee_to_bill_user,
    # Vendor mappers
    build_vendor_csv_row,
    map_vendor_from_api,
    map_vendor_payment_method,
    map_vendor_status,
    map_vendor_to_api,
    # Invoice mappers
    build_invoice_csv_row,
    map_bill_status,
    map_invoice_from_api,
    map_invoice_to_api,
    map_line_items_from_api,
    map_line_items_to_api,
    # Payment mappers
    build_bulk_payment_payload,
    map_funding_account_from_api,
    map_payment_from_api,
    map_payment_method,
    map_payment_status,
    map_payment_to_api,
    parse_bulk_payment_results,
    # Validation
    extract_api_error,
    validate_invoice_for_api,
    validate_payment_for_api,
    validate_vendor_for_api,
)

__all__ = [
    # Base client
    "BillClient",
    # S&E
    "SpendExpenseClient",
    "BillUserRepositoryImpl",
    # AP
    "AccountsPayableClient",
    "VendorRepositoryImpl",
    "InvoiceRepositoryImpl",
    "PaymentRepositoryImpl",
    # Utilities
    "format_date",
    "normalize_email",
    "normalize_phone",
    "parse_date",
    "parse_decimal",
    # BillUser mappers
    "build_bill_user_csv_row",
    "map_bill_user_from_api",
    "map_bill_user_to_api",
    "map_employee_to_bill_user",
    # Vendor mappers
    "build_vendor_csv_row",
    "map_vendor_from_api",
    "map_vendor_payment_method",
    "map_vendor_status",
    "map_vendor_to_api",
    # Invoice mappers
    "build_invoice_csv_row",
    "map_bill_status",
    "map_invoice_from_api",
    "map_invoice_to_api",
    "map_line_items_from_api",
    "map_line_items_to_api",
    # Payment mappers
    "build_bulk_payment_payload",
    "map_funding_account_from_api",
    "map_payment_from_api",
    "map_payment_method",
    "map_payment_status",
    "map_payment_to_api",
    "parse_bulk_payment_results",
    # Validation
    "extract_api_error",
    "validate_invoice_for_api",
    "validate_payment_for_api",
    "validate_vendor_for_api",
]
