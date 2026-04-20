"""
BILL.com v2 API Department client.

This module provides the v2 API client for fetching departments.
Used to map cost center prefixes to budget/department names.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from src.infrastructure.config.constants import (
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class DepartmentClient:
    """
    BILL.com v2 API Department client.

    Fetches departments from the Bill.com v2 API to enable
    cost center to budget/department mapping.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        """
        Initialize department client.

        Args:
            api_base: Bill.com v2 API base URL (e.g., https://api.bill.com/api/v2)
            api_token: Bill.com API token
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.api_base = api_base.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries
        self._departments_cache: Optional[List[Dict[str, Any]]] = None

    def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Make a POST request to Bill.com v2 API.

        Args:
            endpoint: API endpoint (e.g., /List/Department.json)
            data: Request data

        Returns:
            API response data
        """
        url = f"{self.api_base}{endpoint}"

        # v2 API uses form-urlencoded with JSON in 'data' field
        import json
        form_data = {
            "devKey": self.api_token,
            "sessionId": self.api_token,  # Using API token as session
            "data": json.dumps(data),
        }

        logger.info(f"BILL v2 API request: POST {endpoint}")

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        url,
                        data=form_data,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Accept": "application/json",
                        },
                    )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("response_status") == 0:
                        logger.info(
                            f"BILL v2 API response: status={response.status_code}, "
                            f"response_status=0 (success)"
                        )
                        return result.get("response_data", {})
                    else:
                        error_msg = result.get("response_message", "Unknown error")
                        logger.error(f"BILL v2 API error: {error_msg}")
                        raise Exception(f"BILL v2 API error: {error_msg}")
                else:
                    logger.warning(
                        f"BILL v2 API request failed: status={response.status_code}, "
                        f"attempt={attempt + 1}/{self.max_retries}"
                    )

            except httpx.TimeoutException:
                logger.warning(
                    f"BILL v2 API timeout, attempt={attempt + 1}/{self.max_retries}"
                )
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(
                    f"BILL v2 API error: {e}, attempt={attempt + 1}/{self.max_retries}"
                )

        raise Exception(f"BILL v2 API request failed after {self.max_retries} attempts")

    def list_departments(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all departments from Bill.com.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of department dictionaries with 'id', 'name', etc.
        """
        if self._departments_cache is not None and not force_refresh:
            logger.info(
                f"Returning cached departments: {len(self._departments_cache)} items"
            )
            return self._departments_cache

        logger.info("Fetching departments from BILL v2 API...")

        data = {
            "start": 0,
            "max": 999,
        }

        response_data = self._make_request("/List/Department.json", data)
        departments = response_data if isinstance(response_data, list) else []

        self._departments_cache = departments
        logger.info(f"Fetched {len(departments)} departments from BILL")

        return departments

    def get_department_by_cost_center_prefix(
        self,
        cost_center: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find department by cost center prefix.

        Extracts first 4 digits from cost center and finds
        a department whose name contains those digits.

        Args:
            cost_center: Full cost center string (e.g., "5230-Engineering")

        Returns:
            Department dict if found, None otherwise
        """
        if not cost_center:
            return None

        # Extract first 4 digits
        prefix = cost_center[:4] if len(cost_center) >= 4 else cost_center
        # Ensure we only have digits
        prefix = "".join(c for c in prefix if c.isdigit())

        if not prefix:
            logger.warning(f"No numeric prefix found in cost center: {cost_center}")
            return None

        departments = self.list_departments()

        for dept in departments:
            dept_name = dept.get("name", "")
            if prefix in dept_name:
                logger.info(
                    f"Matched cost center prefix '{prefix}' to department: {dept_name}"
                )
                return dept

        logger.warning(
            f"No department found for cost center prefix '{prefix}' "
            f"(from cost_center='{cost_center}')"
        )
        return None

    def get_budget_from_cost_center(self, cost_center: str) -> str:
        """
        Get budget/department name from cost center.

        This is the main method to use for budget resolution.

        Args:
            cost_center: Full cost center string

        Returns:
            Department name if found, empty string otherwise
        """
        dept = self.get_department_by_cost_center_prefix(cost_center)
        if dept:
            return dept.get("name", "")
        return ""

    def clear_cache(self) -> None:
        """Clear the departments cache."""
        self._departments_cache = None
        logger.info("Department cache cleared")
