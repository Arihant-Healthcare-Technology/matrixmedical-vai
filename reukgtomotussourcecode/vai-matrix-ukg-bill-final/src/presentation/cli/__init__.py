"""
CLI presentation layer for UKG to BILL.com integration.

Provides command-line interface for:
- Spend & Expense (S&E) user synchronization
- Accounts Payable (AP) vendor/invoice/payment management
"""

from src.presentation.cli.main import main
from src.presentation.cli.container import Container, get_container, reset_container
from src.presentation.cli.utils import (
    confirm_action,
    format_currency,
    handle_cli_error,
    load_json_file,
    load_json_list,
    print_preview,
    print_step_header,
    print_summary,
    print_sync_result,
)

__all__ = [
    "main",
    "Container",
    "get_container",
    "reset_container",
    # CLI utilities
    "confirm_action",
    "format_currency",
    "handle_cli_error",
    "load_json_file",
    "load_json_list",
    "print_preview",
    "print_step_header",
    "print_summary",
    "print_sync_result",
]
