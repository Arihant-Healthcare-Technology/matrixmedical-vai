"""
BillUser mapping functions.

Provides mappers for transforming between BillUser domain models and BILL API formats.
"""

from typing import Any, Dict, Optional

from src.domain.models.bill_user import BillRole, BillUser
from src.domain.models.employee import Employee


def map_bill_user_from_api(data: Dict[str, Any]) -> BillUser:
    """
    Map BILL S&E API response to BillUser domain model.

    Args:
        data: API response data

    Returns:
        BillUser domain model
    """
    return BillUser.from_bill_api(data)


def map_bill_user_to_api(user: BillUser) -> Dict[str, Any]:
    """
    Map BillUser domain model to API payload.

    Args:
        user: BillUser domain model

    Returns:
        API payload dict
    """
    return user.to_api_payload()


def map_employee_to_bill_user(
    employee: Employee,
    role: Optional[BillRole] = None,
    manager_email: Optional[str] = None,
) -> BillUser:
    """
    Map Employee domain model to BillUser for S&E provisioning.

    Args:
        employee: Source Employee
        role: Optional role override (defaults to MEMBER)
        manager_email: Optional manager email override

    Returns:
        BillUser domain model
    """
    return BillUser.from_employee(
        employee,
        role=role,
        manager_email=manager_email,
    )


def build_bill_user_csv_row(user: BillUser) -> Dict[str, str]:
    """
    Build CSV row for BILL bulk import.

    Uses BillUser.to_csv_row() which includes all fields required
    for BILL.com CSV bulk import.

    Args:
        user: BillUser to export

    Returns:
        Dict suitable for csv.DictWriter with columns:
        - first name, last name, email address, role, manager
        - cost center (formatted as "CODE – Description")
        - budget count (department name from Bill.com, resolved from cost center prefix)
        - company (UKG companyID: J9A6Y = companyCode: CCHN)
        - employee type (PRD, FTC, HRC from UKG employeeTypeCode)
        - sal ("Salaried" or "Hourly" from UKG payFrequency)
    """
    return user.to_csv_row()
