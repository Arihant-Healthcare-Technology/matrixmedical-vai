"""
Motus API client.

Provides client for interacting with Motus driver APIs.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from src.domain.exceptions import AuthenticationError, MotusApiError, RateLimitError
from src.domain.models import MotusDriver
from src.infrastructure.config.settings import MotusSettings

logger = logging.getLogger(__name__)


class MotusClient:
    """Client for Motus driver APIs."""

    def __init__(
        self,
        settings: Optional[MotusSettings] = None,
        debug: bool = False,
        rate_limiter: Optional[Any] = None,
    ):
        """
        Initialize Motus client.

        Args:
            settings: Motus settings (defaults to from_env)
            debug: Enable debug logging
            rate_limiter: Optional rate limiter instance
        """
        self.settings = settings or MotusSettings.from_env()
        self.debug = debug
        self.rate_limiter = rate_limiter

    def _log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            logger.debug(message)

    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        if not self.settings.jwt:
            raise AuthenticationError("Missing MOTUS_JWT", provider="motus")
        return {
            "Authorization": f"Bearer {self.settings.jwt}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _acquire_rate_limit(self) -> None:
        """Acquire rate limit slot if rate limiter is configured."""
        if self.rate_limiter:
            self.rate_limiter.acquire()

    @staticmethod
    def _today_ymd() -> str:
        """Get today's date in YYYY-MM-DD format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _handle_response(
        self,
        response: requests.Response,
        driver_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle API response.

        Args:
            response: HTTP response
            driver_id: Optional driver ID for error context

        Returns:
            Parsed JSON response

        Raises:
            MotusApiError: If request failed
            RateLimitError: If rate limited
            AuthenticationError: If authentication failed
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = int(retry_after) if retry_after else 60
            raise RateLimitError(
                f"Rate limit exceeded, retry after {wait_time}s",
                retry_after=wait_time,
            )

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f"Authentication failed: {response.status_code}",
                provider="motus",
            )

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"text": response.text[:500]}
            raise MotusApiError(
                f"Motus API error {response.status_code}",
                status_code=response.status_code,
                response_body=body,
                driver_id=driver_id,
            )

        try:
            return response.json()
        except Exception:
            return {}

    def get_driver(self, client_employee_id1: str) -> Optional[Dict[str, Any]]:
        """
        Get driver by client employee ID.

        Args:
            client_employee_id1: Client employee ID

        Returns:
            Driver data or None if not found
        """
        self._acquire_rate_limit()

        url = f"{self.settings.api_base}/drivers/{client_employee_id1}"
        self._log(f"GET {url}")

        try:
            response = requests.get(url, headers=self._headers(), timeout=45)
        except requests.exceptions.RequestException as e:
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=client_employee_id1,
            ) from e

        if response.status_code == 404:
            return None

        return self._handle_response(response, driver_id=client_employee_id1)

    def driver_exists(self, client_employee_id1: str) -> bool:
        """
        Check if driver exists.

        Args:
            client_employee_id1: Client employee ID

        Returns:
            True if driver exists
        """
        return self.get_driver(client_employee_id1) is not None

    def create_driver(self, driver: MotusDriver) -> Dict[str, Any]:
        """
        Create a new driver.

        Args:
            driver: Driver to create

        Returns:
            Created driver data
        """
        self._acquire_rate_limit()

        payload = driver.to_api_payload()

        # Ensure startDate for insert
        if not payload.get("startDate"):
            payload["startDate"] = self._today_ymd()
            self._log(f"startDate injected for INSERT: {payload['startDate']}")

        url = f"{self.settings.api_base}/drivers"
        self._log(f"POST {url}")

        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=driver.client_employee_id1,
            ) from e

        result = self._handle_response(response, driver_id=driver.client_employee_id1)

        # Log success response
        logger.info(f"Driver CREATED: {driver.client_employee_id1} | "
                    f"Name: {driver.first_name} {driver.last_name} | "
                    f"Status: {response.status_code} | "
                    f"Program: {driver.program_id}")

        return result

    def update_driver(self, driver: MotusDriver) -> Dict[str, Any]:
        """
        Update an existing driver.

        Args:
            driver: Driver to update

        Returns:
            Updated driver data
        """
        self._acquire_rate_limit()

        payload = driver.to_api_payload()

        # Remove startDate for update
        if "startDate" in payload:
            payload.pop("startDate", None)
            self._log("startDate stripped for UPDATE")

        url = f"{self.settings.api_base}/drivers/{driver.client_employee_id1}"
        self._log(f"PUT {url}")

        try:
            response = requests.put(
                url,
                headers=self._headers(),
                json=payload,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=driver.client_employee_id1,
            ) from e

        result = self._handle_response(response, driver_id=driver.client_employee_id1)

        # Log success response
        end_date_info = f" | EndDate: {driver.end_date}" if driver.end_date else ""
        leave_info = f" | Leave: {driver.leave_start_date}" if driver.leave_start_date else ""
        logger.info(f"Driver UPDATED: {driver.client_employee_id1} | "
                    f"Name: {driver.first_name} {driver.last_name} | "
                    f"Status: {response.status_code} | "
                    f"Program: {driver.program_id}{end_date_info}{leave_info}")

        return result

    def upsert_driver(
        self,
        driver: MotusDriver,
        dry_run: bool = False,
        probe: bool = False,
    ) -> Dict[str, Any]:
        """
        Upsert (create or update) a driver.

        Args:
            driver: Driver to upsert
            dry_run: If True, only validate without making changes
            probe: If True, check if driver exists without creating

        Returns:
            Result dict with action taken
        """
        # Validate driver
        errors = driver.validate()
        if errors:
            return {
                "success": False,
                "action": "validation_error",
                "id": driver.client_employee_id1,
                "errors": errors,
            }

        if dry_run:
            if probe:
                # Check if driver exists
                exists = self.driver_exists(driver.client_employee_id1)
                action = "would_update" if exists else "would_insert"
                return {
                    "dry_run": True,
                    "id": driver.client_employee_id1,
                    "action": action,
                }
            else:
                # Just validate
                return {
                    "dry_run": True,
                    "id": driver.client_employee_id1,
                    "action": "validated",
                }

        # Check if driver exists
        exists = self.driver_exists(driver.client_employee_id1)

        if exists:
            result = self.update_driver(driver)
            return {
                "success": True,
                "action": "update",
                "id": driver.client_employee_id1,
                "name": f"{driver.first_name} {driver.last_name}",
                "program_id": driver.program_id,
                "end_date": driver.end_date,
                "leave_start_date": driver.leave_start_date,
                "data": result,
            }
        else:
            result = self.create_driver(driver)
            return {
                "success": True,
                "action": "insert",
                "id": driver.client_employee_id1,
                "name": f"{driver.first_name} {driver.last_name}",
                "program_id": driver.program_id,
                "data": result,
            }
