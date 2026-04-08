"""
UKG Pro API client adapter.

This module provides the UKG API client for fetching employee data.
It extracts and refactors the API logic from build-bill-entity.py.
"""

import base64
import logging
from typing import Any, Dict, List, Optional

from src.domain.exceptions import AuthenticationError, ConfigurationError
from src.infrastructure.config.constants import DEFAULT_TIMEOUT, MAX_RETRIES
from src.infrastructure.http.client import UKGHttpClient
from src.infrastructure.http.response import safe_json

logger = logging.getLogger(__name__)


class UKGClient:
    """
    UKG Pro API client.

    Provides methods for fetching employee data from UKG Pro.
    Extracts the API logic from build-bill-entity.py into a reusable client.

    Example:
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            username="user",
            password="pass",
            customer_api_key="key",
        )
        employee = client.get_employee_by_number("12345", "COMP1")
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        basic_auth_token: Optional[str] = None,
        customer_api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """
        Initialize UKG client.

        Args:
            base_url: UKG API base URL (e.g., https://service4.ultipro.com)
            username: UKG username (optional if basic_auth_token provided)
            password: UKG password (optional if basic_auth_token provided)
            basic_auth_token: Pre-encoded base64 Basic auth token
            customer_api_key: UKG Customer API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limiter: Optional rate limiter
        """
        # Get or create Basic auth token
        auth_token = self._get_auth_token(basic_auth_token, username, password)

        if not customer_api_key:
            raise ConfigurationError(
                "Missing UKG Customer API key",
                config_key="UKG_CUSTOMER_API_KEY",
            )

        self._http = UKGHttpClient(
            base_url=base_url,
            basic_auth_token=auth_token,
            customer_api_key=customer_api_key,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )
        self._base_url = base_url

    @staticmethod
    def _get_auth_token(
        basic_auth_token: Optional[str],
        username: Optional[str],
        password: Optional[str],
    ) -> str:
        """
        Get or create Basic auth token.

        Logic extracted from build-bill-entity.py _get_token().
        """
        if basic_auth_token:
            # Validate the token
            token = "".join(basic_auth_token.strip().split())
            try:
                base64.b64decode(token, validate=True)
                return token
            except Exception:
                logger.warning("Invalid basic_auth_token provided, falling back to username/password")

        if not username or not password:
            raise ConfigurationError(
                "Missing UKG credentials. Provide either basic_auth_token or username/password.",
                config_key="UKG_USERNAME",
            )

        return base64.b64encode(f"{username}:{password}".encode()).decode()

    def _get_data(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make GET request and return JSON data.

        Args:
            path: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response
        """
        # Log request with sanitized params
        safe_params = {k: "***" if "password" in k.lower() else v
                       for k, v in (params or {}).items()}
        logger.debug(f"UKG API GET {path} params={safe_params}")

        response = self._http.get(path, params=params)
        response.raise_for_status()
        data = safe_json(response)

        # Log response summary
        if isinstance(data, list):
            logger.debug(f"UKG API response: {path} -> {len(data)} records")
        elif isinstance(data, dict):
            logger.debug(f"UKG API response: {path} -> keys={list(data.keys())[:5]}")

        return data

    def _extract_list(self, data: Any) -> List[Dict[str, Any]]:
        """
        Extract list from varying API response formats.

        UKG API sometimes returns a list directly, sometimes a single object.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    # =========================================================================
    # Employee Employment Details
    # =========================================================================

    def get_employment_details(
        self,
        employee_number: str,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get employment details for an employee.

        This endpoint returns employment dates, status, organization, job info.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employment details dict or None if not found
        """
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get_data("/personnel/v1/employment-details", params)
        items = self._extract_list(data)

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    return item

        return None

    def get_employee_employment_details(
        self,
        employee_number: str,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get employee-employment details (includes project codes).

        This is a different endpoint from employment-details.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employee employment details dict or None if not found
        """
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get_data("/personnel/v1/employee-employment-details", params)
        items = self._extract_list(data)

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    return item

        return None

    def get_person_details(
        self,
        employee_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get person details for an employee.

        This endpoint returns personal info like name, email, address.

        Args:
            employee_id: Employee ID (UUID format)

        Returns:
            Person details dict or None if not found
        """
        if not employee_id:
            return None

        params = {"employeeId": employee_id}
        data = self._get_data("/personnel/v1/person-details", params)
        items = self._extract_list(data)

        for item in items:
            if str(item.get("employeeId")) == str(employee_id):
                return item

        # If only one result, return it
        if len(items) == 1:
            return items[0]

        return None

    # =========================================================================
    # List Operations
    # =========================================================================

    def list_employees(
        self,
        company_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        List all employees with pagination.

        Args:
            company_id: Optional company filter
            page: Page number (1-indexed)
            page_size: Page size

        Returns:
            List of employee records
        """
        logger.info(f"UKG listing employees: companyId={company_id} page={page} pageSize={page_size}")

        params: Dict[str, Any] = {
            "page": page,
            "per_page": page_size,
        }
        if company_id:
            params["companyID"] = company_id

        data = self._get_data("/personnel/v1/employment-details", params)
        result = self._extract_list(data)
        logger.info(f"UKG employees listed: count={len(result)} companyId={company_id}")
        return result

    def list_active_employees(
        self,
        company_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        List active employees (status code 'A').

        Args:
            company_id: Optional company filter
            page: Page number
            page_size: Page size

        Returns:
            List of active employee records
        """
        all_employees = self.list_employees(company_id, page, page_size)

        # Filter to active employees
        active = []
        for emp in all_employees:
            status_code = str(emp.get("employeeStatusCode", "")).strip().upper()
            if status_code == "A":
                active.append(emp)

        return active

    # =========================================================================
    # Supervisor Resolution
    # =========================================================================

    def get_supervisor_email(
        self,
        employment_data: Dict[str, Any],
        person_data: Optional[Dict[str, Any]] = None,
        person_cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Resolve supervisor email using multiple fallback strategies.

        Implements the supervisor resolution logic from run-bill-batch.py:
        1. Direct supervisorEmailAddress field
        2. Supervisor employee ID -> person details
        3. Supervisor employee number -> employment -> person details

        Args:
            employment_data: Employment details dict
            person_data: Optional person details dict
            person_cache: Optional cache for person lookups

        Returns:
            Supervisor email or None
        """
        person_cache = person_cache or {}

        # Strategy 1: Direct supervisorEmailAddress
        supervisor_email = employment_data.get("supervisorEmailAddress")
        if supervisor_email:
            return supervisor_email

        # Also check supervisor nested object
        supervisor = employment_data.get("supervisor", {}) or {}
        if supervisor.get("emailAddress"):
            return supervisor["emailAddress"]

        # Check person data
        if person_data and person_data.get("supervisorEmailAddress"):
            return person_data["supervisorEmailAddress"]

        # Strategy 2: Supervisor employee ID -> person details
        supervisor_emp_id = (
            employment_data.get("supervisorEmployeeId")
            or supervisor.get("employeeId")
        )
        if supervisor_emp_id:
            # Check cache first
            if supervisor_emp_id in person_cache:
                cached = person_cache[supervisor_emp_id]
                email = cached.get("emailAddress")
                if email:
                    return email
            else:
                # Fetch person details
                sup_person = self.get_person_details(supervisor_emp_id)
                if sup_person:
                    person_cache[supervisor_emp_id] = sup_person
                    email = sup_person.get("emailAddress")
                    if email:
                        return email

        # Strategy 3: Supervisor employee number -> employment -> person
        supervisor_emp_number = (
            employment_data.get("supervisorEmployeeNumber")
            or supervisor.get("employeeNumber")
        )
        if supervisor_emp_number:
            company_id = (
                employment_data.get("companyID")
                or employment_data.get("companyId")
            )
            if company_id:
                sup_employment = self.get_employment_details(
                    supervisor_emp_number, company_id
                )
                if sup_employment:
                    sup_emp_id = (
                        sup_employment.get("employeeId")
                        or sup_employment.get("employeeID")
                    )
                    if sup_emp_id:
                        sup_person = self.get_person_details(sup_emp_id)
                        if sup_person:
                            email = sup_person.get("emailAddress")
                            if email:
                                return email

        return None

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_employee_full_data(
        self,
        employee_number: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """
        Get complete employee data from all UKG endpoints.

        Combines data from:
        - employment-details
        - employee-employment-details
        - person-details

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Combined employee data dict

        Raises:
            ValueError: If employee not found
        """
        logger.info(f"UKG fetching full employee data: employeeNumber={employee_number} companyId={company_id}")

        # Get employment details
        employment = self.get_employment_details(employee_number, company_id)
        if not employment:
            logger.warning(f"UKG employee not found: employeeNumber={employee_number} companyId={company_id}")
            raise ValueError(
                f"Employee not found: employeeNumber={employee_number}, "
                f"companyID={company_id}"
            )

        # Get employee-employment details
        emp_emp = self.get_employee_employment_details(employee_number, company_id)

        # Resolve employee ID
        employee_id = (
            employment.get("employeeId")
            or employment.get("employeeID")
            or (emp_emp or {}).get("employeeId")
            or (emp_emp or {}).get("employeeID")
        )

        # Get person details
        person = None
        if employee_id:
            person = self.get_person_details(employee_id)

        logger.info(f"UKG full employee data fetched: employeeNumber={employee_number} employeeId={employee_id}")

        return {
            "employment": employment,
            "employee_employment": emp_emp or {},
            "person": person or {},
            "employee_id": employee_id,
            "employee_number": employee_number,
            "company_id": company_id,
        }

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> "UKGClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
