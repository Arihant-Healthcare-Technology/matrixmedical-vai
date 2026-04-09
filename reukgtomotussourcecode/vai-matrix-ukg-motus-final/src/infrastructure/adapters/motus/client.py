"""
Motus API client.

Provides client for interacting with Motus driver APIs.
Includes automatic token refresh before API calls.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

from common.correlation import get_correlation_id
from src.domain.exceptions import AuthenticationError, MotusApiError, RateLimitError
from src.domain.models import MotusDriver
from src.infrastructure.adapters.motus.token_service import MotusTokenService
from src.infrastructure.config.settings import MotusSettings

logger = logging.getLogger(__name__)


class MotusClient:
    """Client for Motus driver APIs."""

    def __init__(
        self,
        settings: Optional[MotusSettings] = None,
        debug: bool = False,
        rate_limiter: Optional[Any] = None,
        token_service: Optional[MotusTokenService] = None,
    ):
        """
        Initialize Motus client.

        Args:
            settings: Motus settings (defaults to from_env)
            debug: Enable debug logging
            rate_limiter: Optional rate limiter instance
            token_service: Optional token service for in-memory token management
        """
        self.settings = settings or MotusSettings.from_env()
        self.debug = debug
        self.rate_limiter = rate_limiter
        self._token_service = token_service or MotusTokenService()
        self._token_refreshed = False  # Track if we've already refreshed to prevent loops
        self._ensure_valid_token()

    def _ensure_valid_token(self) -> None:
        """Ensure we have a valid JWT token, refresh if needed."""
        if not self.settings.jwt:
            logger.info("No MOTUS_JWT found, attempting token refresh...")
            self._refresh_token()

    def _refresh_token(self) -> None:
        """Generate new token in memory using token service."""
        if self._token_refreshed:
            logger.warning("Token already refreshed once, not retrying to prevent loops")
            return

        correlation_id = get_correlation_id()
        logger.info(f"[{correlation_id}] Refreshing Motus token in memory...")

        try:
            token = self._token_service.get_token(force_refresh=True)
            self.settings.set_jwt(token)
            self._token_refreshed = True
            logger.info(f"[{correlation_id}] Token refresh successful (in memory)")
        except ValueError as e:
            logger.error(f"[{correlation_id}] Token refresh failed - missing credentials: {e}")
            raise AuthenticationError(f"Token refresh failed - missing credentials: {e}", provider="motus")
        except Exception as e:
            logger.error(f"[{correlation_id}] Token refresh failed: {str(e)}")
            raise AuthenticationError(f"Token refresh failed: {str(e)}", provider="motus")

    def _log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            logger.debug(message)

    def _headers(self) -> Dict[str, str]:
        """Get request headers. Auto-refreshes token if missing."""
        if not self.settings.jwt:
            logger.info("Token missing in _headers(), attempting refresh...")
            self._refresh_token()
            if not self.settings.jwt:
                raise AuthenticationError("Missing MOTUS_JWT after refresh attempt", provider="motus")
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

    @staticmethod
    def _is_terminated_in_motus(motus_driver_data: Optional[Dict[str, Any]]) -> bool:
        """
        Check if a driver is terminated in MOTUS based on endDate.

        A driver is considered terminated if:
        - The driver exists in MOTUS (data is not None)
        - The endDate field is present and non-empty
        - The endDate is today or in the past

        Args:
            motus_driver_data: Driver data from MOTUS GET response

        Returns:
            True if driver is terminated (endDate <= today), False otherwise
        """
        if not motus_driver_data:
            return False

        end_date_str = motus_driver_data.get("endDate")
        if not end_date_str or not end_date_str.strip():
            return False

        try:
            end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            return end_date <= today
        except (ValueError, TypeError):
            return False

    def _handle_response(
        self,
        response: requests.Response,
        driver_id: Optional[str] = None,
        method: str = "REQUEST",
    ) -> Dict[str, Any]:
        """
        Handle API response.

        Args:
            response: HTTP response
            driver_id: Optional driver ID for error context
            method: HTTP method for logging (GET, POST, PUT)

        Returns:
            Parsed JSON response

        Raises:
            MotusApiError: If request failed
            RateLimitError: If rate limited
            AuthenticationError: If authentication failed
        """
        correlation_id = get_correlation_id()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = int(retry_after) if retry_after else 60
            logger.error(
                f"[{correlation_id}] MOTUS {method} RATE_LIMITED | "
                f"Employee: {driver_id} | Retry after: {wait_time}s"
            )
            raise RateLimitError(
                f"Rate limit exceeded, retry after {wait_time}s",
                retry_after=wait_time,
            )

        if response.status_code in (401, 403):
            logger.warning(
                f"[{correlation_id}] MOTUS {method} AUTH_ERROR | "
                f"Status: {response.status_code} | Employee: {driver_id} | "
                f"Attempting token refresh..."
            )
            # Try to refresh the token
            self._refresh_token()
            # Raise with a flag indicating retry is possible
            raise AuthenticationError(
                f"Authentication failed: {response.status_code}. Token refreshed - please retry.",
                provider="motus",
            )

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"text": response.text[:500]}
            logger.error(
                f"[{correlation_id}] MOTUS {method} ERROR | "
                f"Status: {response.status_code} | "
                f"Employee: {driver_id} | "
                f"Response: {json.dumps(body, default=str)[:500]}"
            )
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
        correlation_id = get_correlation_id()

        url = f"{self.settings.api_base}/drivers/{client_employee_id1}"
        headers = self._headers()

        # Log full request details
        logger.info(
            f"[{correlation_id}] MOTUS GET REQUEST | "
            f"URL: {url} | Employee: {client_employee_id1}"
        )
        logger.info(
            f"[{correlation_id}] MOTUS GET HEADERS | {json.dumps(headers, default=str)}"
        )

        try:
            response = requests.get(url, headers=headers, timeout=45)
        except requests.exceptions.RequestException as e:
            logger.error(
                f"[{correlation_id}] MOTUS GET EXCEPTION | "
                f"Employee: {client_employee_id1} | Error: {str(e)}"
            )
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=client_employee_id1,
            ) from e

        if response.status_code == 404:
            logger.info(
                f"[{correlation_id}] MOTUS GET RESPONSE | "
                f"Status: 404 (Not Found) | Employee: {client_employee_id1}"
            )
            return None

        logger.info(
            f"[{correlation_id}] MOTUS GET RESPONSE | "
            f"Status: {response.status_code} | Employee: {client_employee_id1}"
        )

        return self._handle_response(response, driver_id=client_employee_id1, method="GET")

    def driver_exists(self, client_employee_id1: str) -> bool:
        """
        Check if driver exists.

        Args:
            client_employee_id1: Client employee ID

        Returns:
            True if driver exists
        """
        return self.get_driver(client_employee_id1) is not None

    def is_driver_terminated(
        self, client_employee_id1: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if driver exists and is terminated in MOTUS.

        Makes a GET request to MOTUS to retrieve driver data and checks
        if the endDate field indicates termination (endDate <= today).

        Args:
            client_employee_id1: Client employee ID

        Returns:
            Tuple of (is_terminated, driver_data):
            - (True, data) if driver exists and endDate <= today
            - (False, data) if driver exists but not terminated
            - (False, None) if driver does not exist
        """
        correlation_id = get_correlation_id()
        driver_data = self.get_driver(client_employee_id1)

        if driver_data is None:
            logger.info(
                f"[{correlation_id}] MOTUS TERMINATED CHECK | "
                f"Employee: {client_employee_id1} | "
                f"Result: NOT_FOUND (driver does not exist in MOTUS)"
            )
            return (False, None)

        is_terminated = self._is_terminated_in_motus(driver_data)
        motus_end_date = driver_data.get("endDate", "")

        if is_terminated:
            logger.info(
                f"[{correlation_id}] MOTUS TERMINATED CHECK | "
                f"Employee: {client_employee_id1} | "
                f"Result: TERMINATED | "
                f"MOTUS endDate: {motus_end_date}"
            )
        else:
            logger.info(
                f"[{correlation_id}] MOTUS TERMINATED CHECK | "
                f"Employee: {client_employee_id1} | "
                f"Result: ACTIVE | "
                f"MOTUS endDate: {motus_end_date if motus_end_date else 'N/A'}"
            )

        return (is_terminated, driver_data)

    def create_driver(self, driver: MotusDriver) -> Dict[str, Any]:
        """
        Create a new driver.

        Args:
            driver: Driver to create

        Returns:
            Created driver data
        """
        self._acquire_rate_limit()
        correlation_id = get_correlation_id()

        payload = driver.to_api_payload()

        # Ensure startDate for insert
        if not payload.get("startDate"):
            payload["startDate"] = self._today_ymd()
            self._log(f"startDate injected for INSERT: {payload['startDate']}")

        url = f"{self.settings.api_base}/drivers"
        headers = self._headers()

        # Log full request details BEFORE sending
        logger.info(
            f"[{correlation_id}] MOTUS POST REQUEST | "
            f"URL: {url} | "
            f"Employee: {driver.client_employee_id1}"
        )
        logger.info(
            f"[{correlation_id}] MOTUS POST HEADERS | {json.dumps(headers, default=str)}"
        )
        logger.info(
            f"[{correlation_id}] MOTUS POST BODY | {json.dumps(payload, default=str)}"
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            logger.error(
                f"[{correlation_id}] MOTUS POST EXCEPTION | "
                f"Employee: {driver.client_employee_id1} | "
                f"Error: {str(e)}"
            )
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=driver.client_employee_id1,
            ) from e

        result = self._handle_response(response, driver_id=driver.client_employee_id1, method="POST")

        # Log success response
        logger.info(
            f"[{correlation_id}] MOTUS POST RESPONSE | "
            f"Status: {response.status_code} | "
            f"Employee: {driver.client_employee_id1} | "
            f"Name: {driver.first_name} {driver.last_name} | "
            f"Program: {driver.program_id}"
        )

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
        correlation_id = get_correlation_id()

        payload = driver.to_api_payload()

        # Remove startDate for update
        if "startDate" in payload:
            payload.pop("startDate", None)
            self._log("startDate stripped for UPDATE")

        url = f"{self.settings.api_base}/drivers/{driver.client_employee_id1}"
        headers = self._headers()

        # Log full request details BEFORE sending
        logger.info(
            f"[{correlation_id}] MOTUS PUT REQUEST | "
            f"URL: {url} | "
            f"Employee: {driver.client_employee_id1}"
        )
        logger.info(
            f"[{correlation_id}] MOTUS PUT HEADERS | {json.dumps(headers, default=str)}"
        )
        logger.info(
            f"[{correlation_id}] MOTUS PUT BODY | {json.dumps(payload, default=str)}"
        )

        try:
            response = requests.put(
                url,
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            logger.error(
                f"[{correlation_id}] MOTUS PUT EXCEPTION | "
                f"Employee: {driver.client_employee_id1} | "
                f"Error: {str(e)}"
            )
            raise MotusApiError(
                f"Request failed: {str(e)}",
                status_code=0,
                response_body={"error": str(e)},
                driver_id=driver.client_employee_id1,
            ) from e

        result = self._handle_response(response, driver_id=driver.client_employee_id1, method="PUT")

        # Log success response
        end_date_info = f" | EndDate: {driver.end_date}" if driver.end_date else ""
        leave_info = f" | Leave: {driver.leave_start_date}" if driver.leave_start_date else ""
        logger.info(
            f"[{correlation_id}] MOTUS PUT RESPONSE | "
            f"Status: {response.status_code} | "
            f"Employee: {driver.client_employee_id1} | "
            f"Name: {driver.first_name} {driver.last_name} | "
            f"Program: {driver.program_id}{end_date_info}{leave_info}"
        )

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
        correlation_id = get_correlation_id()

        # Validate driver
        errors = driver.validate()
        if errors:
            logger.error(
                f"[{correlation_id}] MOTUS VALIDATION_ERROR | "
                f"Employee: {driver.client_employee_id1} | "
                f"Errors: {errors}"
            )
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
