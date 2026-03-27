"""
Infrastructure adapters.

External system integrations:
- UKG Pro API adapter
- BILL.com API adapters (S&E and AP)
"""

from src.infrastructure.adapters.ukg import (
    UKGClient,
    UKGEmployeeRepository,
    map_address,
    map_employee_from_ukg,
    map_employment_status,
    normalize_phone,
    parse_date,
    extract_supervisor_info,
)
from src.infrastructure.adapters.bill import (
    BillClient,
    SpendExpenseClient,
    AccountsPayableClient,
    BillUserRepositoryImpl,
    VendorRepositoryImpl,
    InvoiceRepositoryImpl,
    PaymentRepositoryImpl,
)

__all__ = [
    # UKG
    "UKGClient",
    "UKGEmployeeRepository",
    "map_address",
    "map_employee_from_ukg",
    "map_employment_status",
    "normalize_phone",
    "parse_date",
    "extract_supervisor_info",
    # BILL
    "BillClient",
    "SpendExpenseClient",
    "AccountsPayableClient",
    "BillUserRepositoryImpl",
    "VendorRepositoryImpl",
    "InvoiceRepositoryImpl",
    "PaymentRepositoryImpl",
]
