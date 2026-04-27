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


def get_travelperk_scim_base() -> str:
    """Get TravelPerk SCIM base URL from environment."""
    import os
    api_base = os.environ.get("TRAVELPERK_API_BASE", "https://app.travelperk.com")
    return f"{api_base}/api/v2/scim/Users"


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

    # Core SCIM fields
    title: Optional[str] = None  # jobTitle from UKG
    phone_number: Optional[str] = None  # phoneNumber with country code
    preferred_language: Optional[str] = None  # languageCode from UKG
    locale: Optional[str] = None  # languageCode from UKG

    # Enterprise extension
    cost_center: Optional[str] = None  # primaryProjectCode from UKG
    manager_id: Optional[str] = None  # TravelPerk ID of supervisor
    manager_display_name: Optional[str] = None  # Supervisor's full name from UKG

    # TravelPerk extension
    gender: Optional[str] = None  # "M" or "F"
    date_of_birth: Optional[str] = None  # YYYY-MM-DD format
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

        # Add core SCIM fields
        if self.title:
            payload["title"] = self.title

        if self.phone_number:
            payload["phoneNumbers"] = [{"value": self.phone_number, "type": "work"}]

        if self.preferred_language:
            payload["preferredLanguage"] = self.preferred_language

        if self.locale:
            payload["locale"] = self.locale

        # Add enterprise extension fields
        if self.cost_center:
            payload[SCIM_ENTERPRISE_SCHEMA]["costCenter"] = self.cost_center

        if self.manager_id:
            manager_obj: Dict[str, Any] = {
                "value": self.manager_id,
                "$ref": f"{get_travelperk_scim_base()}/{self.manager_id}",
            }
            if self.manager_display_name:
                manager_obj["displayName"] = self.manager_display_name
            payload[SCIM_ENTERPRISE_SCHEMA]["manager"] = manager_obj

        # Add TravelPerk extension fields
        # uniqueId - employee identifier/number
        payload[SCIM_TRAVELPERK_SCHEMA]["uniqueId"] = self.external_id

        if self.gender:
            payload[SCIM_TRAVELPERK_SCHEMA]["gender"] = self.gender

        if self.date_of_birth:
            payload[SCIM_TRAVELPERK_SCHEMA]["dateOfBirth"] = self.date_of_birth

        if self.line_manager_email:
            payload[SCIM_TRAVELPERK_SCHEMA]["lineManagerEmail"] = self.line_manager_email

        # Remove empty extension objects
        if not payload[SCIM_ENTERPRISE_SCHEMA]:
            del payload[SCIM_ENTERPRISE_SCHEMA]
        if not payload[SCIM_TRAVELPERK_SCHEMA]:
            del payload[SCIM_TRAVELPERK_SCHEMA]

        return payload

    def to_patch_operations(self, include_manager: bool = True) -> List[Dict[str, Any]]:
        """Generate SCIM PATCH operations for update.

        Args:
            include_manager: Whether to include manager update

        Returns:
            List of SCIM PATCH operations
        """
        operations = []

        # Update userName (email)
        operations.append({
            "op": "replace",
            "path": "userName",
            "value": self.user_name
        })

        # Update externalId
        operations.append({
            "op": "replace",
            "path": "externalId",
            "value": self.external_id
        })

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

        # Update emails
        operations.append({
            "op": "replace",
            "path": "emails",
            "value": [UserEmail(value=self.user_name).to_dict()]
        })

        # Update enterprise extension (costCenter and manager) as nested object
        enterprise_ext: Dict[str, Any] = {}
        if self.cost_center:
            enterprise_ext["costCenter"] = self.cost_center
        if include_manager and self.manager_id:
            manager_obj: Dict[str, Any] = {
                "value": self.manager_id,
                "$ref": f"{get_travelperk_scim_base()}/{self.manager_id}",
            }
            if self.manager_display_name:
                manager_obj["displayName"] = self.manager_display_name
            enterprise_ext["manager"] = manager_obj

        if enterprise_ext:
            operations.append({
                "op": "replace",
                "path": SCIM_ENTERPRISE_SCHEMA,
                "value": enterprise_ext
            })

        # Update core SCIM fields
        if self.title:
            operations.append({
                "op": "replace",
                "path": "title",
                "value": self.title
            })

        if self.phone_number:
            operations.append({
                "op": "replace",
                "path": "phoneNumbers",
                "value": [{"value": self.phone_number, "type": "work"}]
            })

        if self.preferred_language:
            operations.append({
                "op": "replace",
                "path": "preferredLanguage",
                "value": self.preferred_language
            })

        if self.locale:
            operations.append({
                "op": "replace",
                "path": "locale",
                "value": self.locale
            })

        # Update TravelPerk extension fields as nested object
        travelperk_ext: Dict[str, Any] = {}
        # uniqueId - employee identifier/number (always include)
        travelperk_ext["uniqueId"] = self.external_id
        if self.gender:
            travelperk_ext["gender"] = self.gender
        if self.date_of_birth:
            travelperk_ext["dateOfBirth"] = self.date_of_birth
        if self.line_manager_email:
            travelperk_ext["lineManagerEmail"] = self.line_manager_email

        operations.append({
            "op": "replace",
            "path": SCIM_TRAVELPERK_SCHEMA,
            "value": travelperk_ext
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
        cost_center_info: Optional[Dict[str, str]] = None,
    ) -> "TravelPerkUser":
        """Create TravelPerkUser from UKG API data.

        Args:
            employment: employee-employment-details response
            person: person-details response
            cost_center_info: Dict with glSegment, code, description from org-levels API

        Returns:
            TravelPerkUser instance
        """
        # Extract employee number
        external_id = str(employment.get("employeeNumber") or "").strip()

        # Extract email
        email = (person.get("emailAddress") or "").strip()

        # Extract name
        first_name = (person.get("firstName") or "").strip()
        last_name = (person.get("lastName") or "").strip()
        name = UserName(given_name=first_name, family_name=last_name)

        # Extract cost center - match primaryProjectCode with glSegment from org-levels
        primary_project_code = (employment.get("primaryProjectCode") or "").strip()

        # Format: "glSegment - code - description" (e.g., "27 - 53203 - Account Management")
        # Fall back to just primaryProjectCode if no match found
        if cost_center_info:
            cost_center = f"{cost_center_info['glSegment']} - {cost_center_info['code']} - {cost_center_info['description']}"
        elif primary_project_code:
            cost_center = primary_project_code
        else:
            cost_center = ""

        # Determine active status
        termination_date = employment.get("terminationDate")
        status_code = str(employment.get("employeeStatusCode") or "").strip().upper()

        if status_code:
            status = EmploymentStatus.from_code(status_code)
            is_active = status.is_active
        else:
            is_active = not bool(termination_date)

        # Extract job title
        title = (employment.get("jobTitle") or "").strip() or None

        # Extract phone number with country code
        phone_raw = (person.get("phoneNumber") or "").strip()
        country_code = (person.get("countryCode") or "").strip() or "1"  # Default to US
        if phone_raw:
            # Format: +{countryCode}{phoneNumber} (no space)
            phone_number = f"+{country_code}{phone_raw}"
        else:
            phone_number = None

        # Extract language (for preferredLanguage and locale)
        language_code = (person.get("languageCode") or "").strip() or None

        # Extract gender (if available)
        gender_raw = (person.get("gender") or "").strip().upper()
        if gender_raw in ["M", "MALE"]:
            gender = "M"
        elif gender_raw in ["F", "FEMALE"]:
            gender = "F"
        else:
            gender = None

        # Extract date of birth (if available)
        date_of_birth = (person.get("birthDate") or "").strip() or None

        return cls(
            external_id=external_id,
            user_name=email,
            name=name,
            active=is_active,
            title=title,
            phone_number=phone_number,
            preferred_language=language_code,
            locale=language_code,
            cost_center=cost_center if cost_center else None,
            gender=gender,
            date_of_birth=date_of_birth,
        )
