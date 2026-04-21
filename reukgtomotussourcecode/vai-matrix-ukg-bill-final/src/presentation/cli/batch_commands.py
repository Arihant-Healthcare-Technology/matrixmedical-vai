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

from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.bill_user import BillRole, BillUser
from src.infrastructure.adapters.ukg.mappers import map_employee_from_ukg
from src.presentation.cli.container import Container
from src.presentation.cli.utils import (
    load_json_file,
    print_preview,
    print_sync_result,
)


logger = logging.getLogger(__name__)


def _print_startup_banner(container: Container, operation: str, workers: int = 1, dry_run: bool = False) -> None:
    """Print startup banner showing credentials loaded from .env."""
    settings = container.settings

    print("\n" + "=" * 60)
    print(f"  UKG → BILL.com S&E {operation}")
    print("=" * 60)

    # Show credential status
    logger.info("STEP 1: Loading credentials from .env")

    # UKG credentials status
    ukg_configured = bool(settings.ukg_username or settings.ukg_basic_b64) and bool(settings.ukg_api_key)
    ukg_method = "username + password" if settings.ukg_username else "basic_b64 token"
    ukg_status = f"CONFIGURED ({ukg_method})" if ukg_configured else "NOT CONFIGURED"

    # BILL credentials status
    bill_configured = bool(settings.bill_api_token)
    bill_status = "CONFIGURED (API token)" if bill_configured else "NOT CONFIGURED"

    print(f"  Environment: {settings.environment}")
    print(f"  UKG API:     {settings.ukg_api_base}")
    print(f"  UKG Creds:   {ukg_status}")
    print(f"  BILL API:    {settings.bill_api_base}")
    print(f"  BILL Creds:  {bill_status}")
    print(f"  Workers:     {workers}")
    if dry_run:
        print(f"  Mode:        DRY RUN (no changes)")
    print("=" * 60 + "\n")

    logger.info(f"  UKG credentials: {ukg_status}")
    logger.info(f"  BILL credentials: {bill_status}")


def run_sync_all(
    container: Container,
    company_id: Optional[str] = None,
    workers: int = 1,
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
    # Print startup banner with credential status
    _print_startup_banner(container, "Sync", workers=workers, dry_run=dry_run)

    logger.info("Starting full employee sync to BILL.com S&E")
    if company_id:
        logger.info(f"Filtering by company ID: {company_id}")

    try:
        role = BillRole.from_string(default_role)

        # STEP 2: Fetch employees from UKG
        logger.info("=" * 60)
        logger.info("STEP 2: Fetching employees from UKG")
        logger.info("=" * 60)
        if company_id:
            logger.info(f"  Company ID: {company_id}")

        if dry_run:
            # In dry run, process employees one by one
            employee_repo = container.employee_repository()
            bill_user_repo = container.bill_user_repository()

            # Get raw employee data from UKG
            logger.info("Fetching employees from UKG...")
            raw_employees = employee_repo._client.list_employees(
                company_id=company_id,
                page=1,
                page_size=2147483647,  # Max int to fetch all in one call
            )

            total_from_ukg = len(raw_employees)
            logger.info(f"Fetched {total_from_ukg} employees from UKG")

            # Counters for filter breakdown
            total_active = 0
            total_eligible = 0

            # Classification lists
            create_list = []
            update_list = []
            no_change_list = []

            logger.info("=" * 60)
            logger.info("PROCESSING EMPLOYEES ONE BY ONE")
            logger.info("=" * 60)

            for idx, emp_data in enumerate(raw_employees, 1):
                emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
                emp_number = emp_data.get("employeeNumber", "unknown")
                emp_company_id = emp_data.get("companyID") or emp_data.get("companyId") or company_id

                # Fetch person details for this employee
                person = employee_repo._get_cached_person(emp_id) if emp_id else None

                # Fetch employee-employment details (has cost center / primaryProjectCode)
                emp_emp_details = None
                if emp_number and emp_company_id:
                    emp_emp_details = employee_repo._client.get_employee_employment_details(
                        employee_number=emp_number,
                        company_id=emp_company_id,
                    )

                # Create Employee object using comprehensive mapper
                emp = map_employee_from_ukg(emp_data, person, emp_emp_details)

                # Filter 1: Active status
                if emp.status != EmployeeStatus.ACTIVE:
                    continue
                total_active += 1

                # Filter 2: Employee type (PRD Full Time or FTC/HRC)
                if not emp.should_sync_to_bill:
                    continue
                total_eligible += 1

                # Check against BILL.com
                logger.info(f"[{idx}/{total_from_ukg}] Checking {emp.first_name} {emp.last_name} ({emp.email})")
                existing = bill_user_repo.get_by_email(emp.email)
                if existing:
                    bill_user = BillUser.from_employee(emp, role=role)
                    if bill_user.needs_update(existing):
                        update_list.append(emp)
                    else:
                        no_change_list.append(emp)
                else:
                    create_list.append(emp)

            # Log filter breakdown
            logger.info("=" * 60)
            logger.info("FILTER BREAKDOWN")
            logger.info("=" * 60)
            logger.info(f"  Total from UKG: {total_from_ukg}")
            logger.info(f"  After ACTIVE status filter: {total_active}")
            logger.info(f"  After employee type filter (PRD Full Time / FTC / HRC): {total_eligible}")
            logger.info("=" * 60)

            # Print summary
            logger.info("=" * 60)
            logger.info("DRY RUN SUMMARY")
            logger.info("=" * 60)
            logger.info(f"  Need creation: {len(create_list)}")
            logger.info(f"  Need update: {len(update_list)}")
            logger.info(f"  No changes needed: {len(no_change_list)}")
            logger.info("=" * 60)

            # Print detailed lists
            if create_list:
                logger.info("\nEmployees needing CREATION:")
                for emp in create_list:
                    logger.info(f"  - {emp.first_name} {emp.last_name} | {emp.email} | #{emp.employee_number}")

            if update_list:
                logger.info("\nEmployees needing UPDATE:")
                for emp in update_list:
                    logger.info(f"  - {emp.first_name} {emp.last_name} | {emp.email} | #{emp.employee_number}")

            if no_change_list:
                logger.info("\nEmployees with NO CHANGES needed:")
                for emp in no_change_list:
                    logger.info(f"  - {emp.first_name} {emp.last_name} | {emp.email} | #{emp.employee_number}")

            logger.info("\nDRY RUN MODE - No changes were made to BILL.com")
            return 0

        # STEP 3: Sync employees to BILL.com S&E
        logger.info("=" * 60)
        logger.info("STEP 3: Syncing employees to BILL.com S&E")
        logger.info("=" * 60)

        sync_service = container.sync_service()
        result = sync_service.sync_all(
            company_id=company_id,
            default_role=role,
            workers=workers,
        )

        # STEP 4: Sync Complete
        logger.info("=" * 60)
        logger.info("STEP 4: Sync Complete")
        logger.info("=" * 60)

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
    workers: int = 1,
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
    # Print startup banner with credential status
    _print_startup_banner(container, "Batch Sync", workers=workers, dry_run=dry_run)

    logger.info(f"Starting batch sync from file: {employee_file}")

    try:
        # STEP 2: Load employees from file
        logger.info("=" * 60)
        logger.info("STEP 2: Loading employees from file")
        logger.info("=" * 60)
        logger.info(f"  File: {employee_file}")

        employees = _load_employees_from_file(employee_file)
        logger.info(f"  Loaded {len(employees)} employees from file")

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            print_preview(employees, "employees to sync to BILL.com", show_all=True)
            return 0

        # STEP 3: Sync employees to BILL.com S&E
        logger.info("=" * 60)
        logger.info("STEP 3: Syncing employees to BILL.com S&E")
        logger.info("=" * 60)

        role = BillRole.from_string(default_role)
        sync_service = container.sync_service()

        result = sync_service.sync_batch(
            employees=employees,
            default_role=role,
            workers=workers,
        )

        # STEP 4: Sync Complete
        logger.info("=" * 60)
        logger.info("STEP 4: Sync Complete")
        logger.info("=" * 60)

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
    # Print startup banner (only UKG credentials needed for export)
    print("\n" + "=" * 60)
    print("  UKG → CSV Export")
    print("=" * 60)

    settings = container.settings
    ukg_configured = bool(settings.ukg_username or settings.ukg_basic_b64) and bool(settings.ukg_api_key)
    ukg_method = "username + password" if settings.ukg_username else "basic_b64 token"
    ukg_status = f"CONFIGURED ({ukg_method})" if ukg_configured else "NOT CONFIGURED"

    print(f"  Environment: {settings.environment}")
    print(f"  UKG API:     {settings.ukg_api_base}")
    print(f"  UKG Creds:   {ukg_status}")
    print(f"  Output:      {output_path}")
    print("=" * 60 + "\n")

    logger.info("STEP 1: Loading credentials from .env")
    logger.info(f"  UKG credentials: {ukg_status}")

    logger.info(f"Exporting employees to CSV: {output_path}")
    if company_id:
        logger.info(f"Filtering by company ID: {company_id}")

    try:
        # STEP 2: Fetch employees from UKG
        logger.info("=" * 60)
        logger.info("STEP 2: Fetching employees from UKG")
        logger.info("=" * 60)
        if company_id:
            logger.info(f"  Company ID: {company_id}")

        employee_repo = container.employee_repository()
        employees = list(employee_repo.get_active_employees(company_id=company_id))
        logger.info(f"  Fetched {len(employees)} employees")

        if not employees:
            logger.warning("No employees found")
            return 0

        # STEP 3: Convert and write CSV
        logger.info("=" * 60)
        logger.info("STEP 3: Converting and writing CSV")
        logger.info("=" * 60)

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

        # STEP 4: Export Complete
        logger.info("=" * 60)
        logger.info("STEP 4: Export Complete")
        logger.info("=" * 60)
        logger.info(f"  Exported {len(bill_users)} users to {output_path}")
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
