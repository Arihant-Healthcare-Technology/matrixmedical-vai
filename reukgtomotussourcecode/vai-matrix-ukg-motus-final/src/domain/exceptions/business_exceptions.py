"""
Business exceptions.

Provides exception classes for business logic errors.
"""

from typing import List, Optional


class DriverValidationError(Exception):
    """Exception for driver validation failures."""

    def __init__(
        self,
        message: str,
        errors: Optional[List[str]] = None,
        employee_number: Optional[str] = None,
    ):
        super().__init__(message)
        self.errors = errors or []
        self.employee_number = employee_number


class EmployeeNotFoundError(Exception):
    """Exception when employee is not found in UKG."""

    def __init__(
        self,
        message: str,
        employee_number: Optional[str] = None,
        company_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.employee_number = employee_number
        self.company_id = company_id


class ProgramNotFoundError(Exception):
    """Exception when program ID cannot be determined from job code."""

    def __init__(
        self,
        message: str,
        job_code: Optional[str] = None,
        employee_number: Optional[str] = None,
    ):
        super().__init__(message)
        self.job_code = job_code
        self.employee_number = employee_number
