"""
TravelPerk SCIM API client.

This client provides methods for managing users via TravelPerk's SCIM 2.0 API.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

from ....domain.models import TravelPerkUser
from ....domain.exceptions import TravelPerkApiError
from ...config.settings import TravelPerkSettings
from ...http.utils import parse_json_response, sanitize_url_for_logging
from common import get_rate_limiter, sanitize_for_logging
from .endpoints import TravelPerkEndpoints
from .error_handler import TravelPerkErrorHandler
from .scim import extract_resources, get_user_id


logger = logging.getLogger(__name__)


class TravelPerkClient:
    """Client for TravelPerk SCIM API."""

    def __init__(
        self,
        settings: Optional[TravelPerkSettings] = None,
        debug: bool = False,
    ):
        """
        Initialize TravelPerk client.

        Args:
            settings: TravelPerk API settings. If None, loads from environment.
            debug: Enable debug logging

        Raises:
            ValueError: If required settings are missing
        """
        self.settings = settings or TravelPerkSettings.from_env()
        self.debug = debug

        # Validate settings early to fail fast
        try:
            self.settings.validate()
            logger.debug("TravelPerk settings validation passed")
        except ValueError as e:
            logger.error(f"TravelPerk settings validation failed: {e}")
            raise

        self._rate_limiter = get_rate_limiter("travelperk")

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        if not self.settings.api_key:
            raise TravelPerkApiError("Missing TRAVELPERK_API_KEY")
        return {
            "Authorization": f"ApiKey {self.settings.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.settings.api_base.rstrip('/')}{path}"

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        """Safely parse JSON response."""
        return parse_json_response(response)

    def _log_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict] = None,
    ) -> float:
        """Log API request and return start time."""
        start_time = time.time()
        safe_url = sanitize_url_for_logging(url)
        if payload:
            safe_payload = sanitize_for_logging(payload)
            logger.info(
                f"TravelPerk API request: {method} {safe_url} "
                f"payload_keys={list(safe_payload.keys()) if isinstance(safe_payload, dict) else 'N/A'}"
            )
        else:
            logger.info(f"TravelPerk API request: {method} {safe_url}")
        if self.debug:
            logger.debug(f"TravelPerk API full URL: {url}")
        return start_time

    def _log_response(
        self,
        method: str,
        url: str,
        status: int,
        start_time: float,
        data: Any = None,
    ) -> None:
        """Log API response with timing."""
        elapsed_ms = (time.time() - start_time) * 1000
        safe_url = sanitize_url_for_logging(url)
        if status < 400:
            logger.info(
                f"TravelPerk API response: {method} {safe_url} "
                f"status={status} elapsed={elapsed_ms:.0f}ms"
            )
        else:
            logger.warning(
                f"TravelPerk API response: {method} {safe_url} "
                f"status={status} elapsed={elapsed_ms:.0f}ms"
            )
        if self.debug and data:
            if isinstance(data, dict):
                logger.debug(
                    f"TravelPerk API response body keys: {list(data.keys())[:10]}"
                )
            elif isinstance(data, list):
                logger.debug(f"TravelPerk API response body: list len={len(data)}")

    def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> requests.Response:
        """Make HTTP request with retry logic."""
        url = self._build_url(path)

        for attempt in range(self.settings.max_retries + 1):
            self._rate_limiter.acquire()
            start_time = self._log_request(method, url, json_data)

            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=json_data,
                timeout=self.settings.timeout,
            )

            self._log_response(method, url, response.status_code, start_time)

            # Handle rate limit
            if response.status_code == 429:
                wait_time = TravelPerkErrorHandler.extract_retry_after(response)
                logger.warning(
                    f"TravelPerk rate limited (429), waiting {wait_time}s before retry"
                )
                time.sleep(wait_time)
                continue

            # Handle server errors
            if response.status_code >= 500 and attempt < self.settings.max_retries:
                logger.warning(
                    f"TravelPerk server error {response.status_code}, "
                    f"retry {attempt + 1}/{self.settings.max_retries}"
                )
                time.sleep(2 ** attempt)
                continue

            return response

        logger.error(f"TravelPerk max retries exceeded: {method} {url}")
        raise TravelPerkApiError("Max retries exceeded")

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by TravelPerk ID.

        Args:
            user_id: TravelPerk user ID

        Returns:
            User data or None if not found
        """
        path = TravelPerkEndpoints.user_by_id(user_id)
        response = self._request_with_retry("GET", path)

        if response.status_code == 200:
            return self._safe_json(response)
        if response.status_code == 404:
            logger.debug(f"TravelPerk user not found: id={user_id}")
            return None

        TravelPerkErrorHandler.handle_response(
            response, path, context=f"get_user id={user_id}"
        )
        return None

    def get_user_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by external ID (employeeNumber).

        Args:
            external_id: External ID (employee number)

        Returns:
            User data or None if not found
        """
        params = TravelPerkEndpoints.filter_by_external_id(external_id)
        response = self._request_with_retry(
            "GET", TravelPerkEndpoints.SCIM_USERS, params=params
        )

        if response.status_code == 200:
            data = self._safe_json(response)
            resources = extract_resources(data)
            if resources:
                logger.debug(f"TravelPerk user found by externalId={external_id}")
                return resources[0]
            logger.debug(f"TravelPerk user not found by externalId={external_id}")
        return None

    def get_user_by_user_name(self, user_name: str) -> Optional[Dict[str, Any]]:
        """
        Get user by userName (email).

        Args:
            user_name: User email

        Returns:
            User data or None if not found
        """
        params = TravelPerkEndpoints.filter_by_user_name(user_name)
        response = self._request_with_retry(
            "GET", TravelPerkEndpoints.SCIM_USERS, params=params
        )

        if response.status_code == 200:
            data = self._safe_json(response)
            resources = extract_resources(data)
            if resources:
                logger.debug("TravelPerk user found by userName (email lookup)")
                return resources[0]
        return None

    def create_user(self, user: TravelPerkUser) -> Dict[str, Any]:
        """
        Create new user in TravelPerk.

        Args:
            user: TravelPerkUser instance

        Returns:
            Created user data with TravelPerk ID

        Raises:
            TravelPerkApiError: If creation fails
        """
        payload = user.to_api_payload()
        response = self._request_with_retry(
            "POST", TravelPerkEndpoints.SCIM_USERS, json_data=payload
        )

        if response.status_code in (200, 201):
            data = self._safe_json(response)
            logger.info(
                f"TravelPerk user created: externalId={user.external_id} "
                f"id={get_user_id(data)}"
            )
            return data

        TravelPerkErrorHandler.handle_response(
            response,
            TravelPerkEndpoints.SCIM_USERS,
            context=f"create_user externalId={user.external_id}",
        )
        return {}

    def update_user(
        self,
        user_id: str,
        user: TravelPerkUser,
        include_manager: bool = True,
    ) -> Dict[str, Any]:
        """
        Update existing user using PATCH.

        Args:
            user_id: TravelPerk user ID
            user: TravelPerkUser with updated data
            include_manager: Whether to update manager field

        Returns:
            Updated user data

        Raises:
            TravelPerkApiError: If update fails
        """
        patch_payload = user.to_patch_payload(include_manager=include_manager)
        path = TravelPerkEndpoints.user_by_id(user_id)

        if self.debug:
            logger.debug(
                f"TravelPerk PATCH payload: {sanitize_for_logging(patch_payload)}"
            )

        response = self._request_with_retry("PATCH", path, json_data=patch_payload)

        if response.status_code in (200, 204):
            logger.info(
                f"TravelPerk user updated: id={user_id} externalId={user.external_id}"
            )
            if response.status_code == 200:
                return self._safe_json(response)
            return {"id": user_id}

        TravelPerkErrorHandler.handle_response(
            response, path, context=f"update_user id={user_id}"
        )
        return {}

    def upsert_user(
        self,
        user: TravelPerkUser,
        include_manager: bool = True,
    ) -> Dict[str, Any]:
        """
        Create or update user.

        Args:
            user: TravelPerkUser instance
            include_manager: Whether to update manager on existing user

        Returns:
            Dict with action, status, id, and externalId
        """
        # Check if user exists by externalId
        existing = self.get_user_by_external_id(user.external_id)

        if existing:
            user_id = get_user_id(existing)
            if not user_id:
                raise TravelPerkApiError(
                    f"Existing user found but no id for externalId={user.external_id}"
                )

            self.update_user(user_id, user, include_manager=include_manager)
            return {
                "action": "update",
                "status": 200,
                "id": user_id,
                "externalId": user.external_id,
            }

        # Try to create
        try:
            result = self.create_user(user)
            user_id = get_user_id(result)
            if not user_id:
                raise TravelPerkApiError(
                    f"User created but no id for externalId={user.external_id}"
                )
            return {
                "action": "insert",
                "status": 201,
                "id": user_id,
                "externalId": user.external_id,
            }
        except TravelPerkApiError as error:
            if error.status_code == 409:
                # Conflict - try to find by userName
                existing_by_name = self.get_user_by_user_name(user.user_name)
                if existing_by_name:
                    user_id = get_user_id(existing_by_name)
                    if user_id:
                        logger.info(
                            f"TravelPerk conflict resolved: found by userName, "
                            f"updating id={user_id}"
                        )
                        self.update_user(user_id, user, include_manager=include_manager)
                        return {
                            "action": "update",
                            "status": 200,
                            "id": user_id,
                            "externalId": user.external_id,
                        }
            raise
