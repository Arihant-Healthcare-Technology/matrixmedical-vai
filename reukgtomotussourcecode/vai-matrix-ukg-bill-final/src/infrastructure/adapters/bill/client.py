"""
BILL.com API clients.

This module re-exports the client classes for backward compatibility.
The clients have been split into separate modules for better organization:

- base_client.py: BillClient base class
- spend_expense_client.py: SpendExpenseClient for S&E operations
- accounts_payable_client.py: AccountsPayableClient for AP operations

Usage:
    from src.infrastructure.adapters.bill.client import (
        BillClient,
        SpendExpenseClient,
        AccountsPayableClient,
    )

Or import directly from the specific modules:
    from src.infrastructure.adapters.bill.base_client import BillClient
    from src.infrastructure.adapters.bill.spend_expense_client import SpendExpenseClient
    from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient
"""

from src.infrastructure.adapters.bill.base_client import BillClient
from src.infrastructure.adapters.bill.spend_expense_client import SpendExpenseClient
from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient

# Re-export BillHttpClient for backward compatibility with tests
from src.infrastructure.http.client import BillHttpClient

__all__ = [
    "BillClient",
    "BillHttpClient",
    "SpendExpenseClient",
    "AccountsPayableClient",
]
