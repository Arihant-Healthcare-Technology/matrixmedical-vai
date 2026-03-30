"""
Employment status definitions.

Defines employment status types for driver synchronization.
"""

from enum import Enum
from typing import Any, Dict, Optional


class EmploymentStatus(Enum):
    """Employment status types."""

    ACTIVE = "Active"
    LEAVE = "Leave"
    TERMINATED = "Terminated"
    UNKNOWN = "Unknown"


def determine_employment_status(
    status_code: Optional[str] = None,
    leave_start_date: Optional[str] = None,
    leave_end_date: Optional[str] = None,
    termination_date: Optional[str] = None,
) -> EmploymentStatus:
    """
    Determine employment status from employment details.

    Args:
        status_code: Employment status code from UKG
        leave_start_date: Leave start date
        leave_end_date: Leave end date
        termination_date: Termination date

    Returns:
        EmploymentStatus enum value
    """
    # Check for active leave of absence
    if leave_start_date and not leave_end_date:
        return EmploymentStatus.LEAVE

    # Check for terminated
    if termination_date:
        return EmploymentStatus.TERMINATED

    # Default to Active if status code exists
    if status_code:
        return EmploymentStatus.ACTIVE

    return EmploymentStatus.ACTIVE


def determine_employment_status_from_dict(
    employment_details: Dict[str, Any]
) -> EmploymentStatus:
    """
    Determine employment status from employment details dictionary.

    Args:
        employment_details: UKG employment details dict

    Returns:
        EmploymentStatus enum value
    """
    return determine_employment_status(
        status_code=employment_details.get("employeeStatusCode"),
        leave_start_date=employment_details.get("leaveStartDate"),
        leave_end_date=employment_details.get("leaveEndDate"),
        termination_date=employment_details.get("terminationDate"),
    )
