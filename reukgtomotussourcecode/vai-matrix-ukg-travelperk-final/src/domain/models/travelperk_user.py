"""TravelPerk SCIM user domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .employment_status import EmploymentStatus


# SCIM Schema URIs
SCIM_CORE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_ENTERPRISE_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
SCIM_TRAVELPERK_SCHEMA = "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


@dataclass
class UserName:
    """User name component."""

    given_name: str
    family_name: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to SCIM name format."""
        return {
            "givenName": self.given_name,
            "familyName": self.family_name,
        }


@dataclass
class UserEmail:
    """User email component."""

    value: str
    email_type: str = "work"
    primary: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to SCIM email format."""
        return {
            "value": self.value,
            "type": self.email_type,
            "primary": self.primary,
        }


@dataclass
class TravelPerkUser:
    """TravelPerk SCIM user entity."""

    # Required fields
    external_id: str  # employeeNumber from UKG
    user_name: str  # email address
    name: UserName

    # Status
    active: bool = True

    # Enterprise extension
    cost_center: Optional[str] = None  # primaryProjectCode from UKG
    manager_id: Optional[str] = None  # TravelPerk ID of supervisor

    # TravelPerk extension
    line_manager_email: Optional[str] = None

    # Internal tracking
    travelperk_id: Optional[str] = None  # TravelPerk's internal ID

    def validate(self) -> List[str]:
        """Validate user data.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.external_id:
            errors.append("external_id (employeeNumber) is required")

        if not self.user_name:
            errors.append("user_name (email) is required")
        elif "@" not in self.user_name:
            errors.append(f"user_name must be valid email: {self.user_name}")

        if not self.name.given_name:
            errors.append("name.given_name (firstName) is required")

        if not self.name.family_name:
            errors.append("name.family_name (lastName) is required")

        return errors

    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TravelPerk SCIM API payload for POST.

        Returns:
            Dictionary ready for SCIM API request
        """
        payload: Dict[str, Any] = {
            "schemas": [
                SCIM_CORE_SCHEMA,
                SCIM_ENTERPRISE_SCHEMA,
                SCIM_TRAVELPERK_SCHEMA,
            ],
            "userName": self.user_name,
            "externalId": self.external_id,
            "name": self.name.to_dict(),
            "active": self.active,
            "emails": [
                UserEmail(value=self.user_name).to_dict()
            ],
            SCIM_ENTERPRISE_SCHEMA: {},
            SCIM_TRAVELPERK_SCHEMA: {},
        }

        # Add enterprise extension fields
        if self.cost_center:
            payload[SCIM_ENTERPRISE_SCHEMA]["costCenter"] = self.cost_center

        if self.manager_id:
            payload[SCIM_ENTERPRISE_SCHEMA]["manager"] = {"value": self.manager_id}

        # Add TravelPerk extension fields
        if self.line_manager_email:
            payload[SCIM_TRAVELPERK_SCHEMA]["lineManagerEmail"] = self.line_manager_email

        return payload

    def to_patch_operations(self, include_manager: bool = True) -> List[Dict[str, Any]]:
        """Generate SCIM PATCH operations for update.

        Args:
            include_manager: Whether to include manager update

        Returns:
            List of SCIM PATCH operations
        """
        operations = []

        # Update active status
        operations.append({
            "op": "replace",
            "path": "active",
            "value": self.active
        })

        # Update name
        operations.append({
            "op": "replace",
            "path": "name.givenName",
            "value": self.name.given_name
        })
        operations.append({
            "op": "replace",
            "path": "name.familyName",
            "value": self.name.family_name
        })

        # Update costCenter
        if self.cost_center:
            operations.append({
                "op": "replace",
                "path": f"{SCIM_ENTERPRISE_SCHEMA}:costCenter",
                "value": self.cost_center
            })

        # Update manager
        if include_manager and self.manager_id:
            operations.append({
                "op": "replace",
                "path": f"{SCIM_ENTERPRISE_SCHEMA}:manager",
                "value": {"value": self.manager_id}
            })

        return operations

    def to_patch_payload(self, include_manager: bool = True) -> Dict[str, Any]:
        """Generate full SCIM PATCH payload.

        Args:
            include_manager: Whether to include manager update

        Returns:
            SCIM PATCH payload dictionary
        """
        return {
            "schemas": [SCIM_PATCH_SCHEMA],
            "Operations": self.to_patch_operations(include_manager)
        }

    @classmethod
    def from_ukg_data(
        cls,
        employment: Dict[str, Any],
        person: Dict[str, Any],
    ) -> "TravelPerkUser":
        """Create TravelPerkUser from UKG API data.

        Args:
            employment: employee-employment-details response
            person: person-details response

        Returns:
            TravelPerkUser instance
        """
        # Extract employee number
        external_id = str(employment.get("employeeNumber", "")).strip()

        # Extract email
        email = person.get("emailAddress", "").strip()

        # Extract name
        first_name = person.get("firstName", "")
        last_name = person.get("lastName", "")
        name = UserName(given_name=first_name, family_name=last_name)

        # Extract cost center (project code)
        cost_center = employment.get("primaryProjectCode", "")

        # Determine active status
        termination_date = employment.get("terminationDate")
        status_code = str(employment.get("employeeStatusCode", "")).strip().upper()

        if status_code:
            status = EmploymentStatus.from_code(status_code)
            is_active = status.is_active
        else:
            is_active = not bool(termination_date)

        return cls(
            external_id=external_id,
            user_name=email,
            name=name,
            active=is_active,
            cost_center=cost_center if cost_center else None,
        )
