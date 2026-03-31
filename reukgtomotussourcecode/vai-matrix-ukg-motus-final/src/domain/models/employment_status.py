"""
Employment status definitions.

Defines employment status types for driver synchronization.
"""

from enum import Enum
from typing import Any, Dict, Optional, Set


class EmploymentStatus(Enum):
    """Employment status types."""

    ACTIVE = "Active"
    LEAVE = "Leave"
    TERMINATED = "Terminated"
    UNKNOWN = "Unknown"


# UKG employment status codes that indicate termination
TERMINATED_STATUS_CODES: Set[str] = {"T", "TERM", "TERMINATED", "I", "INACTIVE"}

# UKG employment status codes that indicate leave of absence
LEAVE_STATUS_CODES: Set[str] = {"L", "LOA", "LEAVE"}

# UKG employment status codes that indicate active employment
ACTIVE_STATUS_CODES: Set[str] = {"A", "ACTIVE", "F", "FULLTIME", "P", "PARTTIME"}


def determine_employment_status(
    status_code: Optional[str] = None,
    leave_start_date: Optional[str] = None,
    leave_end_date: Optional[str] = None,
    termination_date: Optional[str] = None,
) -> EmploymentStatus:
    """
    Determine employment status from employment details.

    Priority order:
    1. Termination date present -> TERMINATED
    2. Status code indicates terminated -> TERMINATED
    3. Leave start date without end date -> LEAVE
    4. Status code indicates leave -> LEAVE
    5. Status code indicates active -> ACTIVE
    6. Default -> ACTIVE

    Args:
        status_code: Employment status code from UKG (e.g., 'A', 'T', 'L')
        leave_start_date: Leave start date
        leave_end_date: Leave end date
        termination_date: Termination date

    Returns:
        EmploymentStatus enum value
    """
    # Normalize status code for comparison
    normalized_status = status_code.upper().strip() if status_code else ""

    # Check for terminated - termination date takes highest priority
    if termination_date:
        return EmploymentStatus.TERMINATED

    # Check for terminated via status code
    if normalized_status in TERMINATED_STATUS_CODES:
        return EmploymentStatus.TERMINATED

    # Check for active leave of absence (has start date but no end date)
    if leave_start_date and not leave_end_date:
        return EmploymentStatus.LEAVE

    # Check for leave via status code
    if normalized_status in LEAVE_STATUS_CODES:
        return EmploymentStatus.LEAVE

    # Check for active via status code
    if normalized_status in ACTIVE_STATUS_CODES:
        return EmploymentStatus.ACTIVE

    # Default to Active if any status code exists
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
        leave_start_date=employment_details.get("employeeStatusStartDate"),
        leave_end_date=employment_details.get("employeeStatusExpectedEndDate"),
        termination_date=employment_details.get("dateOfTermination"),
    )
