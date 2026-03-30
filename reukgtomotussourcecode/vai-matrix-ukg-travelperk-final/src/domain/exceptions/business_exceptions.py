"""Business logic exceptions."""

from typing import List, Optional


class UserValidationError(Exception):
    """Exception for user validation failures."""

    def __init__(self, errors: List[str], external_id: Optional[str] = None):
        self.errors = errors
        self.external_id = external_id
        message = f"User validation failed: {'; '.join(errors)}"
        if external_id:
            message = f"[{external_id}] {message}"
        super().__init__(message)


class EmployeeNotFoundError(Exception):
    """Exception when employee is not found in UKG."""

    def __init__(
        self,
        employee_number: str,
        company_id: Optional[str] = None,
    ):
        self.employee_number = employee_number
        self.company_id = company_id
        message = f"Employee not found: {employee_number}"
        if company_id:
            message += f" (company: {company_id})"
        super().__init__(message)


class SupervisorNotFoundError(Exception):
    """Exception when supervisor is not found."""

    def __init__(
        self,
        supervisor_employee_number: str,
        employee_number: str,
    ):
        self.supervisor_employee_number = supervisor_employee_number
        self.employee_number = employee_number
        super().__init__(
            f"Supervisor {supervisor_employee_number} not found "
            f"for employee {employee_number}"
        )
