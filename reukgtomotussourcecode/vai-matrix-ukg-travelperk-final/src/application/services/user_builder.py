"""User builder service."""

import json
from typing import Any, Dict

from ...domain.models import TravelPerkUser
from ...domain.exceptions import EmployeeNotFoundError, UserValidationError
from ...infrastructure.adapters.ukg import UKGClient


class UserBuilderService:
    """Service for building TravelPerk users from UKG data."""

    def __init__(self, ukg_client: UKGClient, debug: bool = False):
        """Initialize user builder service.

        Args:
            ukg_client: UKG API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.debug = debug

    def build_user(
        self,
        employee_number: str,
        company_id: str,
    ) -> TravelPerkUser:
        """Build TravelPerk user from UKG data.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            TravelPerkUser instance

        Raises:
            EmployeeNotFoundError: If employee not found in UKG
            UserValidationError: If built user fails validation
        """
        # Get employment details
        employment = self.ukg_client.get_employment_details(employee_number, company_id)
        if self.debug:
            print("[DEBUG] employee-employment-details:")
            print(json.dumps(employment, indent=2))

        if not employment:
            raise EmployeeNotFoundError(employee_number, company_id)

        # Get employee ID for person details
        employee_id = employment.get("employeeID")
        if not employee_id:
            raise EmployeeNotFoundError(
                employee_number,
                company_id,
            )

        # Get person details
        person = self.ukg_client.get_person_details(employee_id)
        if self.debug:
            print("[DEBUG] person-details:")
            print(json.dumps(person, indent=2))

        # Validate email exists
        email = (person.get("emailAddress") or "").strip()
        if not email:
            raise UserValidationError(
                ["No email address found"],
                external_id=employee_number,
            )

        # Get cost center info by matching primaryProjectCode with glSegment from org-levels
        primary_project_code = (employment.get("primaryProjectCode") or "").strip()
        cost_center_info = self.ukg_client.get_org_level_by_gl_segment(primary_project_code)

        # Build user from UKG data
        user = TravelPerkUser.from_ukg_data(
            employment,
            person,
            cost_center_info=cost_center_info,
        )

        # Validate
        errors = user.validate()
        if errors:
            raise UserValidationError(errors, external_id=employee_number)

        if self.debug:
            print("[DEBUG] TravelPerk user payload:")
            print(json.dumps(user.to_api_payload(), indent=2))

        return user

    def build_user_payload(
        self,
        employee_number: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Build TravelPerk user payload from UKG data.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            SCIM API payload dictionary
        """
        user = self.build_user(employee_number, company_id)
        return user.to_api_payload()
