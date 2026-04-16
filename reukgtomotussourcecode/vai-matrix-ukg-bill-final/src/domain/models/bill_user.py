"""
BillUser domain model - Represents BILL.com Spend & Expense user.

This model represents a user in the BILL.com Spend & Expense system,
and provides conversion from Employee domain model.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.config.constants import DEFAULT_BILL_ROLE, VALID_BILL_ROLES


class BillRole(str, Enum):
    """BILL.com Spend & Expense user roles."""

    ADMIN = "ADMIN"
    AUDITOR = "AUDITOR"
    BOOKKEEPER = "BOOKKEEPER"
    MEMBER = "MEMBER"
    NO_ACCESS = "NO_ACCESS"

    @classmethod
    def from_string(cls, role: str) -> "BillRole":
        """Convert string to role enum."""
        role = (role or "").upper().strip()
        if role in VALID_BILL_ROLES:
            return cls(role)
        return cls.MEMBER  # Default

    @property
    def has_access(self) -> bool:
        """Check if role grants system access."""
        return self != BillRole.NO_ACCESS


@dataclass
class BillUser:
    """
    BILL.com Spend & Expense user.

    Represents a user in the BILL.com S&E system with all fields
    required for API operations.

    Attributes:
        id: BILL.com user UUID (assigned by BILL after creation)
        email: User's email address (unique identifier for lookup)
        first_name: First name
        last_name: Last name
        role: User role (ADMIN, AUDITOR, BOOKKEEPER, MEMBER, NO_ACCESS)
        phone: Phone number
        manager_email: Manager's email address (for UI import)
        external_id: External identifier (employee number)
        retired: Whether user is retired/inactive
        metadata: Additional BILL-specific data
    """

    # Required fields
    email: str
    first_name: str
    last_name: str

    # BILL-assigned ID (populated after creation)
    id: Optional[str] = None

    # Role and status
    role: BillRole = BillRole.MEMBER
    retired: bool = False

    # Contact
    phone: str = ""

    # Manager (for CSV import - not in API)
    manager_email: str = ""

    # External tracking
    external_id: str = ""  # Usually employee_number

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Cost center and budget assignment (from UKG)
    cost_center: str = ""
    cost_center_description: str = ""
    direct_labor: bool = False

    # Additional UKG fields for CSV export
    company: str = ""  # UKG companyID (CCHN)
    employee_type_code: str = ""  # UKG employeeTypeCode (PRD, FTC, HRC)
    pay_frequency: str = ""  # UKG payFrequency (Hourly/Salaried)

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize after initialization."""
        self._normalize()

    def _normalize(self) -> None:
        """Normalize field values."""
        self.email = (self.email or "").strip().lower()
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.phone = self._normalize_phone(self.phone)

        if isinstance(self.role, str):
            self.role = BillRole.from_string(self.role)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone to digits only."""
        if not phone:
            return ""
        return "".join(c for c in phone if c.isdigit())[-10:]

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        """Check if user is active (not retired and has access)."""
        return not self.retired and self.role.has_access

    @property
    def exists_in_bill(self) -> bool:
        """Check if user has been created in BILL (has ID)."""
        return self.id is not None

    def validate(self) -> List[str]:
        """
        Validate user data for BILL.com API.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.email:
            errors.append("email is required")
        elif "@" not in self.email:
            errors.append(f"Invalid email format: {self.email}")

        if not self.first_name:
            errors.append("first_name is required")

        if not self.last_name:
            errors.append("last_name is required")

        if self.role not in BillRole:
            errors.append(f"Invalid role: {self.role}")

        return errors

    def is_valid(self) -> bool:
        """Check if user data is valid."""
        return len(self.validate()) == 0

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert to BILL.com API payload for create/update.

        Returns:
            Dictionary suitable for POST/PATCH to BILL API
        """
        payload: Dict[str, Any] = {
            "email": self.email,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "role": self.role.value,
        }

        if self.phone:
            payload["phone"] = self.phone

        if self.external_id:
            payload["externalId"] = self.external_id

        return payload

    def to_csv_row(self) -> Dict[str, str]:
        """
        Convert to CSV row for BILL.com bulk import.

        The CSV import supports the manager field which is not
        available via API.

        Returns:
            Dictionary with CSV column headers as keys
        """
        # Format cost center as "CODE – Description"
        formatted_cost_center = ""
        if self.cost_center:
            if self.cost_center_description:
                formatted_cost_center = f"{self.cost_center} – {self.cost_center_description}"
            else:
                formatted_cost_center = self.cost_center

        # Determine sal value based on pay_frequency
        pay_freq_lower = (self.pay_frequency or "").lower()
        sal_value = "Salaried" if pay_freq_lower in ("salary", "salaried", "s") else "Hourly"

        return {
            "first name": self.first_name,
            "last name": self.last_name,
            "email address": self.email,
            "role": self.role.value.capitalize() if self.role != BillRole.NO_ACCESS else "No access",
            "manager": self.manager_email,
            "cost center": formatted_cost_center,
            "budget count": "Direct" if self.direct_labor else "Indirect",
            "company": self.company,  # CCHN
            "employee type": self.employee_type_code,  # PRD, FTC, HRC
            "sal": sal_value,  # Salaried or Hourly
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "role": self.role.value,
            "phone": self.phone,
            "manager_email": self.manager_email,
            "external_id": self.external_id,
            "retired": self.retired,
            "is_active": self.is_active,
            "cost_center": self.cost_center,
            "cost_center_description": self.cost_center_description,
            "direct_labor": self.direct_labor,
            "company": self.company,
            "employee_type_code": self.employee_type_code,
            "pay_frequency": self.pay_frequency,
        }

    def diff(self, other: "BillUser") -> Dict[str, tuple]:
        """
        Compare with another BillUser and return differences.

        Args:
            other: Another BillUser to compare with

        Returns:
            Dict of field_name -> (self_value, other_value) for differing fields
        """
        diffs = {}
        compare_fields = ["email", "first_name", "last_name", "role", "phone"]

        for field_name in compare_fields:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)

            # Handle enum comparison
            if isinstance(self_val, Enum):
                self_val = self_val.value
            if isinstance(other_val, Enum):
                other_val = other_val.value

            if self_val != other_val:
                diffs[field_name] = (self_val, other_val)

        return diffs

    def needs_update(self, existing: "BillUser") -> bool:
        """
        Check if this user needs to be updated in BILL.

        Args:
            existing: The existing user data from BILL

        Returns:
            True if there are differences that require an update
        """
        return len(self.diff(existing)) > 0

    @classmethod
    def from_employee(
        cls,
        employee: "Employee",  # Forward reference
        role: Optional[BillRole] = None,
        manager_email: Optional[str] = None,
    ) -> "BillUser":
        """
        Create BillUser from Employee domain model.

        Args:
            employee: Source Employee model
            role: Override role (defaults to MEMBER)
            manager_email: Override manager email

        Returns:
            BillUser instance
        """
        # Import here to avoid circular dependency
        from src.domain.models.employee import Employee

        return cls(
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            phone=employee.phone,
            role=role or BillRole.MEMBER,
            retired=not employee.is_active,
            manager_email=manager_email or employee.supervisor_email,
            external_id=employee.employee_number,
            cost_center=employee.cost_center,
            cost_center_description=employee.cost_center_description,
            direct_labor=employee.direct_labor,
            company=employee.company_id,
            employee_type_code=employee.employee_type_code,
            pay_frequency=employee.pay_frequency,
            metadata={"source_employee_id": employee.employee_id},
        )

    @classmethod
    def from_bill_api(cls, data: Dict[str, Any]) -> "BillUser":
        """
        Create BillUser from BILL.com API response.

        Args:
            data: API response data

        Returns:
            BillUser instance
        """
        return cls(
            id=data.get("id") or data.get("uuid"),
            email=data.get("email", ""),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            role=BillRole.from_string(data.get("role", "")),
            phone=data.get("phone", ""),
            retired=data.get("retired", False),
            external_id=data.get("externalId", ""),
            metadata={"bill_data": data},
        )
