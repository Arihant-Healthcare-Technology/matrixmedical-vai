"""
UKG API client.

Provides client for interacting with UKG Pro APIs.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from src.domain.exceptions import UkgApiError
from src.infrastructure.config.settings import UKGSettings

logger = logging.getLogger(__name__)


class UKGClient:
    """Client for UKG Pro APIs."""

    def __init__(self, settings: Optional[UKGSettings] = None, debug: bool = False):
        """
        Initialize UKG client.

        Args:
            settings: UKG settings (defaults to from_env)
            debug: Enable debug logging
        """
        self.settings = settings or UKGSettings.from_env()
        self.debug = debug

    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Basic {self.settings.get_auth_token()}",
            "US-CUSTOMER-API-KEY": self.settings.customer_api_key,
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make GET request to UKG API.

        Args:
            path: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            UkgApiError: If request fails
        """
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.settings.timeout,
            )

            if self.debug:
                logger.debug(f"GET {response.url} -> {response.status_code}")

            response.raise_for_status()

        except requests.RequestException as e:
            raise UkgApiError(
                f"HTTP error fetching {url}: {e}",
                status_code=getattr(e.response, "status_code", None) if hasattr(e, "response") else None,
                endpoint=path,
            )

        try:
            data = response.json()
            if self.debug:
                if isinstance(data, list):
                    logger.debug(f"UKG Response: list len={len(data)}; first keys={list(data[0].keys()) if data else []}")
                    if data and len(data) > 0:
                        # Log critical fields from first item for debugging
                        first = data[0]
                        logger.debug(f"UKG Response: First item - dateOfTermination={first.get('dateOfTermination')}")
                        logger.debug(f"UKG Response: First item - employeeStatusStartDate={first.get('employeeStatusStartDate')}")
                        logger.debug(f"UKG Response: First item - employeeStatusCode={first.get('employeeStatusCode')}")
                        logger.debug(f"UKG Response: First item - primaryProjectCode={first.get('primaryProjectCode')}")
                        logger.debug(f"UKG Response: First item - primaryProjectDescription={first.get('primaryProjectDescription')}")
                elif isinstance(data, dict):
                    logger.debug(f"UKG Response: dict keys={list(data.keys())}")
                    logger.debug(f"UKG Response: dateOfTermination={data.get('dateOfTermination')}")
                    logger.debug(f"UKG Response: employeeStatusStartDate={data.get('employeeStatusStartDate')}")
                    logger.debug(f"UKG Response: employeeStatusCode={data.get('employeeStatusCode')}")
                    logger.debug(f"UKG Response: primaryProjectCode={data.get('primaryProjectCode')}")
                    logger.debug(f"UKG Response: primaryProjectDescription={data.get('primaryProjectDescription')}")
            return data
        except ValueError as e:
            raise UkgApiError(f"JSON parse error from {url}: {e}", endpoint=path)

    @staticmethod
    def _get_first_item(data: Any) -> Dict[str, Any]:
        """Get first item from list or dict."""
        if isinstance(data, list):
            return data[0] if data else {}
        return data if isinstance(data, dict) else {}

    def get_employment_details(
        self, employee_number: str, company_id: str
    ) -> Dict[str, Any]:
        """
        Get employment details for an employee.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employment details dict
        """
        if self.debug:
            logger.debug(f"UKG get_employment_details: Fetching for employeeNumber={employee_number}, companyID={company_id}")
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get("/personnel/v1/employment-details", params)

        items: List[Dict[str, Any]] = (
            data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        )

        if self.debug:
            logger.debug(f"UKG get_employment_details: Total items returned: {len(items)}")

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    if self.debug:
                        logger.debug(f"UKG get_employment_details: MATCHED! All keys: {list(item.keys())}")
                        logger.debug(f"UKG get_employment_details: dateOfTermination = {item.get('dateOfTermination')}")
                        logger.debug(f"UKG get_employment_details: employeeStatusStartDate = {item.get('employeeStatusStartDate')}")
                        logger.debug(f"UKG get_employment_details: employeeStatusExpectedEndDate = {item.get('employeeStatusExpectedEndDate')}")
                        logger.debug(f"UKG get_employment_details: employeeStatusCode = {item.get('employeeStatusCode')}")
                        logger.debug(f"UKG get_employment_details: startDate = {item.get('startDate')}")
                    return item
        if self.debug:
            logger.debug(f"UKG get_employment_details: NO MATCH FOUND for employeeNumber={employee_number}")
        return {}

    def get_employee_employment_details(
        self, employee_number: str, company_id: str
    ) -> Dict[str, Any]:
        """
        Get employee employment details.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employee employment details dict
        """
        if self.debug:
            logger.debug(f"UKG get_employee_employment_details: Fetching for employeeNumber={employee_number}, companyID={company_id}")
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get("/personnel/v1/employee-employment-details", params)

        items: List[Dict[str, Any]] = (
            data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        )

        if self.debug:
            logger.debug(f"UKG get_employee_employment_details: Total items returned: {len(items)}")

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    if self.debug:
                        logger.debug(f"UKG get_employee_employment_details: MATCHED! All keys: {list(item.keys())}")
                        logger.debug(f"UKG get_employee_employment_details: primaryProjectCode = {item.get('primaryProjectCode')}")
                        logger.debug(f"UKG get_employee_employment_details: primaryProjectDescription = {item.get('primaryProjectDescription')}")
                    return item
        if self.debug:
            logger.debug(f"UKG get_employee_employment_details: NO MATCH FOUND for employeeNumber={employee_number}")
        return {}

    def get_person_details(self, employee_id: str) -> Dict[str, Any]:
        """
        Get person details for an employee.

        Args:
            employee_id: Employee ID

        Returns:
            Person details dict

        Raises:
            UkgApiError: If employee_id is missing
        """
        if not employee_id:
            raise UkgApiError("No employeeId available - cannot fetch person-details")

        data = self._get("/personnel/v1/person-details", {"employeeId": employee_id})

        items: List[Dict[str, Any]] = (
            data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        )

        for item in items:
            if str(item.get("employeeId")) == str(employee_id):
                return item
        return items[0] if items else {}

    def get_supervisor_details(self, employee_id: str) -> Dict[str, Any]:
        """
        Get supervisor details for an employee.

        Args:
            employee_id: Employee ID

        Returns:
            Supervisor details dict (empty if not found)
        """
        try:
            data = self._get("/personnel/v1/supervisor-details", {"employeeId": employee_id})

            items: List[Dict[str, Any]] = (
                data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
            )

            for item in items:
                if str(item.get("employeeId")) == str(employee_id):
                    return item
            return items[0] if items else {}

        except UkgApiError:
            if self.debug:
                logger.warning(f"No supervisor found for employeeId={employee_id}")
            return {}

    def get_location(self, location_code: str) -> Dict[str, Any]:
        """
        Get location details.

        Args:
            location_code: Location code

        Returns:
            Location details dict
        """
        if not location_code:
            return {}

        try:
            return self._get_first_item(
                self._get(f"/configuration/v1/locations/{location_code}")
            )
        except UkgApiError:
            try:
                return self._get_first_item(
                    self._get("/configuration/v1/locations", {"locationCode": location_code})
                )
            except UkgApiError as e:
                if self.debug:
                    logger.warning(f"Location fetch failed for {location_code}: {e}")
                return {}

    def get_all_employment_details_by_company(
        self, company_id: str, per_page: int = 2147483647
    ) -> List[Dict[str, Any]]:
        """
        Get all employment details for a company.

        Args:
            company_id: Company ID
            per_page: Items per page

        Returns:
            List of employment details
        """
        params = {"companyID": company_id, "per_Page": per_page}
        data = self._get("/personnel/v1/employee-employment-details", params)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items", []) if isinstance(data.get("items"), list) else [data]
        return []
