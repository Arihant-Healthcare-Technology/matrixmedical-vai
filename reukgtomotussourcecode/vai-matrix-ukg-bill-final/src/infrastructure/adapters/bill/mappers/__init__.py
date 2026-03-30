"""
BILL.com data mappers.

Provides mapping functions to transform between domain models and BILL API formats.

This package is split into focused modules:
- common: Date parsing, formatting, and normalization utilities
- user_mappers: BillUser mapping functions
- vendor_mappers: Vendor mapping functions
- invoice_mappers: Invoice/Bill mapping functions
- payment_mappers: Payment mapping functions
- bulk_mappers: Bulk/batch operation mappers
- csv_mappers: CSV export mappers
- validators: Validation functions for API submissions
"""

# Common utilities
from .common import (
    format_cost_center,
    format_date,
    normalize_email,
    normalize_phone,
    parse_date,
    parse_decimal,
)

# User mappers
from .user_mappers import (
    build_bill_user_csv_row,
    map_bill_user_from_api,
    map_bill_user_to_api,
    map_employee_to_bill_user,
)

# Vendor mappers
from .vendor_mappers import (
    map_vendor_from_api,
    map_vendor_payment_method,
    map_vendor_status,
    map_vendor_to_api,
)

# Invoice mappers
from .invoice_mappers import (
    map_bill_status,
    map_invoice_from_api,
    map_invoice_to_api,
    map_line_items_from_api,
    map_line_items_to_api,
)

# Payment mappers
from .payment_mappers import (
    map_funding_account_from_api,
    map_payment_from_api,
    map_payment_method,
    map_payment_status,
    map_payment_to_api,
)

# Bulk mappers
from .bulk_mappers import (
    build_bulk_payment_payload,
    parse_bulk_payment_results,
)

# CSV mappers
from .csv_mappers import (
    build_invoice_csv_row,
    build_vendor_csv_row,
)

# Validators
from .validators import (
    extract_api_error,
    validate_invoice_for_api,
    validate_payment_for_api,
    validate_vendor_for_api,
)

__all__ = [
    # Common
    "parse_date",
    "format_date",
    "parse_decimal",
    "normalize_email",
    "format_cost_center",
    "normalize_phone",
    # User mappers
    "map_bill_user_from_api",
    "map_bill_user_to_api",
    "map_employee_to_bill_user",
    "build_bill_user_csv_row",
    # Vendor mappers
    "map_vendor_from_api",
    "map_vendor_to_api",
    "map_vendor_status",
    "map_vendor_payment_method",
    # Invoice mappers
    "map_invoice_from_api",
    "map_invoice_to_api",
    "map_bill_status",
    "map_line_items_from_api",
    "map_line_items_to_api",
    # Payment mappers
    "map_payment_from_api",
    "map_payment_to_api",
    "map_payment_status",
    "map_payment_method",
    "map_funding_account_from_api",
    # Bulk mappers
    "build_bulk_payment_payload",
    "parse_bulk_payment_results",
    # CSV mappers
    "build_vendor_csv_row",
    "build_invoice_csv_row",
    # Validators
    "extract_api_error",
    "validate_vendor_for_api",
    "validate_invoice_for_api",
    "validate_payment_for_api",
]
