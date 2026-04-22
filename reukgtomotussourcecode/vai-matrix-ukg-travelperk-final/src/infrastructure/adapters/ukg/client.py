"""
UKG API client for TravelPerk integration.

This client provides methods for fetching employee data from UKG Personnel API.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from ....domain.exceptions import TimeoutError, ServerError
from ...config.settings import UKGSettings
from .auth import UKGAuthenticator
from .endpoints import UKGEndpoints
from .error_handler import UKGErrorHandler


logger = logging.getLogger(__name__)


class UKGClient:
    """Client for UKG Personnel API."""

    def __init__(
        self,
        settings: Optional[UKGSettings] = None,
        debug: bool = False,
    ):
        """
        Initialize UKG client.

        Args:
            settings: UKG API settings. If None, loads from environment.
            debug: Enable debug logging

        Raises:
            ValueError: If required settings are missing
        """
        self.settings = settings or UKGSettings.from_env()
        self.debug = debug

        # Validate settings early to fail fast
        try:
            self.settings.validate()
            logger.debug("UKG settings validation passed")
        except ValueError as e:
            logger.error(f"UKG settings validation failed: {e}")
            raise

        self._authenticator = UKGAuthenticator(
            username=self.settings.username,
            password=self.settings.password,
            basic_b64=self.settings.basic_b64,
            customer_api_key=self.settings.customer_api_key,
        )

        # Counters for tracking API calls
        self._person_details_count = 0
        self._employment_details_count = 0

        # Cache for org-levels data
        self._org_levels_cache: Optional[Dict[int, Dict[str, str]]] = None

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make GET request to UKG API.

        Args:
            path: API endpoint path.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            Various exceptions from UKGErrorHandler
        """
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"
        start_time = time.time()

        # Log request (hide sensitive query params)
        safe_params = {
            k: "***" if "password" in k.lower() or "key" in k.lower() else v
            for k, v in (params or {}).items()
        }
        logger.info(f"UKG API request: GET {path} params={list(safe_params.keys())}")

        try:
            response = requests.get(
                url,
                headers=self._authenticator.get_headers(),
                params=params,
                timeout=self.settings.timeout,
            )
        except requests.exceptions.Timeout as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"UKG API timeout: GET {path} elapsed={elapsed_ms:.0f}ms "
                f"timeout={self.settings.timeout}s"
            )
            raise TimeoutError(
                message=f"UKG API request timed out: {url}",
                timeout_seconds=self.settings.timeout,
            ) from e
        except requests.exceptions.ConnectionError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"UKG API connection error: GET {path} "
                f"elapsed={elapsed_ms:.0f}ms error={e}"
            )
            raise ServerError(
                message=f"UKG API connection failed: {e}",
                status_code=503,
            ) from e

        elapsed_ms = (time.time() - start_time) * 1000
        if response.status_code < 400:
            logger.info(
                f"UKG API response: GET {path} status={response.status_code} "
                f"elapsed={elapsed_ms:.0f}ms"
            )
        else:
            logger.warning(
                f"UKG API response: GET {path} status={response.status_code} "
                f"elapsed={elapsed_ms:.0f}ms"
            )

        # Handle error responses
        UKGErrorHandler.handle_response(response, url)

        try:
            data = response.json()
            if self.debug:
                if isinstance(data, list):
                    logger.debug(f"UKG API response body: list len={len(data)}")
                elif isinstance(data, dict):
                    logger.debug(
                        f"UKG API response body keys: {list(data.keys())[:12]}"
                    )
            return data
        except Exception:
            return {}

    @staticmethod
    def _normalize_list(data: Any) -> List[Dict[str, Any]]:
        """Normalize API response to list."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return items
            return [data]
        return []

    def get_employment_details(
        self,
        employee_number: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """
        Get employment details for an employee.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employment details dictionary
        """
        self._employment_details_count += 1
        logger.info(
            f"Fetching employment details: employeeNumber={employee_number}, "
            f"companyId={company_id}"
        )
        params = UKGEndpoints.employment_details_params(
            employee_number=employee_number,
            company_id=company_id,
        )
        data = self._get(UKGEndpoints.EMPLOYMENT_DETAILS, params)
        items = self._normalize_list(data)

        for item in items:
            if str(item.get("employeeNumber")) == str(employee_number):
                comp = item.get("companyID") or item.get("companyId")
                if str(comp) == str(company_id):
                    return item

        return {}

    def get_all_employment_details_by_company(
        self,
        company_id: str,
        employee_type_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all employment details for a company.

        Args:
            company_id: Company ID
            employee_type_codes: Optional list of employee type codes to filter

        Returns:
            List of employment details
        """
        params = UKGEndpoints.employment_details_params(
            company_id=company_id,
            per_page=UKGEndpoints.MAX_PAGE_SIZE,
        )
        data = self._get(UKGEndpoints.EMPLOYMENT_DETAILS, params)
        items = self._normalize_list(data)

        if employee_type_codes:
            type_codes_set = {
                code.strip().upper() for code in employee_type_codes if code.strip()
            }
            original_count = len(items)
            items = [
                item
                for item in items
                if item.get("employeeTypeCode", "").strip().upper() in type_codes_set
            ]
            logger.info(
                f"companyId={company_id} -> total: {original_count} | "
                f"filtered by employeeTypeCode={list(type_codes_set)}: {len(items)}"
            )
        else:
            logger.info(f"companyId={company_id} -> total records: {len(items)}")

        return items

    def get_person_details(self, employee_id: str) -> Dict[str, Any]:
        """
        Get person details for an employee.

        Args:
            employee_id: Employee ID (not employee number)

        Returns:
            Person details dictionary
        """
        if not employee_id:
            raise ValueError("employee_id is required")

        self._person_details_count += 1
        logger.info(f"Fetching person details: employeeId={employee_id}")

        params = UKGEndpoints.person_details_params(employee_id)
        data = self._get(UKGEndpoints.PERSON_DETAILS, params)
        items = self._normalize_list(data)

        for item in items:
            if str(item.get("employeeId")) == str(employee_id):
                email = item.get("emailAddress", "N/A")
                logger.info(f"Person details found: employeeId={employee_id}, email={email}")
                return item

        if items:
            email = items[0].get("emailAddress", "N/A")
            logger.info(f"Person details found: employeeId={employee_id}, email={email}")
            return items[0]

        logger.info(f"Person details not found: employeeId={employee_id}")
        return {}

    def get_all_supervisor_details(self) -> List[Dict[str, Any]]:
        """
        Get all supervisor details.

        Returns:
            List of supervisor detail records
        """
        params = UKGEndpoints.supervisor_details_params(
            per_page=UKGEndpoints.MAX_PAGE_SIZE
        )
        data = self._get(UKGEndpoints.SUPERVISOR_DETAILS, params)
        return self._normalize_list(data)

    def print_summary(self) -> None:
        """Print summary of API call counts."""
        logger.info(
            f"UKG API Call Summary: "
            f"person_details_calls={self._person_details_count}, "
            f"employment_details_calls={self._employment_details_count}, "
            f"total_calls={self._person_details_count + self._employment_details_count}"
        )

    def get_org_levels(self) -> Dict[int, Dict[str, str]]:
        """Fetch and cache org-levels from UKG Configuration API.

        Returns:
            Dict mapping level -> {code: description}
            Example: {4: {"730": "730 - Southeast Clinical Part-time"}}
        """
        if self._org_levels_cache is not None:
            return self._org_levels_cache

        logger.info("Fetching org-levels from UKG Configuration API")
        data = self._get(UKGEndpoints.ORG_LEVELS)
        items = self._normalize_list(data)

        cache: Dict[int, Dict[str, str]] = {}
        for item in items:
            level = item.get("level")
            code = item.get("code")
            long_desc = item.get("longDescription")
            short_desc = item.get("description", "")
            description = long_desc or short_desc

            if level is not None and code:
                if level not in cache:
                    cache[level] = {}
                cache[level][str(code)] = str(description)

        logger.info(f"Cached org-levels for {len(cache)} levels")
        self._org_levels_cache = cache
        return self._org_levels_cache

    def get_org_level_description(self, level: int, code: Optional[str]) -> str:
        """Get description for an org level code.

        Args:
            level: Org level number (1, 2, 3, or 4)
            code: Org level code (e.g., "730")

        Returns:
            Description string or empty string if not found
        """
        if not code:
            return ""
        org_levels = self.get_org_levels()
        level_codes = org_levels.get(level, {})
        return level_codes.get(str(code), "")
