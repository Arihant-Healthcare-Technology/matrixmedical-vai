"""UKG API client for TravelPerk integration."""

import base64
from typing import Any, Dict, List, Optional

import requests

from ....domain.exceptions import UkgApiError, AuthenticationError
from ...config.settings import UKGSettings


class UKGClient:
    """Client for UKG Personnel API."""

    def __init__(
        self,
        settings: Optional[UKGSettings] = None,
        debug: bool = False,
    ):
        """Initialize UKG client.

        Args:
            settings: UKG API settings. If None, loads from environment.
            debug: Enable debug logging
        """
        self.settings = settings or UKGSettings.from_env()
        self.debug = debug
        self._token: Optional[str] = None

    def _get_token(self) -> str:
        """Get HTTP Basic auth token."""
        if self._token:
            return self._token

        if self.settings.basic_b64:
            token = self.settings.basic_b64.strip()
            token = ''.join(token.split())
            try:
                base64.b64decode(token, validate=True)
                if self.debug:
                    print(f"[DEBUG] Using UKG_BASIC_B64 (length: {len(token)})")
                self._token = token
                return token
            except Exception as error:
                if self.debug:
                    print(f"[WARN] UKG_BASIC_B64 is invalid: {error}")

        if not self.settings.username or not self.settings.password:
            raise AuthenticationError("Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64")

        raw = f"{self.settings.username}:{self.settings.password}".encode()
        self._token = base64.b64encode(raw).decode()
        return self._token

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        if not self.settings.customer_api_key:
            raise AuthenticationError("Missing UKG_CUSTOMER_API_KEY")
        return {
            "Authorization": f"Basic {self._get_token()}",
            "US-CUSTOMER-API-KEY": self.settings.customer_api_key,
            "Accept": "application/json",
        }

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make GET request to UKG API."""
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"
        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.settings.timeout,
        )

        if self.debug:
            print(f"[DEBUG] GET {response.url} -> {response.status_code}")

        if response.status_code >= 400:
            raise UkgApiError(
                f"UKG API error: {response.text[:500]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
            if self.debug:
                if isinstance(data, list):
                    print(f"[DEBUG] list len={len(data)}")
                elif isinstance(data, dict):
                    print(f"[DEBUG] dict keys={list(data.keys())[:12]}")
            return data
        except Exception:
            return {}

    def _normalize_list(self, data: Any) -> List[Dict[str, Any]]:
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
        """Get employment details for an employee.

        Args:
            employee_number: Employee number
            company_id: Company ID

        Returns:
            Employment details dictionary
        """
        params = {"employeeNumber": employee_number, "companyID": company_id}
        data = self._get("/personnel/v1/employee-employment-details", params)
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
        """Get all employment details for a company.

        Args:
            company_id: Company ID
            employee_type_codes: Optional list of employee type codes to filter

        Returns:
            List of employment details
        """
        params = {"companyId": company_id, "per_Page": 2147483647}
        data = self._get("/personnel/v1/employee-employment-details", params)
        items = self._normalize_list(data)

        if employee_type_codes:
            type_codes_set = {
                code.strip().upper() for code in employee_type_codes if code.strip()
            }
            original_count = len(items)
            items = [
                item for item in items
                if item.get("employeeTypeCode", "").strip().upper() in type_codes_set
            ]
            print(
                f"[INFO] companyId={company_id} -> total: {original_count} | "
                f"filtered by employeeTypeCode={list(type_codes_set)}: {len(items)}"
            )
        else:
            print(f"[INFO] companyId={company_id} -> total records: {len(items)}")

        return items

    def get_person_details(self, employee_id: str) -> Dict[str, Any]:
        """Get person details for an employee.

        Args:
            employee_id: Employee ID (not employee number)

        Returns:
            Person details dictionary
        """
        if not employee_id:
            raise ValueError("employee_id is required")

        data = self._get("/personnel/v1/person-details", {"employeeId": employee_id})
        items = self._normalize_list(data)

        for item in items:
            if str(item.get("employeeId")) == str(employee_id):
                return item

        return items[0] if items else {}

    def get_all_supervisor_details(self) -> List[Dict[str, Any]]:
        """Get all supervisor details.

        Returns:
            List of supervisor detail records
        """
        params = {"per_Page": 2147483647}
        data = self._get("/personnel/v1/employee-supervisor-details", params)
        return self._normalize_list(data)
