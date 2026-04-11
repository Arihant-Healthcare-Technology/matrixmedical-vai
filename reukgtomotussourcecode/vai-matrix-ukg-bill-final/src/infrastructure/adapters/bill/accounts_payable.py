"""
BILL.com Accounts Payable repository implementations.

This module re-exports the repository classes and client for backward compatibility.
The components have been split into separate modules for better organization:

- accounts_payable_client.py: AccountsPayableClient
- vendor_repository.py: VendorRepositoryImpl
- invoice_repository.py: InvoiceRepositoryImpl
- payment_repository.py: PaymentRepositoryImpl

Usage:
    from src.infrastructure.adapters.bill.accounts_payable import (
        AccountsPayableClient,
        VendorRepositoryImpl,
        InvoiceRepositoryImpl,
        PaymentRepositoryImpl,
    )

Or import directly from the specific modules:
    from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient
    from src.infrastructure.adapters.bill.vendor_repository import VendorRepositoryImpl
    from src.infrastructure.adapters.bill.invoice_repository import InvoiceRepositoryImpl
    from src.infrastructure.adapters.bill.payment_repository import PaymentRepositoryImpl
"""

from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient
from src.infrastructure.adapters.bill.vendor_repository import VendorRepositoryImpl
from src.infrastructure.adapters.bill.invoice_repository import InvoiceRepositoryImpl
from src.infrastructure.adapters.bill.payment_repository import PaymentRepositoryImpl

__all__ = [
    "AccountsPayableClient",
    "VendorRepositoryImpl",
    "InvoiceRepositoryImpl",
    "PaymentRepositoryImpl",
]
