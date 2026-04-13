"""
Driver builder service.

Builds Motus driver payloads from UKG data.
"""

import logging
from typing import Any, Dict, Optional

from common.correlation import get_correlation_id
from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError
from src.domain.models import MotusDriver
from src.domain.models.employment_status import determine_employment_status_from_dict
from src.domain.models.program import resolve_program_id_from_job_code
from src.infrastructure.adapters.ukg import UKGClient

logger = logging.getLogger(__name__)


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
            logger.debug(message)

    def build_driver(
        self,
        employee_number: str,
        company_id: str,
        existing_supervisor_name: str = "",
    ) -> MotusDriver:
        """
        Build a Motus driver from UKG data.

        Args:
            employee_number: UKG employee number
            company_id: UKG company ID
            existing_supervisor_name: Existing supervisor name from Motus (fallback)

        Returns:
            MotusDriver instance

        Raises:
            EmployeeNotFoundError: If employee not found
            ProgramNotFoundError: If program ID cannot be determined
        """
        correlation_id = get_correlation_id()

        logger.info(
            f"[{correlation_id}] BUILD START | "
            f"Employee: {employee_number} | Company: {company_id}"
        )

        # 1) Get employment details
        employment_details = self.ukg_client.get_employment_details(
            employee_number, company_id
        )
        self._log(f"Employee {employee_number}: === EMPLOYMENT DETAILS ===")
        self._log(f"Employee {employee_number}: employment_details keys: {list(employment_details.keys())}")
        self._log(f"Employee {employee_number}: dateOfTermination = {employment_details.get('dateOfTermination')}")
        self._log(f"Employee {employee_number}: employeeStatusStartDate = {employment_details.get('employeeStatusStartDate')}")
        self._log(f"Employee {employee_number}: employeeStatusExpectedEndDate = {employment_details.get('employeeStatusExpectedEndDate')}")
        self._log(f"Employee {employee_number}: employeeStatusCode = {employment_details.get('employeeStatusCode')}")
        self._log(f"Employee {employee_number}: originalHireDate = {employment_details.get('originalHireDate')}")
        self._log(f"Employee {employee_number}: primaryJobCode = {employment_details.get('primaryJobCode')}")
        if not employment_details:
            logger.error(
                f"[{correlation_id}] BUILD ERROR | "
                f"Employee: {employee_number} | "
                f"Reason: No employment details found"
            )
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
        self._log(f"Employee {employee_number}: === EMPLOYEE EMPLOYMENT DETAILS ===")
        self._log(f"Employee {employee_number}: employee_employment keys: {list(employee_employment.keys())}")
        self._log(f"Employee {employee_number}: primaryProjectCode = {employee_employment.get('primaryProjectCode')}")
        self._log(f"Employee {employee_number}: primaryProjectDescription = {employee_employment.get('primaryProjectDescription')}")

        # 3) Resolve employee ID
        employee_id = (
            employment_details.get("employeeId")
            or employment_details.get("employeeID")
            or employee_employment.get("employeeId")
            or employee_employment.get("employeeID")
        )
        if not employee_id:
            logger.error(
                f"[{correlation_id}] BUILD ERROR | "
                f"Employee: {employee_number} | "
                f"Reason: No employeeId found"
            )
            raise EmployeeNotFoundError(
                f"No employeeId found for employeeNumber={employee_number} "
                f"companyID={company_id}",
                employee_number=employee_number,
                company_id=company_id,
            )

        # 4) Get person details
        person = self.ukg_client.get_person_details(employee_id)
        self._log(f"Employee {employee_number}: === PERSON DETAILS ===")
        self._log(f"Employee {employee_number}: person keys: {list(person.keys())}")
        self._log(f"Employee {employee_number}: firstName = {person.get('firstName')}")
        self._log(f"Employee {employee_number}: lastName = {person.get('lastName')}")
        self._log(f"Employee {employee_number}: emailAddress = {person.get('emailAddress')}")
        self._log(f"Employee {employee_number}: addressLine1 = {person.get('addressLine1')}")
        self._log(f"Employee {employee_number}: addressCity = {person.get('addressCity')}")
        self._log(f"Employee {employee_number}: addressState = {person.get('addressState')}")
        self._log(f"Employee {employee_number}: addressZipCode = {person.get('addressZipCode')}")

        # 5) Get supervisor details
        supervisor = self.ukg_client.get_supervisor_details(employee_id)
        supervisor_name = ""
        if supervisor:
            sup_first = supervisor.get("supervisorFirstName", "") or ""
            sup_last = supervisor.get("supervisorLastName", "") or ""
            supervisor_name = f"{sup_first} {sup_last}".strip()
        self._log(f"Employee {employee_number}: === SUPERVISOR DETAILS ===")
        self._log(f"Employee {employee_number}: supervisor keys: {list(supervisor.keys()) if supervisor else []}")
        self._log(f"Employee {employee_number}: supervisor_name = {supervisor_name}")

        # 6) Determine employment status
        derived_status = determine_employment_status_from_dict(employment_details)
        self._log(f"Employee {employee_number}: === STATUS DETERMINATION ===")
        self._log(f"Employee {employee_number}: Input - employeeStatusCode = {employment_details.get('employeeStatusCode')}")
        self._log(f"Employee {employee_number}: Input - employeeStatusStartDate = {employment_details.get('employeeStatusStartDate')}")
        self._log(f"Employee {employee_number}: Input - employeeStatusExpectedEndDate = {employment_details.get('employeeStatusExpectedEndDate')}")
        self._log(f"Employee {employee_number}: Input - dateOfTermination = {employment_details.get('dateOfTermination')}")
        self._log(f"Employee {employee_number}: Output - derived_status = {derived_status.value}")

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
            logger.error(
                f"[{correlation_id}] BUILD ERROR | "
                f"Employee: {employee_number} | "
                f"Reason: No programId for jobCode={job_code}"
            )
            raise ProgramNotFoundError(
                f"No programId found for employeeNumber={employee_number} "
                f"companyID={company_id} jobCode={job_code}",
                job_code=str(job_code) if job_code else None,
                employee_number=employee_number,
            )

        # 10) Build driver
        self._log(f"Employee {employee_number}: === BUILDING DRIVER ===")
        self._log(f"Employee {employee_number}: project_code = {project_code}")
        self._log(f"Employee {employee_number}: project_label = {project_label}")
        self._log(f"Employee {employee_number}: program_id = {program_id}")
        self._log(f"Employee {employee_number}: job_code = {job_code}")
        self._log(f"Employee {employee_number}: location = {location}")

        driver = MotusDriver.from_ukg_data(
            employee_number=employee_number,
            program_id=program_id,
            person=person,
            employment_details=employment_details,
            supervisor_name=supervisor_name,
            location=location,
            project_code=project_code,
            project_label=project_label,
            derived_status=derived_status.value,
            existing_supervisor_name=existing_supervisor_name,
        )

        self._log(f"Employee {employee_number}: === FINAL DRIVER PAYLOAD SUMMARY ===")
        self._log(f"Employee {employee_number}: client_employee_id1 = {driver.client_employee_id1}")
        self._log(f"Employee {employee_number}: program_id = {driver.program_id}")
        self._log(f"Employee {employee_number}: start_date = {driver.start_date}")
        self._log(f"Employee {employee_number}: end_date = {driver.end_date}")
        self._log(f"Employee {employee_number}: leave_start_date = {driver.leave_start_date}")
        self._log(f"Employee {employee_number}: leave_end_date = {driver.leave_end_date}")
        for cv in driver.custom_variables:
            self._log(f"Employee {employee_number}: CV[{cv.name}] = {cv.value}")

        logger.info(
            f"[{correlation_id}] BUILD COMPLETE | "
            f"Employee: {employee_number} | "
            f"Name: {driver.first_name} {driver.last_name} | "
            f"Program: {program_id}"
        )

        return driver
