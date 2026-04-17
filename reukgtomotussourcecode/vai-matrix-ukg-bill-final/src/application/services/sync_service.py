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
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from src.domain.interfaces.services import (
    EmployeeSyncService,
    SyncResult,
    BatchSyncResult,
)
from src.domain.interfaces.repositories import EmployeeRepository, BillUserRepository
from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.bill_user import BillUser, BillRole
from src.infrastructure.adapters.bill.mappers import map_employee_to_bill_user


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
    ):
        """
        Initialize sync service.

        Args:
            employee_repository: Repository for UKG employee data.
            bill_user_repository: Repository for BILL user data.
            rate_limiter: Optional rate limiter callable.
            person_cache: Optional cache for person details.
        """
        self.employee_repo = employee_repository
        self.bill_user_repo = bill_user_repository
        self.rate_limiter = rate_limiter
        self.person_cache = person_cache or {}

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

            # Check if user already exists in BILL
            existing_user = self.bill_user_repo.get_by_email(employee.email)
            logger.info(
                f"User lookup for {employee.email}: exists={existing_user is not None}"
            )

            # Resolve supervisor email
            supervisor_email = self.resolve_supervisor_email(employee)

            # Map employee to BILL user
            bill_user = map_employee_to_bill_user(
                employee,
                role=default_role,
                manager_email=supervisor_email,
            )

            if existing_user:
                # Update existing user
                return self._update_user(existing_user, bill_user, employee)
            else:
                # Create new user
                return self._create_user(bill_user, employee)

        except Exception as e:
            logger.error(
                f"Employee sync failed: {employee.employee_number} ({employee.email}): {e}",
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
                },
            )

    def _create_user(self, bill_user: BillUser, employee: Employee) -> SyncResult:
        """Create a new BILL user."""
        try:
            logger.info(
                f"Creating BILL user: {bill_user.email}, "
                f"role={bill_user.role.value if bill_user.role else 'None'}, "
                f"cost_center={bill_user.cost_center}"
            )
            created = self.bill_user_repo.create(bill_user)
            logger.info(
                f"Employee synced: {employee.employee_number} → {created.email} "
                f"(action=create, id={created.id})"
            )
            return SyncResult(
                success=True,
                action="create",
                entity_id=created.id,
                message=f"Created user {created.email}",
                details={
                    "employee_number": employee.employee_number,
                    "role": created.role.value if created.role else None,
                },
            )
        except Exception as e:
            error_msg = str(e).lower()
            # Also check response_body if available (for ApiError exceptions)
            response_body = ""
            if hasattr(e, 'response_body') and e.response_body:
                response_body = str(e.response_body).lower()

            combined_error = error_msg + " " + response_body

            # Handle "User already exists" error - fall back to update
            if "already exists" in combined_error or "user already exists" in combined_error:
                logger.warning(
                    f"User {bill_user.email} already exists (detected from API error), falling back to update"
                )
                # Clear cache and re-fetch to ensure we get fresh data
                self.bill_user_repo.clear_cache()
                existing_user = self.bill_user_repo.get_by_email(bill_user.email)
                if existing_user:
                    logger.info(f"Found existing user {bill_user.email} with ID {existing_user.id}")
                    return self._update_user(existing_user, bill_user, employee)
                else:
                    # User exists in BILL but we can't fetch - skip with warning
                    logger.warning(
                        f"User {bill_user.email} exists in BILL but could not be fetched for update. Skipping."
                    )
                    return SyncResult(
                        success=True,
                        action="skip",
                        entity_id=employee.employee_id,
                        message=f"User exists but could not be fetched for update - skipped",
                        details={"email": bill_user.email},
                    )

            logger.error(
                f"Failed to create user {bill_user.email}: {e}",
                exc_info=True,
            )
            return SyncResult(
                success=False,
                action="error",
                entity_id=employee.employee_id,
                message=f"Failed to create user: {e}",
                details={"email": bill_user.email},
            )

    def _update_user(
        self,
        existing: BillUser,
        updated: BillUser,
        employee: Employee,
    ) -> SyncResult:
        """Update an existing BILL user."""
        try:
            # Preserve existing ID
            updated.id = existing.id

            # Log field changes
            changes = self._get_changes(existing, updated)
            changes_str = ", ".join(
                f"{field}: '{change['old']}' → '{change['new']}'"
                for field, change in changes.items()
            )
            logger.info(f"Changes detected for {existing.email}: {changes_str}")

            # Update user
            result = self.bill_user_repo.update(updated)
            logger.info(
                f"Employee synced: {employee.employee_number} → {result.email} "
                f"(action=update, id={result.id})"
            )
            return SyncResult(
                success=True,
                action="update",
                entity_id=result.id,
                message=f"Updated user {result.email}",
                details={
                    "employee_number": employee.employee_number,
                    "changes": changes,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to update user {existing.email}: {e}",
                exc_info=True,
            )
            return SyncResult(
                success=False,
                action="error",
                entity_id=existing.id,
                message=f"Failed to update user: {e}",
                details={"email": existing.email},
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
        workers: int = 6,
    ) -> BatchSyncResult:
        """
        Sync multiple employees to BILL.com.

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

        # Pre-populate email cache to avoid repeated pagination for each employee
        # The _paginate method now has rate limiting built-in (3s delay per request)
        logger.info("Pre-populating BILL.com email cache (with rate limiting)...")
        self.bill_user_repo.build_email_cache()
        logger.info("Email cache populated.")

        # Process sequentially with single worker
        total_employees = len(employees)
        completed_count = 0
        progress_interval = max(1, total_employees // 10)  # Log every 10%

        logger.info(
            f"Starting batch sync: {total_employees} employees, {workers} workers "
            f"[correlation_id={correlation_id}]"
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.sync_employee, emp, default_role): emp
                for emp in employees
            }

            for future in as_completed(futures):
                employee = futures[future]
                completed_count += 1

                try:
                    sync_result = future.result()
                    result.results.append(sync_result)

                    if sync_result.action == "create":
                        result.created += 1
                    elif sync_result.action == "update":
                        result.updated += 1
                    elif sync_result.action == "skip":
                        result.skipped += 1
                    elif sync_result.action == "error":
                        result.errors += 1

                except Exception as e:
                    logger.error(
                        f"Unexpected error syncing {employee.email}: {e}",
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
                if completed_count % progress_interval == 0 or completed_count == total_employees:
                    percentage = (completed_count / total_employees) * 100
                    logger.info(
                        f"Sync progress: {completed_count}/{total_employees} ({percentage:.0f}%) "
                        f"[created={result.created}, updated={result.updated}, "
                        f"skipped={result.skipped}, errors={result.errors}]"
                    )

        result.end_time = datetime.now()

        logger.info(
            f"Batch sync complete: {result.created} created, {result.updated} updated, "
            f"{result.skipped} skipped, {result.errors} errors "
            f"({result.success_rate:.1f}% success) [correlation_id={correlation_id}]"
        )

        return result

    def sync_all(
        self,
        company_id: Optional[str] = None,
        default_role: BillRole = BillRole.MEMBER,
        workers: int = 6,
    ) -> BatchSyncResult:
        """
        Sync all active employees from UKG to BILL.com.

        Args:
            company_id: Optional company filter.
            default_role: Default role for new users.
            workers: Number of concurrent workers.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        # Fetch all active employees
        employees = []
        page = 1
        page_size = 200

        logger.info(
            f"Fetching active employees from UKG "
            f"(company_id={company_id}, page_size={page_size})"
        )

        while True:
            batch = self.employee_repo.get_active_employees(
                company_id=company_id,
                page=page,
                page_size=page_size,
            )
            if not batch:
                break

            # Filter for only active employees that should be synced to BILL
            # Criteria: PRD employee type + Full Time only
            eligible_batch = [
                emp for emp in batch
                if emp.status == EmployeeStatus.ACTIVE and emp.should_sync_to_bill
            ]
            employees.extend(eligible_batch)

            logger.info(
                f"Fetched page {page}: {len(batch)} employees "
                f"({len(eligible_batch)} eligible for BILL sync, total so far: {len(employees)})"
            )

            if len(batch) < page_size:
                break

            page += 1

        logger.info(
            f"UKG fetch complete: {len(employees)} eligible employees found "
            f"(PRD + Full Time only, from {page} page(s))"
        )

        return self.sync_batch(employees, default_role, workers)

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
