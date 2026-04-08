"""UKG API client for TravelPerk integration."""

import base64
import logging
from typing import Any, Dict, List, Optional

import requests

from ....domain.exceptions import (
    UkgApiError,
    AuthenticationError,
    RateLimitError,
    BadRequestError,
    NotFoundError,
    ServerError,
    TimeoutError,
)
from ...config.settings import UKGSettings


logger = logging.getLogger(__name__)


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
                logger.debug(f"Using UKG_BASIC_B64 (length: {len(token)})")
                self._token = token
                return token
            except Exception as error:
                logger.warning(f"UKG_BASIC_B64 is invalid: {error}")

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
        """Make GET request to UKG API.

        Args:
            path: API endpoint path.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: For 401/403 status codes.
            BadRequestError: For 400 status code.
            NotFoundError: For 404 status code.
            RateLimitError: For 429 status code.
            ServerError: For 5xx status codes.
            TimeoutError: For request timeouts.
            UkgApiError: For other error status codes.
        """
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.settings.timeout,
            )
        except requests.exceptions.Timeout as e:
            logger.error(f"UKG API timeout: {url}")
            raise TimeoutError(
                message=f"UKG API request timed out: {url}",
                timeout_seconds=self.settings.timeout,
            ) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"UKG API connection error: {url} - {e}")
            raise ServerError(
                message=f"UKG API connection failed: {e}",
                status_code=503,
            ) from e

        if self.debug:
            logger.debug(f"GET {response.url} -> {response.status_code}")

        # Handle specific HTTP status codes
        self._handle_response_status(response, url)

        try:
            data = response.json()
            if self.debug:
                if isinstance(data, list):
                    logger.debug(f"Response: list len={len(data)}")
                elif isinstance(data, dict):
                    logger.debug(f"Response: dict keys={list(data.keys())[:12]}")
            return data
        except Exception:
            return {}

    def _handle_response_status(
        self,
        response: requests.Response,
        url: str,
    ) -> None:
        """Handle HTTP response status codes.

        Args:
            response: HTTP response object.
            url: Request URL for error messages.

        Raises:
            Appropriate exception based on status code.
        """
        status = response.status_code

        if status < 400:
            return  # Success

        # Parse error response body
        try:
            error_body = response.json()
        except Exception:
            error_body = {"raw_text": response.text[:500]}

        error_message = error_body.get("message") or error_body.get("error") or response.text[:200]

        if status == 400:
            logger.warning(f"UKG bad request: {url} - {error_message}")
            raise BadRequestError(
                message=f"UKG bad request: {error_message}",
                response_body=error_body,
            )

        elif status == 401:
            logger.error(f"UKG authentication failed: {url}")
            raise AuthenticationError(
                message="UKG authentication failed - check credentials",
                status_code=401,
            )

        elif status == 403:
            logger.error(f"UKG access forbidden: {url}")
            raise AuthenticationError(
                message="UKG access forbidden - check API key permissions",
                status_code=403,
            )

        elif status == 404:
            logger.debug(f"UKG resource not found: {url}")
            raise NotFoundError(
                message=f"UKG resource not found: {url}",
                resource_type="employee",
            )

        elif status == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"UKG rate limit exceeded, retry after {retry_after}s")
            raise RateLimitError(
                message="UKG rate limit exceeded",
                retry_after=retry_after,
            )

        elif status >= 500:
            logger.error(f"UKG server error {status}: {url} - {error_message}")
            raise ServerError(
                message=f"UKG server error: {error_message}",
                status_code=status,
                response_body=error_body,
            )

        else:
            logger.error(f"UKG API error {status}: {url} - {error_message}")
            raise UkgApiError(
                message=f"UKG API error: {error_message}",
                status_code=status,
                response_body=error_body,
            )

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
            logger.info(
                f"companyId={company_id} -> total: {original_count} | "
                f"filtered by employeeTypeCode={list(type_codes_set)}: {len(items)}"
            )
        else:
            logger.info(f"companyId={company_id} -> total records: {len(items)}")

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
