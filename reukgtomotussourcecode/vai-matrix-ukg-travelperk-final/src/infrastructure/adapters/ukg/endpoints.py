"""
UKG API endpoint definitions.

Centralizes all UKG API endpoint paths and provides
endpoint builders for consistent URL construction.
"""

from typing import Dict, Any, Optional


class UKGEndpoints:
    """UKG API endpoint definitions."""

    # Personnel API endpoints
    EMPLOYMENT_DETAILS = "/personnel/v1/employee-employment-details"
    PERSON_DETAILS = "/personnel/v1/person-details"
    SUPERVISOR_DETAILS = "/personnel/v1/employee-supervisor-details"

    # Configuration API endpoints
    ORG_LEVELS = "/configuration/v1/org-levels"

    # Pagination constants
    MAX_PAGE_SIZE = 2147483647  # Used to fetch all records

    @classmethod
    def employment_details_params(
        cls,
        employee_number: Optional[str] = None,
        company_id: Optional[str] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build query parameters for employment details endpoint.

        Args:
            employee_number: Filter by employee number
            company_id: Filter by company ID
            per_page: Number of records per page

        Returns:
            Dict of query parameters
        """
        params: Dict[str, Any] = {}

        if employee_number:
            params["employeeNumber"] = employee_number
        if company_id:
            params["companyId"] = company_id
        if per_page:
            params["per_Page"] = per_page

        return params

    @classmethod
    def person_details_params(cls, employee_id: str) -> Dict[str, Any]:
        """
        Build query parameters for person details endpoint.

        Args:
            employee_id: Employee ID

        Returns:
            Dict of query parameters
        """
        return {"employeeId": employee_id}

    @classmethod
    def supervisor_details_params(
        cls,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build query parameters for supervisor details endpoint.

        Args:
            per_page: Number of records per page

        Returns:
            Dict of query parameters
        """
        params: Dict[str, Any] = {}
        if per_page:
            params["per_Page"] = per_page
        return params
