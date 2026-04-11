"""
CLI utility functions - Shared utilities for CLI commands.

Provides common patterns for:
- JSON file loading with error handling
- Result formatting and printing
- Preview formatting
- CLI error handling
"""

import json
import logging
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


def load_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load and parse JSON file with proper error handling.

    Args:
        file_path: Path to JSON file.

    Returns:
        Parsed JSON data.

    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If JSON is invalid.
    """
    path = Path(file_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_list(
    file_path: Union[str, Path],
    key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load JSON file and return as list.

    Handles both array-style JSON and object with nested array.

    Args:
        file_path: Path to JSON file.
        key: Optional key if data is nested in an object.

    Returns:
        List of items from the JSON file.

    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If JSON is invalid.
    """
    data = load_json_file(file_path)

    if isinstance(data, list):
        return data

    if key and key in data:
        return data[key]

    # Try common keys
    for common_key in ["items", "data", "records"]:
        if common_key in data:
            return data[common_key]

    return []


def handle_cli_error(func: Callable[..., int]) -> Callable[..., int]:
    """
    Decorator for CLI commands with standardized error handling.

    Catches common exceptions and returns appropriate exit codes.

    Args:
        func: CLI command function.

    Returns:
        Wrapped function with error handling.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return 1
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return 1
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return 1
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            return 130
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            return 1

    return wrapper


def print_preview(
    items: List[Any],
    label: str,
    max_items: int = 10,
    formatter: Optional[Callable[[Any], str]] = None,
) -> None:
    """
    Print preview of items to be processed.

    Args:
        items: List of items to preview.
        label: Label describing what's being previewed.
        max_items: Maximum items to show.
        formatter: Optional function to format each item.
    """
    preview_items = items[:max_items]
    remaining = len(items) - len(preview_items)

    print(f"\n=== Preview: {label} (showing {len(preview_items)} of {len(items)}) ===")

    for item in preview_items:
        if formatter:
            print(f"  - {formatter(item)}")
        else:
            print(f"  - {_format_item_default(item)}")

    if remaining > 0:
        print(f"  ... and {remaining} more")

    print()


def _format_item_default(item: Any) -> str:
    """Default formatter for preview items."""
    # Invoice/bill-like
    if hasattr(item, "invoice_number") and hasattr(item, "total_amount"):
        return f"{item.invoice_number} (${item.total_amount})"

    # Employee-like
    if hasattr(item, "email") and hasattr(item, "full_name"):
        return f"{item.email} ({item.full_name})"

    # Vendor-like
    if hasattr(item, "name") and hasattr(item, "email"):
        return f"{item.name} ({item.email})"

    # Named entity
    if hasattr(item, "name"):
        return str(item.name)

    # Dict with common keys
    if isinstance(item, dict):
        if "name" in item:
            return item["name"]
        if "email" in item:
            return item["email"]
        if "id" in item:
            return str(item["id"])

    return str(item)


def print_sync_result(
    result: Any,
    title: str = "SYNC RESULT",
    show_errors: bool = True,
    max_errors: int = 10,
) -> None:
    """
    Print sync result summary.

    Args:
        result: BatchSyncResult or similar object with sync stats.
        title: Title for the result block.
        show_errors: Whether to print individual errors.
        max_errors: Maximum errors to print.
    """
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)

    # Core stats
    print(f"Total Processed:  {result.total}")
    print(f"Created:          {result.created}")
    print(f"Updated:          {result.updated}")
    print(f"Skipped:          {result.skipped}")
    print(f"Errors:           {result.errors}")

    # Success rate
    if hasattr(result, "success_rate"):
        print(f"Success Rate:     {result.success_rate:.1f}%")

    # Duration (may not always be present)
    if hasattr(result, "duration") and result.duration is not None:
        print(f"Duration:         {result.duration:.1f}s")

    # Correlation ID
    if hasattr(result, "correlation_id") and result.correlation_id:
        print(f"Correlation ID:   {result.correlation_id}")

    print("=" * 50 + "\n")

    # Print errors if any
    if show_errors and result.errors > 0 and hasattr(result, "results"):
        print("Errors:")
        error_count = 0
        for r in result.results:
            if hasattr(r, "action") and r.action == "error":
                entity_id = getattr(r, "entity_id", "unknown")
                message = getattr(r, "message", "No message")
                print(f"  - {entity_id}: {message}")
                error_count += 1
                if error_count >= max_errors:
                    remaining = result.errors - error_count
                    if remaining > 0:
                        print(f"  ... and {remaining} more errors")
                    break
        print()


def print_step_header(step_number: int, step_name: str) -> None:
    """
    Print formatted step header for batch operations.

    Args:
        step_number: Step number.
        step_name: Step description.
    """
    print("=" * 50)
    print(f"Step {step_number}: {step_name}")
    print("=" * 50)


def print_summary(
    results: List[tuple],
    title: str = "BATCH SUMMARY",
) -> None:
    """
    Print summary of batch operation results.

    Args:
        results: List of (step_name, exit_code) tuples.
        title: Title for the summary.
    """
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)

    for step_name, exit_code in results:
        status = "SUCCESS" if exit_code == 0 else "FAILED"
        print(f"  {step_name}: {status}")

    print("=" * 50 + "\n")


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"${amount:,.2f}"


def confirm_action(
    message: str,
    default: bool = False,
) -> bool:
    """
    Prompt user for confirmation.

    Args:
        message: Confirmation message.
        default: Default response if user just presses Enter.

    Returns:
        True if confirmed, False otherwise.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    response = input(message + suffix).strip().lower()

    if not response:
        return default

    return response in ("y", "yes")
