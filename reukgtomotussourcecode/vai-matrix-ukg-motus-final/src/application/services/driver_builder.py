"""
Driver builder service.

Builds Motus driver payloads from UKG data.
"""

from typing import Any, Dict, Optional

from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError
from src.domain.models import MotusDriver
from src.domain.models.employment_status import determine_employment_status_from_dict
from src.domain.models.program import resolve_program_id_from_job_code
from src.infrastructure.adapters.ukg import UKGClient


class DriverBuilderService:
    """Service for building Motus drivers from UKG data."""

    def __init__(self, ukg_client: UKGClient, debug: bool = False):
        """
        Initialize driver builder service.

        Args:
            ukg_client: UKG API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.debug = debug

    def _log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def build_driver(
        self,
        employee_number: str,
        company_id: str,
    ) -> MotusDriver:
        """
        Build a Motus driver from UKG data.

        Args:
            employee_number: UKG employee number
            company_id: UKG company ID

        Returns:
            MotusDriver instance

        Raises:
            EmployeeNotFoundError: If employee not found
            ProgramNotFoundError: If program ID cannot be determined
        """
        # 1) Get employment details
        employment_details = self.ukg_client.get_employment_details(
            employee_number, company_id
        )
        if not employment_details:
            raise EmployeeNotFoundError(
                f"No employment details found for employeeNumber={employee_number} "
                f"companyID={company_id}",
                employee_number=employee_number,
                company_id=company_id,
            )

        # 2) Get employee employment details for project info
        employee_employment = self.ukg_client.get_employee_employment_details(
            employee_number, company_id
        )

        # 3) Resolve employee ID
        employee_id = (
            employment_details.get("employeeId")
            or employment_details.get("employeeID")
            or employee_employment.get("employeeId")
            or employee_employment.get("employeeID")
        )
        if not employee_id:
            raise EmployeeNotFoundError(
                f"No employeeId found for employeeNumber={employee_number} "
                f"companyID={company_id}",
                employee_number=employee_number,
                company_id=company_id,
            )

        # 4) Get person details
        person = self.ukg_client.get_person_details(employee_id)

        # 5) Get supervisor details
        supervisor = self.ukg_client.get_supervisor_details(employee_id)
        supervisor_name = ""
        if supervisor:
            sup_first = supervisor.get("supervisorFirstName", "") or ""
            sup_last = supervisor.get("supervisorLastName", "") or ""
            supervisor_name = f"{sup_first} {sup_last}".strip()

        # 6) Determine employment status
        derived_status = determine_employment_status_from_dict(employment_details)

        # 7) Get location
        location: Dict[str, Any] = {}
        loc_code = employment_details.get("primaryWorkLocationCode")
        if loc_code:
            location = self.ukg_client.get_location(loc_code)

        # 8) Get project info
        project_code = employee_employment.get("primaryProjectCode") or ""
        project_label = employee_employment.get("primaryProjectDescription") or ""

        # 9) Resolve program ID from job code
        job_code = employment_details.get("primaryJobCode")
        program_id = resolve_program_id_from_job_code(job_code)
        if not program_id:
            raise ProgramNotFoundError(
                f"No programId found for employeeNumber={employee_number} "
                f"companyID={company_id} jobCode={job_code}",
                job_code=str(job_code) if job_code else None,
                employee_number=employee_number,
            )

        # 10) Build driver
        return MotusDriver.from_ukg_data(
            employee_number=employee_number,
            program_id=program_id,
            person=person,
            employment_details=employment_details,
            supervisor_name=supervisor_name,
            location=location,
            project_code=project_code,
            project_label=project_label,
            derived_status=derived_status.value,
        )
