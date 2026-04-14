"""
UKG Employee repository implementation.

This module implements the EmployeeRepository interface using the UKG API client.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import EmployeeRepository
from src.domain.models.employee import Employee
from src.infrastructure.adapters.ukg.client import UKGClient

logger = logging.getLogger(__name__)


class UKGEmployeeRepository(EmployeeRepository):
    """
    UKG Pro employee repository implementation.

    Implements the EmployeeRepository interface using the UKG API client.
    Provides data access operations for UKG Pro employees.
    """

    def __init__(self, client: UKGClient, default_company_id: Optional[str] = None) -> None:
        """
        Initialize repository.

        Args:
            client: UKG API client
            default_company_id: Default company ID for operations
        """
        self._client = client
        self._default_company_id = default_company_id
        self._person_cache: Dict[str, Dict[str, Any]] = {}

    def _get_company_id(self, company_id: Optional[str] = None) -> str:
        """Get company ID with fallback to default."""
        cid = company_id or self._default_company_id
        if not cid:
            raise ValueError("company_id is required")
        return cid

    def get_by_id(self, entity_id: str) -> Optional[Employee]:
        """
        Get employee by employee ID (UUID).

        Args:
            entity_id: Employee ID (UUID format)

        Returns:
            Employee if found, None otherwise
        """
        logger.debug(f"UKG API: Looking up employee by ID: {entity_id}")

        # First, get person details
        person = self._client.get_person_details(entity_id)
        if not person:
            logger.debug(f"UKG API: Employee not found by ID: {entity_id}")
            return None

        # Try to find employment details
        employee_number = person.get("employeeNumber")
        company_id = person.get("companyId") or person.get("companyID")

        if employee_number and company_id:
            employment = self._client.get_employment_details(employee_number, company_id)
            if employment:
                employee = Employee.from_ukg(employment, person)
                logger.debug(
                    f"UKG API: Employee found: {employee_number}, email={employee.email}"
                )
                return employee

        # Return basic employee from person data only
        logger.debug(
            f"UKG API: Returning partial employee data for {entity_id}"
        )
        return Employee(
            employee_id=entity_id,
            employee_number=person.get("employeeNumber", ""),
            first_name=person.get("firstName", ""),
            last_name=person.get("lastName", ""),
            email=person.get("emailAddress", ""),
            phone=person.get("workPhone", "") or person.get("mobilePhone", ""),
        )

    def get_by_employee_number(
        self,
        employee_number: str,
        company_id: Optional[str] = None,
    ) -> Optional[Employee]:
        """
        Get employee by employee number.

        Args:
            employee_number: Human-readable employee number
            company_id: Company ID (uses default if not provided)

        Returns:
            Employee if found, None otherwise
        """
        cid = self._get_company_id(company_id)
        logger.debug(f"Fetching UKG employee: {employee_number} from company {cid}")

        try:
            full_data = self._client.get_employee_full_data(employee_number, cid)
            employee = Employee.from_ukg(
                full_data["employment"],
                full_data.get("person"),
            )
            logger.debug(
                f"Employee fetched: {employee_number}, "
                f"status={employee.status.value if employee.status else 'unknown'}, "
                f"email={employee.email}"
            )
            return employee
        except ValueError:
            logger.debug(f"Employee not found in UKG: {employee_number}")
            return None

    def get_by_email(self, email: str) -> Optional[Employee]:
        """
        Get employee by email address.

        Note: This requires iterating through employees as UKG doesn't
        support direct email lookup. Use sparingly.

        Args:
            email: Employee email

        Returns:
            Employee if found, None otherwise
        """
        email_lower = email.lower().strip()

        # Paginate through all employees
        page = 1
        while True:
            employees = self._client.list_employees(
                company_id=self._default_company_id,
                page=page,
                page_size=200,
            )

            if not employees:
                break

            for emp_data in employees:
                emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
                if emp_id:
                    person = self._get_cached_person(emp_id)
                    if person:
                        if person.get("emailAddress", "").lower().strip() == email_lower:
                            return Employee.from_ukg(emp_data, person)

            if len(employees) < 200:
                break
            page += 1

        return None

    def get_active_employees(
        self,
        company_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Employee]:
        """
        Get all active employees.

        Args:
            company_id: Optional company filter
            page: Page number
            page_size: Page size

        Returns:
            List of active employees
        """
        cid = company_id or self._default_company_id
        logger.debug(
            f"UKG API: Fetching active employees "
            f"(company_id={cid}, page={page}, page_size={page_size})"
        )

        active_data = self._client.list_active_employees(
            company_id=cid,
            page=page,
            page_size=page_size,
        )

        employees = []
        for emp_data in active_data:
            emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
            person = self._get_cached_person(emp_id) if emp_id else None
            employees.append(Employee.from_ukg(emp_data, person))

        logger.debug(
            f"UKG API: Fetched {len(employees)} employees from page {page}"
        )
        return employees

    def get_employees_with_supervisor(
        self,
        supervisor_id: str,
    ) -> List[Employee]:
        """
        Get employees reporting to a supervisor.

        Args:
            supervisor_id: Supervisor's employee ID

        Returns:
            List of direct reports
        """
        reports = []

        # Paginate through all employees
        page = 1
        while True:
            employees = self._client.list_employees(
                company_id=self._default_company_id,
                page=page,
                page_size=200,
            )

            if not employees:
                break

            for emp_data in employees:
                # Check various supervisor ID fields
                sup_id = (
                    emp_data.get("supervisorEmployeeId")
                    or emp_data.get("supervisor", {}).get("employeeId")
                )
                if sup_id == supervisor_id:
                    emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
                    person = self._get_cached_person(emp_id) if emp_id else None
                    reports.append(Employee.from_ukg(emp_data, person))

            if len(employees) < 200:
                break
            page += 1

        return reports

    def get_person_details(self, employee_id: str) -> Dict[str, Any]:
        """
        Get additional person details from UKG.

        Args:
            employee_id: Employee ID

        Returns:
            Person details dictionary
        """
        return self._get_cached_person(employee_id) or {}

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Employee]:
        """
        List employees with pagination.

        Args:
            page: Page number
            page_size: Page size
            filters: Optional filters (company_id, status)

        Returns:
            List of employees
        """
        filters = filters or {}
        company_id = filters.get("company_id", self._default_company_id)
        status = filters.get("status")

        if status == "active":
            data = self._client.list_active_employees(company_id, page, page_size)
        else:
            data = self._client.list_employees(company_id, page, page_size)

        employees = []
        for emp_data in data:
            emp_id = emp_data.get("employeeId") or emp_data.get("employeeID")
            person = self._get_cached_person(emp_id) if emp_id else None
            employees.append(Employee.from_ukg(emp_data, person))

        return employees

    def create(self, entity: Employee) -> Employee:
        """
        Create operation not supported for UKG repository.

        UKG is a read-only source for this integration.
        """
        raise NotImplementedError("UKG repository is read-only")

    def update(self, entity: Employee) -> Employee:
        """
        Update operation not supported for UKG repository.

        UKG is a read-only source for this integration.
        """
        raise NotImplementedError("UKG repository is read-only")

    def delete(self, entity_id: str) -> bool:
        """
        Delete operation not supported for UKG repository.

        UKG is a read-only source for this integration.
        """
        raise NotImplementedError("UKG repository is read-only")

    def resolve_supervisor_email(
        self,
        employee: Employee,
    ) -> Optional[str]:
        """
        Resolve supervisor email for an employee.

        Uses the UKG client's supervisor resolution logic with caching.

        Args:
            employee: Employee to resolve supervisor for

        Returns:
            Supervisor email or None
        """
        # If already have supervisor email, return it
        if employee.supervisor_email:
            return employee.supervisor_email

        # Get employment data from metadata
        employment_data = employee.metadata.get("ukg_data", {})
        person_data = employee.metadata.get("person_data")

        if not employment_data:
            # Try to fetch fresh data
            if employee.employee_number and employee.company_id:
                employment_data = self._client.get_employment_details(
                    employee.employee_number,
                    employee.company_id,
                ) or {}

        return self._client.get_supervisor_email(
            employment_data,
            person_data,
            self._person_cache,
        )

    def _get_cached_person(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get person details with caching."""
        if not employee_id:
            return None

        if employee_id not in self._person_cache:
            person = self._client.get_person_details(employee_id)
            if person:
                self._person_cache[employee_id] = person

        return self._person_cache.get(employee_id)

    def clear_cache(self) -> None:
        """Clear the person details cache."""
        self._person_cache.clear()
