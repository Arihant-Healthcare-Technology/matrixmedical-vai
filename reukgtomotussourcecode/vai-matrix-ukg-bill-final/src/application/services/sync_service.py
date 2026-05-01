"""
Employee sync service - Orchestrates UKG to BILL.com S&E synchronization.

This service coordinates:
- Fetching employees from UKG
- Mapping to BILL.com users
- Creating/updating users in BILL.com
- Handling errors and reporting
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable

from src.domain.interfaces.services import (
    EmployeeSyncService,
    SyncResult,
    BatchSyncResult,
)
from src.domain.interfaces.repositories import EmployeeRepository, BillUserRepository
from src.domain.exceptions.api_exceptions import ApiError
from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.bill_user import BillUser, BillRole
from src.infrastructure.adapters.bill.mappers import map_employee_to_bill_user
from src.infrastructure.adapters.bill.department_client import DepartmentClient
from src.infrastructure.adapters.ukg.mappers import map_employee_from_ukg


logger = logging.getLogger(__name__)


class SyncService(EmployeeSyncService):
    """
    Implementation of employee sync service.

    Orchestrates the synchronization of employees from UKG Pro
    to BILL.com Spend & Expense.
    """

    def __init__(
        self,
        employee_repository: EmployeeRepository,
        bill_user_repository: BillUserRepository,
        rate_limiter: Optional[Callable[[], None]] = None,
        person_cache: Optional[Dict[str, Dict[str, Any]]] = None,
        department_client: Optional[DepartmentClient] = None,
        days_to_process: Optional[int] = None,
    ):
        """
        Initialize sync service.

        Args:
            employee_repository: Repository for UKG employee data.
            bill_user_repository: Repository for BILL user data.
            rate_limiter: Optional rate limiter callable.
            person_cache: Optional cache for person details.
            department_client: Optional client for resolving budget from cost center.
            days_to_process: Only process employees changed within this many days. None = no filter.
        """
        self.employee_repo = employee_repository
        self.bill_user_repo = bill_user_repository
        self.rate_limiter = rate_limiter
        self.person_cache = person_cache or {}
        self.department_client = department_client
        self.days_to_process = days_to_process

    def sync_employee(
        self,
        employee: Employee,
        default_role: BillRole = BillRole.MEMBER,
    ) -> SyncResult:
        """
        Sync a single employee to BILL.com.

        Args:
            employee: Employee to sync.
            default_role: Default role for new users.

        Returns:
            SyncResult with operation details.
        """
        # Add 5 second delay between requests to avoid BILL API rate limiting (429 errors)
        time.sleep(5)

        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate employee has required data
            if not employee.email:
                logger.warning(
                    f"Employee {employee.employee_number} skipped: missing email address"
                )
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=employee.employee_id,
                    message="Employee missing email address",
                    details={"employee_number": employee.employee_number},
                )

            # Resolve supervisor email
            supervisor_email = self.resolve_supervisor_email(employee)

            # Format cost center using org-levels lookup
            formatted_cost_center = None
            if employee.cost_center:
                formatted_cost_center = self.employee_repo._client.format_cost_center(
                    employee.cost_center
                )

            # Map employee to BILL user
            bill_user = map_employee_to_bill_user(
                employee,
                role=default_role,
                manager_email=supervisor_email,
                formatted_cost_center=formatted_cost_center,
            )

            # Resolve budget from cost center using department client
            if self.department_client and employee.cost_center:
                budget = self.department_client.get_budget_from_cost_center(
                    employee.cost_center
                )
                bill_user.budget = budget
                logger.info(
                    f"Budget resolved for {employee.email}: "
                    f"cost_center={employee.cost_center} -> budget={budget or '(empty)'}"
                )

            # Use repository's upsert which handles "already exists" gracefully
            return self._upsert_user(bill_user, employee)

        except Exception as e:
            # Build detailed error context
            error_context = (
                f"employee_number={employee.employee_number}, "
                f"email={employee.email}, "
                f"employee_id={employee.employee_id}, "
                f"first_name={employee.first_name}, "
                f"last_name={employee.last_name}, "
                f"cost_center={employee.cost_center}, "
                f"status={employee.status.value if employee.status else 'None'}"
            )

            # Log Bill API 400 errors as warning (e.g., "Invalid last name") to avoid batch exit confusion
            if isinstance(e, ApiError) and e.status_code == 400:
                response_body = getattr(e, 'response_body', 'N/A')
                logger.warning(
                    f"SYNC FAILED - Bill API 400 validation error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error: {e}\n"
                    f"  Response: {response_body}"
                )
            else:
                logger.error(
                    f"SYNC FAILED - Unexpected error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error Type: {type(e).__name__}\n"
                    f"  Error: {e}",
                    exc_info=True,
                )
            return SyncResult(
                success=False,
                action="error",
                entity_id=employee.employee_id,
                message=str(e),
                details={
                    "employee_number": employee.employee_number,
                    "email": employee.email,
                    "error_type": type(e).__name__,
                },
            )

    def _upsert_user(self, bill_user: BillUser, employee: Employee) -> SyncResult:
        """Create or update a BILL user using repository's upsert."""
        try:
            logger.info(
                f"Syncing BILL user: {bill_user.email}, "
                f"role={bill_user.role.value if bill_user.role else 'None'}, "
                f"cost_center={bill_user.cost_center}"
            )

            # Use repository's upsert which handles "already exists" gracefully
            result_user, action = self.bill_user_repo.upsert(bill_user)

            logger.info(
                f"Employee synced: {employee.employee_number} → {result_user.email} "
                f"(action={action}, id={result_user.id})"
            )

            return SyncResult(
                success=True,
                action=action,
                entity_id=result_user.id or employee.employee_id,
                message=f"User {action}: {result_user.email}",
                details={
                    "employee_number": employee.employee_number,
                    "role": result_user.role.value if result_user.role else None,
                },
            )

        except Exception as e:
            # Build detailed error context
            error_context = (
                f"email={bill_user.email}, "
                f"external_id={bill_user.external_id}, "
                f"employee_number={employee.employee_number}, "
                f"role={bill_user.role.value if bill_user.role else 'None'}, "
                f"cost_center={bill_user.cost_center}"
            )

            # Log Bill API 400 errors as warning to avoid batch exit confusion
            if isinstance(e, ApiError) and e.status_code == 400:
                response_body = getattr(e, 'response_body', 'N/A')
                logger.warning(
                    f"UPSERT FAILED - Bill API 400 validation error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error: {e}\n"
                    f"  Response: {response_body}"
                )
            else:
                logger.error(
                    f"UPSERT FAILED - Unexpected error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error Type: {type(e).__name__}\n"
                    f"  Error: {e}",
                    exc_info=True,
                )
            return SyncResult(
                success=False,
                action="error",
                entity_id=employee.employee_id,
                message=f"Failed to sync user: {e}",
                details={
                    "email": bill_user.email,
                    "external_id": bill_user.external_id,
                    "error_type": type(e).__name__,
                },
            )

    def _create_bill_user(
        self,
        employee: Employee,
        default_role: BillRole = BillRole.MEMBER,
    ) -> SyncResult:
        """
        Create a new Bill user (POST) - no lookup needed.

        Used when we know the user doesn't exist in Bill based on
        prior categorization using the email cache.

        Args:
            employee: Employee to create in Bill.
            default_role: Default role for new users.

        Returns:
            SyncResult with creation details.
        """
        # Rate limiting delay
        time.sleep(5)
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate email
            if not employee.email:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=employee.employee_id,
                    message="Employee missing email address",
                    details={"employee_number": employee.employee_number},
                )

            # Resolve supervisor email
            supervisor_email = self.resolve_supervisor_email(employee)

            # Format cost center using org-levels lookup
            formatted_cost_center = None
            if employee.cost_center:
                formatted_cost_center = self.employee_repo._client.format_cost_center(
                    employee.cost_center
                )

            # Map employee to Bill user
            bill_user = map_employee_to_bill_user(
                employee,
                role=default_role,
                manager_email=supervisor_email,
                formatted_cost_center=formatted_cost_center,
            )

            # Resolve budget from cost center
            if self.department_client and employee.cost_center:
                budget = self.department_client.get_budget_from_cost_center(
                    employee.cost_center
                )
                bill_user.budget = budget

            logger.info(
                f"Creating BILL user (POST): {bill_user.email}, "
                f"role={bill_user.role.value if bill_user.role else 'None'}"
            )

            # Create user directly (no lookup)
            created_user = self.bill_user_repo.create(bill_user)

            logger.info(
                f"User created: {employee.employee_number} → {created_user.email} "
                f"(id={created_user.id})"
            )

            return SyncResult(
                success=True,
                action="created",
                entity_id=created_user.id or employee.employee_id,
                message=f"User created: {created_user.email}",
                details={
                    "employee_number": employee.employee_number,
                    "role": created_user.role.value if created_user.role else None,
                },
            )

        except Exception as e:
            # Build detailed error context for CREATE operation
            error_context = (
                f"email={employee.email}, "
                f"employee_number={employee.employee_number}, "
                f"first_name={employee.first_name}, "
                f"last_name={employee.last_name}, "
                f"cost_center={employee.cost_center}"
            )

            if isinstance(e, ApiError) and e.status_code == 400:
                response_body = getattr(e, 'response_body', 'N/A')
                logger.warning(
                    f"CREATE FAILED - Bill API 400 validation error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error: {e}\n"
                    f"  Response: {response_body}"
                )
            else:
                logger.error(
                    f"CREATE FAILED - Unexpected error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error Type: {type(e).__name__}\n"
                    f"  Error: {e}",
                    exc_info=True,
                )
            return SyncResult(
                success=False,
                action="error",
                entity_id=employee.employee_id,
                message=f"Failed to create user: {e}",
                details={
                    "email": employee.email,
                    "employee_number": employee.employee_number,
                    "error_type": type(e).__name__,
                },
            )

    def _update_bill_user(
        self,
        employee: Employee,
        bill_user_id: str,
        default_role: BillRole = BillRole.MEMBER,
    ) -> SyncResult:
        """
        Update existing Bill user (PATCH) - use cached ID, skip lookup.

        Used when we know the user exists in Bill and have their ID
        from prior categorization using the email cache.

        Args:
            employee: Employee data to update.
            bill_user_id: Existing Bill user ID from cache.
            default_role: Default role for users.

        Returns:
            SyncResult with update details.
        """
        # Rate limiting delay
        time.sleep(5)
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate email
            if not employee.email:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=employee.employee_id,
                    message="Employee missing email address",
                    details={"employee_number": employee.employee_number},
                )

            # Resolve supervisor email
            supervisor_email = self.resolve_supervisor_email(employee)

            # Format cost center using org-levels lookup
            formatted_cost_center = None
            if employee.cost_center:
                formatted_cost_center = self.employee_repo._client.format_cost_center(
                    employee.cost_center
                )

            # Map employee to Bill user
            bill_user = map_employee_to_bill_user(
                employee,
                role=default_role,
                manager_email=supervisor_email,
                formatted_cost_center=formatted_cost_center,
            )

            # Set the ID from cache - skip get_by_email lookup
            bill_user.id = bill_user_id

            # Resolve budget from cost center
            if self.department_client and employee.cost_center:
                budget = self.department_client.get_budget_from_cost_center(
                    employee.cost_center
                )
                bill_user.budget = budget

            logger.info(
                f"Updating BILL user (PATCH): {bill_user.email}, "
                f"id={bill_user_id}, role={bill_user.role.value if bill_user.role else 'None'}"
            )

            # Update user directly (no lookup needed)
            updated_user = self.bill_user_repo.update(bill_user)

            logger.info(
                f"User updated: {employee.employee_number} → {updated_user.email} "
                f"(id={updated_user.id})"
            )

            return SyncResult(
                success=True,
                action="updated",
                entity_id=updated_user.id or employee.employee_id,
                message=f"User updated: {updated_user.email}",
                details={
                    "employee_number": employee.employee_number,
                    "role": updated_user.role.value if updated_user.role else None,
                },
            )

        except Exception as e:
            # Build detailed error context for UPDATE operation
            error_context = (
                f"email={employee.email}, "
                f"bill_user_id={bill_user_id}, "
                f"employee_number={employee.employee_number}, "
                f"first_name={employee.first_name}, "
                f"last_name={employee.last_name}, "
                f"cost_center={employee.cost_center}"
            )

            if isinstance(e, ApiError) and e.status_code == 400:
                response_body = getattr(e, 'response_body', 'N/A')
                logger.warning(
                    f"UPDATE FAILED - Bill API 400 validation error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error: {e}\n"
                    f"  Response: {response_body}"
                )
            else:
                logger.error(
                    f"UPDATE FAILED - Unexpected error:\n"
                    f"  Context: {error_context}\n"
                    f"  Error Type: {type(e).__name__}\n"
                    f"  Error: {e}",
                    exc_info=True,
                )
            return SyncResult(
                success=False,
                action="error",
                entity_id=employee.employee_id,
                message=f"Failed to update user: {e}",
                details={
                    "email": employee.email,
                    "bill_user_id": bill_user_id,
                    "employee_number": employee.employee_number,
                    "error_type": type(e).__name__,
                },
            )

    def _users_match(self, existing: BillUser, updated: BillUser) -> bool:
        """Check if two users have matching data."""
        return (
            existing.first_name == updated.first_name
            and existing.last_name == updated.last_name
            and existing.role == updated.role
            and existing.retired == updated.retired
            and existing.cost_center == updated.cost_center
            and existing.cost_center_description == updated.cost_center_description
            and existing.direct_labor == updated.direct_labor
            and existing.company == updated.company
            and existing.employee_type_code == updated.employee_type_code
            and existing.pay_frequency == updated.pay_frequency
        )

    def _get_changes(self, existing: BillUser, updated: BillUser) -> Dict[str, Any]:
        """Get dictionary of changed fields."""
        changes = {}
        if existing.first_name != updated.first_name:
            changes["first_name"] = {"old": existing.first_name, "new": updated.first_name}
        if existing.last_name != updated.last_name:
            changes["last_name"] = {"old": existing.last_name, "new": updated.last_name}
        if existing.role != updated.role:
            changes["role"] = {
                "old": existing.role.value if existing.role else None,
                "new": updated.role.value if updated.role else None,
            }
        if existing.retired != updated.retired:
            changes["retired"] = {"old": existing.retired, "new": updated.retired}
        if existing.cost_center != updated.cost_center:
            changes["cost_center"] = {"old": existing.cost_center, "new": updated.cost_center}
        if existing.cost_center_description != updated.cost_center_description:
            changes["cost_center_description"] = {
                "old": existing.cost_center_description,
                "new": updated.cost_center_description,
            }
        if existing.direct_labor != updated.direct_labor:
            changes["direct_labor"] = {"old": existing.direct_labor, "new": updated.direct_labor}
        if existing.company != updated.company:
            changes["company"] = {"old": existing.company, "new": updated.company}
        if existing.employee_type_code != updated.employee_type_code:
            changes["employee_type_code"] = {
                "old": existing.employee_type_code,
                "new": updated.employee_type_code,
            }
        if existing.pay_frequency != updated.pay_frequency:
            changes["pay_frequency"] = {
                "old": existing.pay_frequency,
                "new": updated.pay_frequency,
            }
        return changes

    def sync_batch(
        self,
        employees: List[Employee],
        default_role: BillRole = BillRole.MEMBER,
        workers: int = 1,
    ) -> BatchSyncResult:
        """
        Sync multiple employees to BILL.com.

        Uses cursor-based pagination to fetch all Bill users upfront,
        then categorizes employees into POST (create) vs PATCH (update)
        lists to avoid per-employee lookups.

        Args:
            employees: List of employees to sync.
            default_role: Default role for new users.
            workers: Number of concurrent workers.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"Starting batch sync of {len(employees)} employees "
            f"[correlation_id={correlation_id}]"
        )

        result = BatchSyncResult(
            total=len(employees),
            correlation_id=correlation_id,
            start_time=datetime.now(),
        )

        if not employees:
            result.end_time = datetime.now()
            return result

        # Pre-populate email cache using cursor-based pagination
        # This fetches ALL Bill users upfront for efficient categorization
        logger.info("Pre-populating BILL.com email cache (cursor pagination)...")
        self.bill_user_repo.build_email_cache()
        logger.info("Email cache populated.")

        # Pre-build org-levels cache for cost center formatting
        logger.info("Pre-populating UKG org-levels cache for cost center formatting...")
        self.employee_repo._client.build_org_levels_cache()
        logger.info("Org-levels cache populated.")

        # Pre-fetch departments for budget resolution
        if self.department_client:
            logger.info("Pre-fetching BILL.com departments for budget resolution...")
            departments = self.department_client.list_departments()
            logger.info(f"Departments cache populated: {len(departments)} departments")

        # Categorize employees into POST (create) vs PATCH (update) lists
        logger.info("Categorizing employees into create vs update lists...")
        to_create, to_update = self.bill_user_repo.categorize_employees(employees)

        logger.info(
            f"Sync plan: {len(to_create)} new users (POST), "
            f"{len(to_update)} existing users (PATCH) "
            f"[correlation_id={correlation_id}]"
        )

        total_to_process = len(to_create) + len(to_update)
        completed_count = 0
        progress_interval = max(1, total_to_process // 10)  # Log every 10%

        # Process creates (POST calls) - no lookup needed
        logger.info(f"Processing {len(to_create)} new users (POST)...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._create_bill_user, emp, default_role): emp
                for emp in to_create
            }

            for future in as_completed(futures):
                employee = futures[future]
                completed_count += 1

                try:
                    sync_result = future.result()
                    result.results.append(sync_result)

                    if sync_result.action == "created":
                        result.created += 1
                    elif sync_result.action == "error":
                        result.errors += 1

                except Exception as e:
                    logger.error(
                        f"Unexpected error creating {employee.email}: {e}",
                        exc_info=True,
                    )
                    result.errors += 1
                    result.results.append(
                        SyncResult(
                            success=False,
                            action="error",
                            entity_id=employee.employee_id,
                            message=str(e),
                        )
                    )

                # Log progress at intervals
                if completed_count % progress_interval == 0:
                    percentage = (completed_count / total_to_process) * 100
                    logger.info(
                        f"Sync progress: {completed_count}/{total_to_process} ({percentage:.0f}%) "
                        f"[created={result.created}, updated={result.updated}, errors={result.errors}]"
                    )

        # Process updates (PATCH calls) - use cached ID, skip lookup
        logger.info(f"Processing {len(to_update)} existing users (PATCH)...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._update_bill_user, emp, bill_user_id, default_role
                ): emp
                for emp, bill_user_id in to_update
            }

            for future in as_completed(futures):
                employee = futures[future]
                completed_count += 1

                try:
                    sync_result = future.result()
                    result.results.append(sync_result)

                    if sync_result.action == "updated":
                        result.updated += 1
                    elif sync_result.action == "error":
                        result.errors += 1

                except Exception as e:
                    logger.error(
                        f"Unexpected error updating {employee.email}: {e}",
                        exc_info=True,
                    )
                    result.errors += 1
                    result.results.append(
                        SyncResult(
                            success=False,
                            action="error",
                            entity_id=employee.employee_id,
                            message=str(e),
                        )
                    )

                # Log progress at intervals
                if completed_count % progress_interval == 0 or completed_count == total_to_process:
                    percentage = (completed_count / total_to_process) * 100
                    logger.info(
                        f"Sync progress: {completed_count}/{total_to_process} ({percentage:.0f}%) "
                        f"[created={result.created}, updated={result.updated}, errors={result.errors}]"
                    )

        result.end_time = datetime.now()

        logger.info(
            f"Batch sync complete: {result.created} created, {result.updated} updated, "
            f"{result.skipped} skipped, {result.errors} errors "
            f"({result.success_rate:.1f}% success) [correlation_id={correlation_id}]"
        )

        return result

    def _process_single_employee(
        self,
        emp_data: Dict[str, Any],
        company_id: Optional[str],
        default_role: BillRole,
        idx: int,
        total: int,
    ) -> tuple:
        """
        Process a single employee: fetch details, filter, sync to BILL.com.

        Returns:
            Tuple of (is_active, is_eligible, sync_result or None)
        """
        emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
        emp_number = emp_data.get("employeeNumber", "unknown")
        emp_company_id = emp_data.get("companyID") or emp_data.get("companyId") or company_id

        # Fetch person details for this employee
        person = self.employee_repo._get_cached_person(emp_id) if emp_id else None

        # Fetch employee-employment details (has cost center / primaryProjectCode)
        emp_emp_details = None
        if emp_number and emp_company_id:
            emp_emp_details = self.employee_repo._client.get_employee_employment_details(
                employee_number=emp_number,
                company_id=emp_company_id,
            )

        # Create Employee object using comprehensive mapper
        employee = map_employee_from_ukg(emp_data, person, emp_emp_details)

        # Filter 1: Active status
        if employee.status != EmployeeStatus.ACTIVE:
            logger.debug(f"[{idx}/{total}] Skipping {emp_number}: not active")
            return (False, False, None)

        # Filter 2: Employee type (PRD Full Time or FTC/HRC)
        if not employee.should_sync_to_bill:
            logger.debug(f"[{idx}/{total}] Skipping {emp_number}: not eligible type")
            return (True, False, None)

        # Sync this employee to BILL.com
        logger.info(f"[{idx}/{total}] Processing {employee.first_name} {employee.last_name} ({employee.email})")
        result = self.sync_employee(employee, default_role)
        return (True, True, result)

    def sync_all(
        self,
        company_id: Optional[str] = None,
        default_role: BillRole = BillRole.MEMBER,
        workers: int = 1,
    ) -> BatchSyncResult:
        """
        Sync all active employees from UKG to BILL.com.

        Processes employees with parallel workers: fetch details -> filter -> sync to BILL.com.

        Args:
            company_id: Optional company filter.
            default_role: Default role for new users.
            workers: Number of concurrent workers.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        logger.info(
            f"Fetching employees from UKG and processing with {workers} worker(s) "
            f"(company_id={company_id})"
        )

        # Get raw employee data from UKG (without person details)
        raw_employees = self.employee_repo._client.list_employees(
            company_id=company_id,
            page=1,
            page_size=2147483647,  # Max int to fetch all in one call
        )

        total_from_ukg = len(raw_employees)
        logger.info(f"Fetched {total_from_ukg} employees from UKG")

        # Filter by dateTimeChanged if days_to_process is set
        if self.days_to_process is not None and self.days_to_process >= 0:
            raw_employees = self._filter_by_date_changed(raw_employees, self.days_to_process)

        # Log processing header
        logger.info("=" * 60)
        logger.info(f"PROCESSING EMPLOYEES WITH {workers} WORKER(S)")
        logger.info("=" * 60)

        # Counters for filter breakdown
        total_active = 0
        total_eligible = 0

        # Results tracking
        results: List[SyncResult] = []
        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Process employees with workers
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._process_single_employee,
                    emp_data,
                    company_id,
                    default_role,
                    idx,
                    total_from_ukg,
                ): idx
                for idx, emp_data in enumerate(raw_employees, 1)
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    is_active, is_eligible, result = future.result()

                    if is_active:
                        total_active += 1
                    if is_eligible:
                        total_eligible += 1

                    if result:
                        results.append(result)
                        if result.success:
                            if result.action == "created":
                                created += 1
                            elif result.action == "updated":
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            errors += 1

                except Exception as e:
                    logger.error(f"Error processing employee index {idx}: {e}", exc_info=True)
                    errors += 1

        # Log filter breakdown
        logger.info("=" * 60)
        logger.info("FILTER BREAKDOWN")
        logger.info("=" * 60)
        logger.info(f"  Total from UKG: {total_from_ukg}")
        logger.info(f"  After ACTIVE status filter: {total_active}")
        logger.info(f"  After employee type filter (PRD Full Time / FTC / HRC): {total_eligible}")
        logger.info("=" * 60)

        return BatchSyncResult(
            total=total_eligible,
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            results=results,
        )

    def resolve_supervisor_email(self, employee: Employee) -> Optional[str]:
        """
        Resolve supervisor email using multiple fallback strategies.

        Strategies:
        1. Direct supervisor_email field
        2. Supervisor ID -> lookup person details
        3. Supervisor employee number -> lookup person details

        Args:
            employee: Employee to resolve supervisor for.

        Returns:
            Supervisor email or None if not found.
        """
        # Strategy 1: Direct email field
        if employee.supervisor_email:
            logger.debug(
                f"Supervisor resolved for {employee.email}: "
                f"{employee.supervisor_email} (strategy=direct)"
            )
            return employee.supervisor_email

        # Strategy 2: Supervisor ID -> person details
        if employee.supervisor_id:
            email = self._lookup_supervisor_by_id(employee.supervisor_id)
            if email:
                logger.debug(
                    f"Supervisor resolved for {employee.email}: "
                    f"{email} (strategy=id_lookup)"
                )
                return email

        # Strategy 3: Supervisor employee number -> employment -> person details
        if employee.supervisor_number:
            email = self._lookup_supervisor_by_number(employee.supervisor_number)
            if email:
                logger.debug(
                    f"Supervisor resolved for {employee.email}: "
                    f"{email} (strategy=number_lookup)"
                )
                return email

        logger.debug(
            f"Supervisor not found for {employee.email} "
            f"(employee_id={employee.employee_id})"
        )
        return None

    def _lookup_supervisor_by_id(self, supervisor_id: str) -> Optional[str]:
        """Look up supervisor email by employee ID."""
        try:
            # Check cache first
            if supervisor_id in self.person_cache:
                return self.person_cache[supervisor_id].get("emailAddress")

            # Look up via repository
            supervisor = self.employee_repo.get_by_id(supervisor_id)
            if supervisor and supervisor.email:
                # Cache for future lookups
                self.person_cache[supervisor_id] = {"emailAddress": supervisor.email}
                return supervisor.email

        except Exception as e:
            logger.warning(f"Failed to lookup supervisor by ID {supervisor_id}: {e}")

        return None

    def _lookup_supervisor_by_number(self, supervisor_number: str) -> Optional[str]:
        """Look up supervisor email by employee number."""
        try:
            # Look up via repository
            supervisor = self.employee_repo.get_by_employee_number(supervisor_number)
            if supervisor and supervisor.email:
                # Cache by ID for future lookups
                if supervisor.employee_id:
                    self.person_cache[supervisor.employee_id] = {
                        "emailAddress": supervisor.email
                    }
                return supervisor.email

        except Exception as e:
            logger.warning(
                f"Failed to lookup supervisor by number {supervisor_number}: {e}"
            )

        return None

    def _filter_by_date_changed(
        self,
        employees: List[Dict[str, Any]],
        days: int,
    ) -> List[Dict[str, Any]]:
        """
        Filter employees to only those changed within the last X days.

        Args:
            employees: List of raw employee data from UKG API.
            days: Number of days to look back.

        Returns:
            Filtered list of employees changed within the specified period.
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = []

        for emp in employees:
            date_changed_str = emp.get("dateTimeChanged")
            if date_changed_str:
                try:
                    # Parse UKG format: "2026-04-20T13:35:31.44"
                    # Handle with or without timezone
                    date_changed = datetime.fromisoformat(
                        date_changed_str.replace("Z", "+00:00")
                    )
                    # Make cutoff_date timezone-aware if needed
                    if date_changed.tzinfo is not None:
                        from datetime import timezone
                        cutoff_aware = cutoff_date.replace(tzinfo=timezone.utc)
                        if date_changed >= cutoff_aware:
                            filtered.append(emp)
                    else:
                        if date_changed >= cutoff_date:
                            filtered.append(emp)
                except ValueError as e:
                    # If parse fails, include employee to be safe
                    logger.debug(
                        f"Could not parse dateTimeChanged '{date_changed_str}': {e}, including employee"
                    )
                    filtered.append(emp)
            else:
                # If no dateTimeChanged, include employee to be safe
                filtered.append(emp)

        logger.info(
            f"Filtered employees by date changed: {len(filtered)}/{len(employees)} "
            f"(last {days} days)"
        )
        return filtered
