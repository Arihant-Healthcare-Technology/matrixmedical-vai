"""
Batch commands for Spend & Expense (S&E) operations.

Provides CLI handlers for:
- Full employee sync from UKG to BILL.com
- Batch sync from file
- CSV export for UI import
"""

import csv
import json
import logging
from pathlib import Path
from typing import List, Optional

from src.domain.models.employee import Employee
from src.domain.models.bill_user import BillRole
from src.presentation.cli.container import Container
from src.presentation.cli.utils import (
    load_json_file,
    print_preview,
    print_sync_result,
)


logger = logging.getLogger(__name__)


def run_sync_all(
    container: Container,
    company_id: Optional[str] = None,
    workers: int = 12,
    default_role: str = "MEMBER",
    dry_run: bool = False,
) -> int:
    """
    Sync all active employees from UKG to BILL.com.

    Args:
        container: DI container.
        company_id: Optional UKG company ID filter.
        workers: Number of concurrent workers.
        default_role: Default role for new users.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting full employee sync to BILL.com S&E")
    if company_id:
        logger.info(f"Filtering by company ID: {company_id}")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    try:
        role = BillRole.from_string(default_role)
        sync_service = container.sync_service()

        if dry_run:
            # In dry run, just fetch and report what would happen
            employee_repo = container.employee_repository()
            employees = list(employee_repo.get_active_employees(company_id=company_id))
            logger.info(f"Would sync {len(employees)} employees")
            print_preview(employees, "employees to sync")
            return 0

        # Run full sync
        result = sync_service.sync_all(
            company_id=company_id,
            default_role=role,
            workers=workers,
        )

        print_sync_result(result)
        return 0 if result.errors == 0 else 1

    except ValueError as e:
        # Configuration/credential errors
        logger.error(f"Configuration error: {e}")
        print("\n" + "=" * 60)
        print("  CONFIGURATION ERROR")
        print("=" * 60)
        print(f"\n{e}\n")
        print("Please check your .env file and ensure all required")
        print("credentials are set correctly.")
        print("\nRequired environment variables:")
        print("  - UKG_USERNAME and UKG_PASSWORD (or UKG_BASIC_B64)")
        print("  - UKG_CUSTOMER_API_KEY")
        print("  - BILL_API_TOKEN")
        print("=" * 60 + "\n")
        return 1

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return 1


def run_sync_batch(
    container: Container,
    employee_file: str,
    workers: int = 12,
    default_role: str = "MEMBER",
    dry_run: bool = False,
) -> int:
    """
    Sync employees from JSON file to BILL.com.

    Args:
        container: DI container.
        employee_file: Path to JSON file with employee data.
        workers: Number of concurrent workers.
        default_role: Default role for new users.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info(f"Starting batch sync from file: {employee_file}")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    try:
        # Load employees from file
        employees = _load_employees_from_file(employee_file)
        logger.info(f"Loaded {len(employees)} employees from file")

        if dry_run:
            print_preview(employees, "employees to sync")
            return 0

        role = BillRole.from_string(default_role)
        sync_service = container.sync_service()

        # Run batch sync
        result = sync_service.sync_batch(
            employees=employees,
            default_role=role,
            workers=workers,
        )

        print_sync_result(result)
        return 0 if result.errors == 0 else 1

    except FileNotFoundError:
        logger.error(f"File not found: {employee_file}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {employee_file}: {e}")
        return 1
    except ValueError as e:
        # Configuration/credential errors
        logger.error(f"Configuration error: {e}")
        print("\n" + "=" * 60)
        print("  CONFIGURATION ERROR")
        print("=" * 60)
        print(f"\n{e}\n")
        print("Please check your .env file and ensure all required")
        print("credentials are set correctly.")
        print("\nRequired environment variables:")
        print("  - UKG_USERNAME and UKG_PASSWORD (or UKG_BASIC_B64)")
        print("  - UKG_CUSTOMER_API_KEY")
        print("  - BILL_API_TOKEN")
        print("=" * 60 + "\n")
        return 1
    except Exception as e:
        logger.error(f"Batch sync failed: {e}", exc_info=True)
        return 1


def run_export_csv(
    container: Container,
    output_path: str,
    company_id: Optional[str] = None,
    include_managers: bool = False,
) -> int:
    """
    Export employees to CSV for BILL.com bulk import.

    Args:
        container: DI container.
        output_path: Output CSV file path.
        company_id: Optional UKG company ID filter.
        include_managers: Include manager column.

    Returns:
        Exit code (0 for success).
    """
    logger.info(f"Exporting employees to CSV: {output_path}")
    if company_id:
        logger.info(f"Filtering by company ID: {company_id}")

    try:
        # Fetch employees
        employee_repo = container.employee_repository()
        employees = list(employee_repo.get_active_employees(company_id=company_id))
        logger.info(f"Found {len(employees)} employees to export")

        if not employees:
            logger.warning("No employees found")
            return 0

        # Convert to BILL users for CSV format
        from src.infrastructure.adapters.bill.mappers import map_employee_to_bill_user

        bill_users = []
        for emp in employees:
            try:
                supervisor_email = emp.supervisor_email or ""
                user = map_employee_to_bill_user(
                    emp,
                    role=BillRole.MEMBER,
                    manager_email=supervisor_email if include_managers else None,
                )
                bill_users.append(user)
            except Exception as e:
                logger.warning(f"Failed to map employee {emp.email}: {e}")

        # Write CSV
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ["first name", "last name", "email address", "role"]
        if include_managers:
            fieldnames.append("manager")

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for user in bill_users:
                row = user.to_csv_row()
                if not include_managers and "manager" in row:
                    del row["manager"]
                writer.writerow(row)

        logger.info(f"Exported {len(bill_users)} users to {output_path}")
        return 0

    except ValueError as e:
        # Configuration/credential errors
        logger.error(f"Configuration error: {e}")
        print("\n" + "=" * 60)
        print("  CONFIGURATION ERROR")
        print("=" * 60)
        print(f"\n{e}\n")
        print("Please check your .env file and ensure all required")
        print("credentials are set correctly.")
        print("\nRequired environment variables for CSV export:")
        print("  - UKG_USERNAME and UKG_PASSWORD (or UKG_BASIC_B64)")
        print("  - UKG_CUSTOMER_API_KEY")
        print("=" * 60 + "\n")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


def _load_employees_from_file(file_path: str) -> List[Employee]:
    """Load employees from JSON file."""
    data = load_json_file(file_path)

    employees = []
    items = data if isinstance(data, list) else data.get("employees", [])

    for item in items:
        try:
            emp = Employee.from_ukg(item)
            employees.append(emp)
        except Exception as e:
            logger.warning(f"Failed to parse employee: {e}")

    return employees
