"""
Motus Driver domain model.

Represents a driver in the Motus mileage reimbursement system.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .employment_status import EmploymentStatus
from .program import ProgramType


@dataclass
class CustomVariable:
    """Custom variable for Motus driver payload."""

    name: str
    value: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for API payload."""
        return {"name": self.name, "value": self.value}


@dataclass
class MotusDriver:
    """
    Motus driver domain model.

    Represents a driver that can be synced to the Motus system.

    Attributes:
        client_employee_id1: Primary employee identifier (employeeNumber)
        program_id: Motus program ID (FAVR or CPM)
        first_name: Driver first name
        last_name: Driver last name
        email: Driver email address
        address1: Street address line 1
        address2: Street address line 2
        city: City
        state_province: State/Province code
        country: Country code
        postal_code: Postal/ZIP code
        phone: Primary phone number
        alternate_phone: Alternate phone number
        start_date: Employment start date (YYYY-MM-DD)
        end_date: Employment end date (YYYY-MM-DD)
        leave_start_date: Leave start date (YYYY-MM-DD)
        leave_end_date: Leave end date (YYYY-MM-DD)
        annual_business_miles: Estimated annual business miles
        commute_deduction_type: Commute deduction type
        commute_deduction_cap: Commute deduction cap
        custom_variables: List of custom variables
        client_employee_id2: Secondary employee identifier
    """

    # Required fields
    client_employee_id1: str
    program_id: int
    first_name: str
    last_name: str
    email: str

    # Address
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

    # Contact
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None

    # Dates (YYYY-MM-DD format per Motus API spec)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    leave_start_date: Optional[str] = None
    leave_end_date: Optional[str] = None

    # Mileage
    annual_business_miles: int = 0
    commute_deduction_type: Optional[str] = None
    commute_deduction_cap: Optional[int] = None

    # Custom variables
    custom_variables: List[CustomVariable] = field(default_factory=list)

    # Secondary identifier
    client_employee_id2: Optional[str] = None

    def __post_init__(self) -> None:
        """Normalize fields after initialization."""
        self._normalize()

    def _normalize(self) -> None:
        """Normalize field values."""
        self.client_employee_id1 = (self.client_employee_id1 or "").strip()
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.email = (self.email or "").strip().lower()

        if self.phone:
            self.phone = self._normalize_phone(self.phone)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone to XXX-XXX-XXXX format."""
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
        return phone

    @staticmethod
    def _to_iso_date(date_str: Optional[str]) -> str:
        """Convert date to YYYY-MM-DD format as required by Motus API."""
        if not date_str:
            return ""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                return date_str
        return dt.strftime("%Y-%m-%d")

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def program_type(self) -> Optional[ProgramType]:
        """Get program type enum."""
        for pt in ProgramType:
            if pt.value == self.program_id:
                return pt
        return None

    def validate(self) -> List[str]:
        """
        Validate driver data per Motus API specification.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Required fields per Motus API spec (driverapi.yaml)
        if not self.client_employee_id1:
            errors.append("client_employee_id1 is required")

        if not self.program_id:
            errors.append("program_id is required")

        if not self.first_name:
            errors.append("first_name is required")

        if not self.last_name:
            errors.append("last_name is required")

        if not self.email:
            errors.append("email is required")
        elif "@" not in self.email:
            errors.append(f"Invalid email format: {self.email}")

        # Additional required fields per API spec
        if not self.address1:
            errors.append("address1 is required")

        if not self.city:
            errors.append("city is required")

        if not self.state_province:
            errors.append("stateProvince is required")

        if not self.postal_code:
            errors.append("postalCode is required")

        if not self.start_date:
            errors.append("startDate is required")

        return errors

    def is_valid(self) -> bool:
        """Check if driver data is valid."""
        return len(self.validate()) == 0

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert to Motus API payload format.

        Returns:
            Dictionary suitable for POST/PUT to Motus API
        """
        payload: Dict[str, Any] = {
            "clientEmployeeId1": self.client_employee_id1,
            "clientEmployeeId2": self.client_employee_id2,
            "programId": self.program_id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "stateProvince": self.state_province,
            "country": self.country,
            "postalCode": self.postal_code,
            "email": self.email,
            "phone": self.phone,
            "alternatePhone": self.alternate_phone or "",
            "startDate": self.start_date,
            "endDate": self.end_date,
            "leaveStartDate": self.leave_start_date,
            "leaveEndDate": self.leave_end_date,
            "annualBusinessMiles": self.annual_business_miles,
            "commuteDeductionType": self.commute_deduction_type,
            "commuteDeductionCap": self.commute_deduction_cap,
            "customVariables": [cv.to_dict() for cv in self.custom_variables],
        }

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "client_employee_id1": self.client_employee_id1,
            "client_employee_id2": self.client_employee_id2,
            "program_id": self.program_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "state_province": self.state_province,
            "country": self.country,
            "postal_code": self.postal_code,
            "phone": self.phone,
            "alternate_phone": self.alternate_phone,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "leave_start_date": self.leave_start_date,
            "leave_end_date": self.leave_end_date,
            "annual_business_miles": self.annual_business_miles,
            "commute_deduction_type": self.commute_deduction_type,
            "commute_deduction_cap": self.commute_deduction_cap,
            "custom_variables": [cv.to_dict() for cv in self.custom_variables],
        }

    @classmethod
    def from_ukg_data(
        cls,
        employee_number: str,
        program_id: int,
        person: Dict[str, Any],
        employment_details: Dict[str, Any],
        supervisor_name: str = "",
        location: Optional[Dict[str, Any]] = None,
        project_code: str = "",
        project_label: str = "",
        derived_status: str = "Active",
    ) -> "MotusDriver":
        """
        Create MotusDriver from UKG data sources.

        Args:
            employee_number: UKG employee number
            program_id: Motus program ID
            person: UKG person details
            employment_details: UKG employment details
            supervisor_name: Supervisor full name
            location: UKG location details
            project_code: Primary project code
            project_label: Primary project description
            derived_status: Derived employment status

        Returns:
            MotusDriver instance
        """
        location = location or {}

        # Build custom variables
        custom_variables = [
            # Project
            CustomVariable(name="Project Code", value=project_code),
            CustomVariable(name="Project", value=project_label),

            # Role
            CustomVariable(
                name="Job Code",
                value=str(employment_details.get("primaryJobCode", "") or "")
            ),
            CustomVariable(
                name="Job",
                value=str(employment_details.get("jobDescription", "") or "")
            ),

            # Location
            CustomVariable(
                name="Location Code",
                value=str(employment_details.get("primaryWorkLocationCode", "") or "")
            ),
            CustomVariable(
                name="Location",
                value=str(location.get("description", "") or "")
            ),

            # Organizational structure
            CustomVariable(
                name="Org Level 1 Code",
                value=str(employment_details.get("orgLevel1Code", "") or "")
            ),
            CustomVariable(
                name="Org Level 2 Code",
                value=str(employment_details.get("orgLevel2Code", "") or "")
            ),
            CustomVariable(
                name="Org Level 3 Code",
                value=str(employment_details.get("orgLevel3Code", "") or "")
            ),
            CustomVariable(
                name="Org Level 4 Code",
                value=str(employment_details.get("orgLevel4Code", "") or "")
            ),

            # Employment
            CustomVariable(
                name="Full/Part Time Code",
                value=str(employment_details.get("fullTimeOrPartTimeCode", "") or "")
            ),
            CustomVariable(
                name="Employment Type Code",
                value=str(employment_details.get("employeeTypeCode", "") or "")
            ),
            CustomVariable(
                name="Employment Status Code",
                value=str(employment_details.get("employeeStatusCode", "") or "")
            ),

            # Important dates
            CustomVariable(
                name="Last Hire",
                value=cls._to_iso_date(employment_details.get("lastHireDate"))
            ),
            CustomVariable(
                name="Termination Date",
                value=cls._to_iso_date(employment_details.get("dateOfTermination"))
            ),

            # Manager/supervisor
            CustomVariable(name="Manager Name", value=supervisor_name),

            # Derived status
            CustomVariable(name="Derived Status", value=derived_status),
        ]

        return cls(
            client_employee_id1=employee_number,
            program_id=program_id,
            first_name=person.get("firstName", ""),
            last_name=person.get("lastName", ""),
            email=person.get("emailAddress", ""),
            address1=person.get("addressLine1"),
            address2=person.get("addressLine2"),
            city=person.get("addressCity"),
            state_province=person.get("addressState"),
            country=person.get("addressCountry"),
            postal_code=person.get("addressZipCode"),
            phone=person.get("homePhone", ""),
            alternate_phone=person.get("mobilePhone") or employment_details.get("workPhoneNumber") or "",
            start_date=cls._to_iso_date(employment_details.get("originalHireDate")),
            end_date=cls._to_iso_date(employment_details.get("dateOfTermination")),
            leave_start_date=cls._to_iso_date(employment_details.get("employeeStatusStartDate")),
            leave_end_date=cls._to_iso_date(employment_details.get("employeeStatusExpectedEndDate")),
            custom_variables=custom_variables,
        )
