"""
UKG data mappers.

Provides mapping functions to transform UKG API data to domain models.

Note: This module uses shared formatters from common/formatters.py
for phone normalization and date parsing.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from common.formatters import normalize_phone, parse_datetime
from src.domain.models.employee import Address, Employee, EmployeeStatus


# Re-export for backward compatibility
def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse UKG date string to datetime.

    Note: This is a wrapper around common.formatters.parse_datetime
    for backward compatibility.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime or None
    """
    return parse_datetime(date_str)


def map_employment_status(data: Dict[str, Any]) -> EmployeeStatus:
    """
    Map UKG employment status to domain enum.

    Args:
        data: UKG employment data

    Returns:
        EmployeeStatus enum value
    """
    # Check termination date first
    termination_date = data.get("terminationDate")
    if termination_date:
        return EmployeeStatus.TERMINATED

    # Check status code
    status_code = str(
        data.get("employeeStatusCode")
        or data.get("statusCode")
        or ""
    ).strip().upper()

    return EmployeeStatus.from_code(status_code)


def map_address(data: Dict[str, Any]) -> Address:
    """
    Map UKG address data to Address domain model.

    Args:
        data: UKG person or employment data containing address fields

    Returns:
        Address domain model
    """
    return Address(
        line1=data.get("addressLine1", "") or data.get("address1", "") or "",
        line2=data.get("addressLine2", "") or data.get("address2", "") or "",
        city=data.get("addressCity", "") or data.get("city", "") or "",
        state=data.get("addressState", "") or data.get("state", "") or data.get("stateCode", "") or "",
        zip_code=data.get("addressZipCode", "") or data.get("zip", "") or data.get("postalCode", "") or "",
        country=data.get("addressCountry", "") or data.get("country", "") or data.get("countryCode", "US") or "US",
    )


def map_employee_from_ukg(
    employment_data: Dict[str, Any],
    person_data: Optional[Dict[str, Any]] = None,
    employee_employment_data: Optional[Dict[str, Any]] = None,
) -> Employee:
    """
    Map UKG API data to Employee domain model.

    This is a more comprehensive mapper than Employee.from_ukg(),
    handling all three UKG data sources.

    Args:
        employment_data: Data from /personnel/v1/employment-details
        person_data: Data from /personnel/v1/person-details
        employee_employment_data: Data from /personnel/v1/employee-employment-details

    Returns:
        Employee domain model
    """
    person = person_data or {}
    emp_emp = employee_employment_data or {}

    # Resolve employee ID from various sources
    employee_id = (
        employment_data.get("employeeId")
        or employment_data.get("employeeID")
        or emp_emp.get("employeeId")
        or emp_emp.get("employeeID")
        or person.get("employeeId")
        or ""
    )

    # Employee number
    employee_number = (
        employment_data.get("employeeNumber")
        or emp_emp.get("employeeNumber")
        or person.get("employeeNumber")
        or ""
    )

    # Name (prefer person data)
    first_name = person.get("firstName") or employment_data.get("firstName") or ""
    last_name = person.get("lastName") or employment_data.get("lastName") or ""

    # Contact info
    email = (
        person.get("emailAddress")
        or employment_data.get("emailAddress")
        or ""
    )
    phone = normalize_phone(
        person.get("workPhone")
        or person.get("mobilePhone")
        or employment_data.get("phoneNumber")
        or ""
    )

    # Parse dates
    hire_date = parse_date(
        employment_data.get("originalHireDate")
        or employment_data.get("hireDate")
    )
    termination_date = parse_date(employment_data.get("terminationDate"))

    # Status
    status = map_employment_status(employment_data)

    # Organization
    department = (
        employment_data.get("departmentDescription")
        or employment_data.get("department")
        or emp_emp.get("departmentDescription")
        or ""
    )
    job_title = (
        employment_data.get("jobDescription")
        or employment_data.get("jobTitle")
        or emp_emp.get("jobDescription")
        or ""
    )
    company_id = (
        employment_data.get("companyID")
        or employment_data.get("companyId")
        or emp_emp.get("companyID")
        or ""
    )
    cost_center = (
        employment_data.get("costCenter")
        or employment_data.get("costCenterCode")
        or emp_emp.get("primaryProjectCode")
        or ""
    )
    cost_center_description = (
        employment_data.get("costCenterDescription")
        or emp_emp.get("primaryProjectDescription")
        or ""
    )
    direct_labor = bool(
        employment_data.get("directLabor")
        or employment_data.get("isDirectLabor")
        or False
    )

    # Employee type and pay frequency
    employee_type_code = (
        employment_data.get("employeeTypeCode")
        or emp_emp.get("employeeTypeCode")
        or ""
    )
    # Full/Part Time - try multiple possible field names
    full_or_part_time = (
        employment_data.get("fullOrPartTime")
        or employment_data.get("fullPartTimeDescription")
        or employment_data.get("fullPartTime")
        or emp_emp.get("fullOrPartTime")
        or emp_emp.get("fullPartTimeDescription")
        or ""
    )
    pay_frequency = (
        employment_data.get("payFrequency")
        or emp_emp.get("payFrequency")
        or ""
    )

    # Supervisor
    supervisor_email = (
        employment_data.get("supervisorEmailAddress")
        or person.get("supervisorEmailAddress")
        or ""
    )
    supervisor_id = (
        employment_data.get("supervisorEmployeeId")
        or employment_data.get("supervisor", {}).get("employeeId")
        or ""
    )

    # Address (prefer person data)
    address = map_address(person) if person else map_address(employment_data)

    return Employee(
        employee_id=employee_id,
        employee_number=employee_number,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        status=status,
        hire_date=hire_date.date() if hire_date else None,
        termination_date=termination_date.date() if termination_date else None,
        department=department,
        job_title=job_title,
        supervisor_email=supervisor_email,
        supervisor_id=supervisor_id,
        company_id=company_id,
        address=address,
        employee_type_code=employee_type_code,
        full_or_part_time=full_or_part_time,
        pay_frequency=pay_frequency,
        cost_center=cost_center,
        cost_center_description=cost_center_description,
        direct_labor=direct_labor,
        metadata={
            "ukg_data": employment_data,
            "person_data": person_data,
            "employee_employment_data": employee_employment_data,
        },
    )


def extract_supervisor_info(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract supervisor information from UKG data.

    Args:
        data: UKG employment data

    Returns:
        Dict with supervisor_email, supervisor_id, supervisor_number
    """
    supervisor = data.get("supervisor", {}) or {}

    return {
        "supervisor_email": (
            data.get("supervisorEmailAddress")
            or supervisor.get("emailAddress")
            or ""
        ),
        "supervisor_id": (
            data.get("supervisorEmployeeId")
            or supervisor.get("employeeId")
            or ""
        ),
        "supervisor_number": (
            data.get("supervisorEmployeeNumber")
            or supervisor.get("employeeNumber")
            or ""
        ),
    }
