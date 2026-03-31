"""
UKG API mock fixtures using responses library.

Provides mock server class for UKG Pro API endpoints.
"""

import re
from typing import Any, Callable, Dict, List, Optional

import responses

from .mock_data import UKGMockDataFactory


class UKGMockServer:
    """Helper class to set up UKG API mocks using responses library."""

    DEFAULT_BASE_URL = "https://service4.ultipro.com"

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize UKG mock server.

        Args:
            base_url: UKG API base URL (defaults to DEFAULT_BASE_URL)
        """
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.factory = UKGMockDataFactory()

    def mock_employment_details(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        status: int = 200,
        employee_number: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> None:
        """
        Mock employment-details endpoint.

        Args:
            data: Response data (defaults to sample data)
            status: HTTP status code
            employee_number: Filter by employee number
            company_id: Filter by company ID
        """
        if data is None:
            emp_data = self.factory.employment_details(
                employee_number=employee_number or "12345",
                company_id=company_id or "J9A6Y",
            )
            data = [emp_data]

        pattern = rf"{re.escape(self.base_url)}/personnel/v1/employment-details.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_employee_employment_details(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        status: int = 200,
        employee_number: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> None:
        """
        Mock employee-employment-details endpoint.

        Args:
            data: Response data (defaults to sample data)
            status: HTTP status code
            employee_number: Employee number
            company_id: Company ID
        """
        if data is None:
            data = [
                self.factory.employee_employment_details(
                    employee_number=employee_number or "12345",
                    company_id=company_id or "J9A6Y",
                )
            ]

        pattern = rf"{re.escape(self.base_url)}/personnel/v1/employee-employment-details.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_person_details(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        status: int = 200,
        employee_id: Optional[str] = None,
    ) -> None:
        """
        Mock person-details endpoint.

        Args:
            data: Response data (defaults to sample data)
            status: HTTP status code
            employee_id: Employee ID
        """
        if data is None:
            data = [self.factory.person_details(employee_id=employee_id or "EMP001")]

        pattern = rf"{re.escape(self.base_url)}/personnel/v1/person-details.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_supervisor_details(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        status: int = 200,
        employee_id: Optional[str] = None,
    ) -> None:
        """
        Mock supervisor-details endpoint.

        Args:
            data: Response data (defaults to sample data)
            status: HTTP status code
            employee_id: Employee ID
        """
        if data is None:
            data = [self.factory.supervisor_details(employee_id=employee_id or "EMP001")]

        pattern = rf"{re.escape(self.base_url)}/personnel/v1/supervisor-details.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_supervisor_not_found(self) -> None:
        """Mock supervisor-details endpoint returning 404."""
        pattern = rf"{re.escape(self.base_url)}/personnel/v1/supervisor-details.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json={"error": "Not found"},
            status=404,
        )

    def mock_location(
        self,
        data: Optional[Dict[str, Any]] = None,
        status: int = 200,
        location_code: Optional[str] = None,
    ) -> None:
        """
        Mock locations endpoint (both path and query param versions).

        Args:
            data: Response data (defaults to sample data)
            status: HTTP status code
            location_code: Location code
        """
        if data is None:
            data = self.factory.location(code=location_code or "LOC001")

        # Mock both endpoint variants
        # 1. /configuration/v1/locations/{code}
        pattern1 = rf"{re.escape(self.base_url)}/configuration/v1/locations/[^?]+"
        responses.add(
            responses.GET,
            re.compile(pattern1),
            json=data,
            status=status,
        )

        # 2. /configuration/v1/locations?locationCode=xxx
        pattern2 = rf"{re.escape(self.base_url)}/configuration/v1/locations\?.*"
        responses.add(
            responses.GET,
            re.compile(pattern2),
            json=data,
            status=status,
        )

    def mock_location_not_found(self) -> None:
        """Mock locations endpoint returning 404."""
        pattern1 = rf"{re.escape(self.base_url)}/configuration/v1/locations/[^?]+"
        responses.add(
            responses.GET,
            re.compile(pattern1),
            json={"error": "Not found"},
            status=404,
        )

        pattern2 = rf"{re.escape(self.base_url)}/configuration/v1/locations\?.*"
        responses.add(
            responses.GET,
            re.compile(pattern2),
            json={"error": "Not found"},
            status=404,
        )

    def mock_all_standard(
        self,
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
        employee_id: str = "EMP001",
    ) -> None:
        """
        Set up all standard UKG mocks for a complete workflow.

        Args:
            employee_number: Employee number
            company_id: Company ID
            employee_id: Employee ID
        """
        self.mock_employment_details(
            employee_number=employee_number,
            company_id=company_id,
        )
        self.mock_employee_employment_details(
            employee_number=employee_number,
            company_id=company_id,
        )
        self.mock_person_details(employee_id=employee_id)
        self.mock_supervisor_details(employee_id=employee_id)
        self.mock_location()

    def mock_active_employee(
        self,
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
    ) -> None:
        """
        Set up mocks for an active employee.

        Args:
            employee_number: Employee number
            company_id: Company ID
        """
        employee_data = self.factory.active_employee(
            employee_number=employee_number,
            company_id=company_id,
        )

        self.mock_employment_details(data=[employee_data["employment"]])
        self.mock_employee_employment_details(data=[employee_data["employee_employment"]])
        self.mock_person_details(data=[employee_data["person"]])
        self.mock_supervisor_details(data=[employee_data["supervisor"]])
        self.mock_location(data=employee_data["location"])

    def mock_terminated_employee(
        self,
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
        termination_date: str = "2024-03-01T00:00:00Z",
    ) -> None:
        """
        Set up mocks for a terminated employee.

        Args:
            employee_number: Employee number
            company_id: Company ID
            termination_date: Termination date
        """
        employee_data = self.factory.terminated_employee(
            employee_number=employee_number,
            company_id=company_id,
            termination_date=termination_date,
        )

        self.mock_employment_details(data=[employee_data["employment"]])
        self.mock_employee_employment_details(data=[employee_data["employee_employment"]])
        self.mock_person_details(data=[employee_data["person"]])
        self.mock_supervisor_details(data=[employee_data["supervisor"]])
        self.mock_location(data=employee_data["location"])

    def mock_leave_employee(
        self,
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
        leave_start_date: str = "2024-02-01T00:00:00Z",
        leave_end_date: Optional[str] = None,
    ) -> None:
        """
        Set up mocks for an employee on leave.

        Args:
            employee_number: Employee number
            company_id: Company ID
            leave_start_date: Leave start date
            leave_end_date: Leave end date (None for indefinite leave)
        """
        employee_data = self.factory.leave_employee(
            employee_number=employee_number,
            company_id=company_id,
            leave_start_date=leave_start_date,
            leave_end_date=leave_end_date,
        )

        self.mock_employment_details(data=[employee_data["employment"]])
        self.mock_employee_employment_details(data=[employee_data["employee_employment"]])
        self.mock_person_details(data=[employee_data["person"]])
        self.mock_supervisor_details(data=[employee_data["supervisor"]])
        self.mock_location(data=employee_data["location"])

    def mock_unauthorized(self) -> None:
        """Mock all endpoints returning 401 Unauthorized."""
        patterns = [
            r"/personnel/v1/employment-details",
            r"/personnel/v1/employee-employment-details",
            r"/personnel/v1/person-details",
            r"/personnel/v1/supervisor-details",
            r"/configuration/v1/locations",
        ]

        for endpoint in patterns:
            pattern = rf"{re.escape(self.base_url)}{endpoint}.*"
            responses.add(
                responses.GET,
                re.compile(pattern),
                json={"error": "Unauthorized"},
                status=401,
            )

    def mock_server_error(self) -> None:
        """Mock all endpoints returning 500 Server Error."""
        patterns = [
            r"/personnel/v1/employment-details",
            r"/personnel/v1/employee-employment-details",
            r"/personnel/v1/person-details",
            r"/personnel/v1/supervisor-details",
            r"/configuration/v1/locations",
        ]

        for endpoint in patterns:
            pattern = rf"{re.escape(self.base_url)}{endpoint}.*"
            responses.add(
                responses.GET,
                re.compile(pattern),
                json={"error": "Internal Server Error"},
                status=500,
            )
