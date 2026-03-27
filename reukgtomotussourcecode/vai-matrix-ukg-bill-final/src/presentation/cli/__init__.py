"""
CLI presentation layer for UKG to BILL.com integration.

Provides command-line interface for:
- Spend & Expense (S&E) user synchronization
- Accounts Payable (AP) vendor/invoice/payment management
"""

from src.presentation.cli.main import main
from src.presentation.cli.container import Container, get_container, reset_container

__all__ = [
    "main",
    "Container",
    "get_container",
    "reset_container",
]
