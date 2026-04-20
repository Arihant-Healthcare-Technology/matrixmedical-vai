"""
UKG API client.

Provides client for interacting with UKG Pro APIs.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from common.correlation import get_correlation_id
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
        self._org_levels_cache: Optional[Dict[int, Dict[str, str]]] = None

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
        correlation_id = get_correlation_id()
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.settings.timeout,
            )

            response.raise_for_status()

        except requests.RequestException as e:
            status_code = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            logger.error(
                f"[{correlation_id}] UKG GET ERROR | "
                f"URL: {url} | "
                f"Status: {status_code} | "
                f"Error: {str(e)}"
            )
            raise UkgApiError(
                f"HTTP error fetching {url}: {e}",
                status_code=status_code,
                endpoint=path,
            )

        try:
            data = response.json()
            return data
        except ValueError as e:
            logger.error(
                f"[{correlation_id}] UKG JSON_PARSE_ERROR | "
                f"URL: {url} | Error: {str(e)}"
            )
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
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get("/personnel/v1/employment-details", params)

        items: List[Dict[str, Any]] = (
            data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        )

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    return item
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
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get("/personnel/v1/employee-employment-details", params)

        items: List[Dict[str, Any]] = (
            data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        )

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    return item
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

        This is a soft lookup - failures are logged as warnings, not errors.
        Missing supervisor data does not block driver creation.

        Note: This method bypasses _get() to avoid ERROR-level logging on 404s.

        Args:
            employee_id: Employee ID

        Returns:
            Supervisor details dict (empty if not found)
        """
        correlation_id = get_correlation_id()
        url = f"{self.settings.base_url.rstrip('/')}/personnel/v1/employee-supervisor-details"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params={"employeeId": employee_id},
                timeout=self.settings.timeout,
            )

            # Handle 404 as soft failure (WARNING, not ERROR)
            if response.status_code == 404:
                logger.warning(
                    f"[{correlation_id}] Supervisor not found for employee {employee_id}. "
                    "Continuing with empty supervisor data."
                )
                return {}

            response.raise_for_status()
            data = response.json()

            items: List[Dict[str, Any]] = (
                data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
            )

            for item in items:
                # Response uses employeeID (uppercase)
                if str(item.get("employeeID")) == str(employee_id):
                    return item
            return items[0] if items else {}

        except requests.RequestException as e:
            # Soft error - log as warning, return empty dict
            logger.warning(
                f"[{correlation_id}] Supervisor lookup failed for employee {employee_id}: {e}. "
                "Continuing with empty supervisor data."
            )
            return {}
        except Exception as e:
            # Unexpected error - still soft fail
            logger.warning(
                f"[{correlation_id}] Unexpected error fetching supervisor for {employee_id}: {e}. "
                "Continuing with empty supervisor data."
            )
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
            except UkgApiError:
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

    def get_org_levels(self, force_refresh: bool = False) -> Dict[int, Dict[str, str]]:
        """
        Get all org-levels from UKG configuration.

        Results are cached for the lifetime of this client instance.

        Args:
            force_refresh: Force re-fetch even if cached

        Returns:
            Nested dict: {level: {code: description, ...}, ...}
            Example: {1: {"DIV1": "Division One"}, 2: {"DEPT1": "Dept A"}}
        """
        if not force_refresh and self._org_levels_cache is not None:
            return self._org_levels_cache

        correlation_id = get_correlation_id()

        try:
            data = self._get("/configuration/v1/org-levels")
            logger.debug(
                f"[{correlation_id}] org-levels API returned {len(data) if isinstance(data, list) else 1} items"
            )
        except UkgApiError as e:
            logger.warning(
                f"[{correlation_id}] Failed to fetch org-levels: {e}. Using empty cache."
            )
            self._org_levels_cache = {}
            return self._org_levels_cache

        # Build nested lookup dictionary
        cache: Dict[int, Dict[str, str]] = {}
        items = data if isinstance(data, list) else []

        for item in items:
            level = item.get("level")
            code = item.get("code")
            # Prefer longDescription (full description) over description (short)
            long_desc = item.get("longDescription")
            short_desc = item.get("description", "")
            description = long_desc or short_desc

            # Log first few items for debugging
            if len(cache) < 5:
                logger.debug(
                    f"[{correlation_id}] org-level item: level={level}, code={code}, "
                    f"longDescription={long_desc[:50] if long_desc else None}..., "
                    f"description={short_desc[:50] if short_desc else None}..."
                )

            if level is not None and code:
                if level not in cache:
                    cache[level] = {}
                cache[level][str(code)] = str(description)

        logger.debug(
            f"[{correlation_id}] org-levels cache built with {sum(len(v) for v in cache.values())} entries "
            f"across {len(cache)} levels"
        )
        self._org_levels_cache = cache
        return self._org_levels_cache

    def get_org_level_description(self, level: int, code: Optional[str]) -> str:
        """
        Get description for an org-level code.

        Args:
            level: Org level number (1, 2, 3, or 4)
            code: Org level code

        Returns:
            Description string, or empty string if not found
        """
        if not code:
            return ""

        org_levels = self.get_org_levels()
        level_codes = org_levels.get(level, {})
        return level_codes.get(str(code), "")
