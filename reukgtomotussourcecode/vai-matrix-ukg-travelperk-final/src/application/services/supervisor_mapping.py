"""
Supervisor mapping service.

Handles the mapping of employee numbers to supervisor employee numbers
and TravelPerk IDs for the two-phase sync process.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...infrastructure.adapters.ukg import UKGClient
from ...infrastructure.adapters.travelperk import TravelPerkClient


logger = logging.getLogger(__name__)


@dataclass
class SupervisorInfo:
    """Supervisor information from UKG."""

    employee_number: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

    @property
    def full_name(self) -> Optional[str]:
        """Get full name if available."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or None


class SupervisorMappingService:
    """Service for managing supervisor relationships."""

    def __init__(
        self,
        ukg_client: UKGClient,
        travelperk_client: TravelPerkClient,
        debug: bool = False,
    ):
        """
        Initialize supervisor mapping service.

        Args:
            ukg_client: UKG API client
            travelperk_client: TravelPerk API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.travelperk_client = travelperk_client
        self.debug = debug

    def build_supervisor_mapping(
        self,
        supervisor_details: List[Dict[str, Any]],
    ) -> Dict[str, Optional[SupervisorInfo]]:
        """
        Build employeeNumber -> SupervisorInfo mapping.

        Args:
            supervisor_details: List of supervisor detail records from UKG

        Returns:
            Mapping of employee number to SupervisorInfo (None if no supervisor)
        """
        mapping: Dict[str, Optional[SupervisorInfo]] = {}

        for detail in supervisor_details:
            emp_number = str(detail.get("employeeNumber", "")).strip()
            if not emp_number:
                continue

            supervisor_emp_number = detail.get("supervisorEmployeeNumber")
            if supervisor_emp_number:
                supervisor_info = SupervisorInfo(
                    employee_number=str(supervisor_emp_number).strip(),
                    first_name=detail.get("supervisorFirstName", "").strip() or None,
                    last_name=detail.get("supervisorLastName", "").strip() or None,
                    email=detail.get("supervisorEmail", "").strip() or None,
                )
                mapping[emp_number] = supervisor_info

                logger.info(
                    f"Supervisor for {emp_number}: {supervisor_info.full_name or 'N/A'} "
                    f"(email: {supervisor_info.email or 'N/A'})"
                )
            else:
                mapping[emp_number] = None

        logger.info(
            f"Built supervisor mapping: {len(mapping)} employees, "
            f"{sum(1 for v in mapping.values() if v)} with supervisors"
        )
        return mapping

    def fetch_supervisor_mapping(self) -> Dict[str, Optional[SupervisorInfo]]:
        """
        Fetch and build supervisor mapping from UKG.

        Returns:
            Mapping of employee number to SupervisorInfo (None if no supervisor)
        """
        logger.info("Fetching supervisor details from UKG...")
        supervisor_details = self.ukg_client.get_all_supervisor_details()
        return self.build_supervisor_mapping(supervisor_details)

    def split_by_supervisor_status(
        self,
        supervisor_mapping: Dict[str, Optional[SupervisorInfo]],
    ) -> tuple:
        """
        Split employees into those with and without supervisors.

        Args:
            supervisor_mapping: Employee to SupervisorInfo mapping

        Returns:
            Tuple of (employees_without_supervisor, employees_with_supervisor)
        """
        without_supervisor = [
            emp for emp, sup in supervisor_mapping.items() if sup is None
        ]
        with_supervisor = [
            emp for emp, sup in supervisor_mapping.items() if sup is not None
        ]

        logger.info(f"Phase 1: {len(without_supervisor)} users without supervisor")
        logger.info(f"Phase 2: {len(with_supervisor)} users with supervisor")

        return without_supervisor, with_supervisor

    def resolve_supervisor_id(
        self,
        supervisor_emp_number: str,
        employee_to_travelperk_id: Dict[str, str],
    ) -> Optional[str]:
        """
        Resolve supervisor's TravelPerk ID.

        First checks local mapping, then queries TravelPerk API.

        Args:
            supervisor_emp_number: Supervisor's employee number
            employee_to_travelperk_id: Existing mapping

        Returns:
            TravelPerk ID or None if not found
        """
        # Check local mapping first
        supervisor_id = employee_to_travelperk_id.get(supervisor_emp_number)
        if supervisor_id:
            return supervisor_id

        # Try to find in TravelPerk
        if self.debug:
            logger.debug(f"Supervisor {supervisor_emp_number} not in local mapping")

        sup_user = self.travelperk_client.get_user_by_external_id(supervisor_emp_number)
        if sup_user:
            supervisor_id = sup_user.get("id")
            if supervisor_id:
                # Update local mapping
                employee_to_travelperk_id[supervisor_emp_number] = supervisor_id
                logger.info(
                    f"Supervisor resolved: employeeNumber={supervisor_emp_number} -> TravelPerk id={supervisor_id}"
                )
                return supervisor_id

        # Supervisor not found - log warning
        logger.warning(
            f"Supervisor NOT FOUND: employeeNumber={supervisor_emp_number} - "
            f"not in local mapping and not found in TravelPerk"
        )
        return None
