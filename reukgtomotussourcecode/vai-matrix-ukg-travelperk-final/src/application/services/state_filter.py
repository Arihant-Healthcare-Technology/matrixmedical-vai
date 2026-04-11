"""
State filtering service.

Handles filtering employees by US state codes.
"""

import logging
import time
from typing import Any, Dict, Optional, Set

from ...infrastructure.adapters.ukg import UKGClient


logger = logging.getLogger(__name__)


class StateFilterService:
    """Service for filtering employees by state."""

    def __init__(
        self,
        ukg_client: UKGClient,
        debug: bool = False,
    ):
        """
        Initialize state filter service.

        Args:
            ukg_client: UKG API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.debug = debug
        self._person_cache: Dict[str, str] = {}

    def fetch_person_state(
        self,
        employee_id: str,
        max_retries: int = 5,
    ) -> str:
        """
        Fetch person's state with caching and retry logic.

        Args:
            employee_id: Employee ID
            max_retries: Maximum retry attempts

        Returns:
            State code (uppercase) or empty string
        """
        # Check cache first
        if employee_id in self._person_cache:
            return self._person_cache[employee_id]

        delay = 0.2
        for attempt in range(1, max_retries + 1):
            try:
                person = self.ukg_client.get_person_details(employee_id)
                state = (person.get("addressState") or "").strip().upper()
                self._person_cache[employee_id] = state
                return state
            except Exception as e:
                if attempt < max_retries:
                    if self.debug:
                        logger.debug(
                            f"Retry {attempt}/{max_retries} for state lookup "
                            f"employee_id={employee_id}: {e}"
                        )
                    time.sleep(delay)
                    delay = min(delay * 2, 3.2)  # Exponential backoff
                else:
                    logger.warning(
                        f"Failed to fetch state for employee_id={employee_id}: {e}"
                    )
                    self._person_cache[employee_id] = ""
                    return ""

        return ""

    def should_include_employee(
        self,
        employee: Dict[str, Any],
        states_filter: Optional[Set[str]],
    ) -> bool:
        """
        Check if employee should be included based on state filter.

        Args:
            employee: Employee record
            states_filter: Set of allowed state codes (None = no filter)

        Returns:
            True if employee should be included
        """
        if not states_filter:
            return True

        emp_id = (employee.get("employeeID") or "").strip()
        if not emp_id:
            return False

        state = self.fetch_person_state(emp_id)
        return state in states_filter

    def filter_employees(
        self,
        employees: list,
        states_filter: Optional[Set[str]],
    ) -> list:
        """
        Filter employees by state.

        Args:
            employees: List of employee records
            states_filter: Set of allowed state codes

        Returns:
            Filtered list of employees
        """
        if not states_filter:
            return employees

        filtered = []
        for emp in employees:
            if self.should_include_employee(emp, states_filter):
                filtered.append(emp)

        logger.info(
            f"State filter: {len(employees)} -> {len(filtered)} employees "
            f"(states={states_filter})"
        )
        return filtered

    def clear_cache(self) -> None:
        """Clear the person state cache."""
        self._person_cache.clear()

    @property
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self._person_cache)
