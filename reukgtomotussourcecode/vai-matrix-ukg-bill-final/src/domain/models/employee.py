"""
Employee domain model - Represents UKG Pro employee data.

This model captures the employee data extracted from UKG Pro that is
relevant for synchronization to BILL.com and other systems.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.domain.exceptions import ValidationError


class EmployeeStatus(str, Enum):
    """Employee employment status."""

    ACTIVE = "A"
    TERMINATED = "T"
    LEAVE = "L"
    RETIRED = "R"

    @classmethod
    def from_code(cls, code: str) -> "EmployeeStatus":
        """Convert UKG status code to enum."""
        code = code.upper() if code else ""
        for status in cls:
            if status.value == code:
                return status
        # Default to active if unknown
        return cls.ACTIVE

    @property
    def is_active(self) -> bool:
        """Check if status represents an active employee."""
        return self == EmployeeStatus.ACTIVE


class EmployeeType(str, Enum):
    """Employee type classification."""

    FULL_TIME = "FT"
    PART_TIME = "PT"
    CONTRACTOR = "C"
    TEMPORARY = "T"
    INTERN = "I"


@dataclass
class Address:
    """Physical address."""

    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"

    def is_complete(self) -> bool:
        """Check if address has minimum required fields."""
        return bool(self.line1 and self.city and self.state and self.zip_code)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "line1": self.line1,
            "line2": self.line2,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "country": self.country,
        }

    @classmethod
    def from_ukg(cls, data: Dict[str, Any]) -> "Address":
        """Create from UKG API response."""
        return cls(
            line1=data.get("address1", "") or data.get("line1", "") or "",
            line2=data.get("address2", "") or data.get("line2", "") or "",
            city=data.get("city", "") or "",
            state=data.get("state", "") or data.get("stateCode", "") or "",
            zip_code=data.get("zip", "") or data.get("postalCode", "") or "",
            country=data.get("country", "") or data.get("countryCode", "US") or "US",
        )


@dataclass
class Employee:
    """
    Employee domain model.

    Represents an employee from UKG Pro with all data relevant for
    BILL.com synchronization.

    Attributes:
        employee_id: UKG internal employee ID (UUID)
        employee_number: Human-readable employee number
        first_name: Employee's first name
        last_name: Employee's last name
        email: Primary work email address
        phone: Work phone number
        status: Employment status (Active, Terminated, etc.)
        hire_date: Original hire date
        termination_date: Termination date (if applicable)
        department: Department name or code
        job_title: Job title
        supervisor_email: Direct supervisor's email address
        supervisor_id: Direct supervisor's employee ID
        company_id: UKG company identifier
        address: Work or home address
        employee_type: Full-time, Part-time, etc.
        cost_center: Cost center code
        metadata: Additional UKG-specific data
    """

    # Required identifiers
    employee_id: str
    employee_number: str

    # Name
    first_name: str
    last_name: str

    # Contact
    email: str
    phone: str = ""

    # Status
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None

    # Organization
    department: str = ""
    job_title: str = ""
    supervisor_email: str = ""
    supervisor_id: str = ""
    supervisor_number: str = ""
    company_id: str = ""

    # Address
    address: Address = field(default_factory=Address)

    # Classification
    employee_type: Optional[EmployeeType] = None
    employee_type_code: str = ""  # UKG employeeTypeCode (PRD, FTC, HRC)
    pay_frequency: str = ""  # UKG payFrequency (Hourly/Salaried)
    cost_center: str = ""
    cost_center_description: str = ""
    direct_labor: bool = False

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate after initialization."""
        self._normalize()

    def _normalize(self) -> None:
        """Normalize field values."""
        # Normalize strings
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.email = (self.email or "").strip().lower()
        self.phone = self._normalize_phone(self.phone)

        # Ensure status is enum
        if isinstance(self.status, str):
            self.status = EmployeeStatus.from_code(self.status)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number to digits only."""
        if not phone:
            return ""
        digits = "".join(c for c in phone if c.isdigit())
        # US phone: keep last 10 digits
        if len(digits) > 10:
            digits = digits[-10:]
        return digits

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        """Check if employee is currently active."""
        return self.status.is_active

    @property
    def has_supervisor(self) -> bool:
        """Check if employee has a supervisor assigned."""
        return bool(self.supervisor_email or self.supervisor_id)

    def validate(self) -> List[str]:
        """
        Validate employee data.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.employee_id:
            errors.append("employee_id is required")

        if not self.employee_number:
            errors.append("employee_number is required")

        if not self.first_name:
            errors.append("first_name is required")

        if not self.last_name:
            errors.append("last_name is required")

        if not self.email:
            errors.append("email is required")
        elif not self._is_valid_email(self.email):
            errors.append(f"Invalid email format: {self.email}")

        if self.phone and len(self.phone) != 10:
            errors.append(f"Phone must be 10 digits, got {len(self.phone)}")

        if self.address.state and len(self.address.state) != 2:
            errors.append(f"State must be 2-letter code: {self.address.state}")

        return errors

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        return "@" in email and "." in email.split("@")[-1]

    def is_valid(self) -> bool:
        """Check if employee data is valid."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "employee_id": self.employee_id,
            "employee_number": self.employee_number,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "status": self.status.value,
            "is_active": self.is_active,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "termination_date": self.termination_date.isoformat() if self.termination_date else None,
            "department": self.department,
            "job_title": self.job_title,
            "supervisor_email": self.supervisor_email,
            "supervisor_id": self.supervisor_id,
            "supervisor_number": self.supervisor_number,
            "company_id": self.company_id,
            "address": self.address.to_dict(),
            "employee_type_code": self.employee_type_code,
            "pay_frequency": self.pay_frequency,
            "cost_center": self.cost_center,
            "cost_center_description": self.cost_center_description,
            "direct_labor": self.direct_labor,
        }

    @classmethod
    def from_ukg(cls, data: Dict[str, Any], person_data: Optional[Dict[str, Any]] = None) -> "Employee":
        """
        Create Employee from UKG API response.

        Args:
            data: Employment data from UKG
            person_data: Optional person-details data for additional info

        Returns:
            Employee instance
        """
        person = person_data or {}

        # Extract dates
        hire_date = None
        if data.get("originalHireDate"):
            try:
                hire_date = datetime.strptime(data["originalHireDate"][:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        termination_date = None
        if data.get("terminationDate"):
            try:
                termination_date = datetime.strptime(data["terminationDate"][:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        # Extract status
        status_code = data.get("employeeStatusCode", "") or data.get("statusCode", "A")

        # Extract supervisor info
        supervisor_email = ""
        supervisor_id = ""

        # Try various supervisor fields
        if data.get("supervisorEmailAddress"):
            supervisor_email = data["supervisorEmailAddress"]
        elif data.get("supervisor", {}).get("emailAddress"):
            supervisor_email = data["supervisor"]["emailAddress"]
        elif person.get("supervisorEmailAddress"):
            supervisor_email = person["supervisorEmailAddress"]

        if data.get("supervisorEmployeeId"):
            supervisor_id = data["supervisorEmployeeId"]
        elif data.get("supervisor", {}).get("employeeId"):
            supervisor_id = data["supervisor"]["employeeId"]

        supervisor_number = ""
        if data.get("supervisorEmployeeNumber"):
            supervisor_number = data["supervisorEmployeeNumber"]
        elif data.get("supervisor", {}).get("employeeNumber"):
            supervisor_number = data["supervisor"]["employeeNumber"]

        # Build address
        address_data = data.get("address", {}) or person.get("address", {}) or {}
        address = Address.from_ukg(address_data)

        return cls(
            employee_id=data.get("employeeId", "") or person.get("employeeId", ""),
            employee_number=data.get("employeeNumber", "") or person.get("employeeNumber", ""),
            first_name=person.get("firstName", "") or data.get("firstName", ""),
            last_name=person.get("lastName", "") or data.get("lastName", ""),
            email=person.get("emailAddress", "") or data.get("emailAddress", ""),
            phone=person.get("workPhone", "") or data.get("phoneNumber", ""),
            status=EmployeeStatus.from_code(status_code),
            hire_date=hire_date,
            termination_date=termination_date,
            department=data.get("departmentDescription", "") or data.get("department", ""),
            job_title=data.get("jobDescription", "") or data.get("jobTitle", ""),
            supervisor_email=supervisor_email,
            supervisor_id=supervisor_id,
            supervisor_number=supervisor_number,
            company_id=data.get("companyId", "") or data.get("coid", ""),
            address=address,
            employee_type_code=data.get("employeeTypeCode", "") or "",
            pay_frequency=data.get("payFrequency", "") or "",
            cost_center=data.get("costCenter", "") or data.get("costCenterCode", ""),
            cost_center_description=data.get("costCenterDescription", "") or data.get("primaryProjectDescription", ""),
            direct_labor=bool(data.get("directLabor") or data.get("isDirectLabor", False)),
            metadata={
                "ukg_data": data,
                "person_data": person_data,
            },
        )
