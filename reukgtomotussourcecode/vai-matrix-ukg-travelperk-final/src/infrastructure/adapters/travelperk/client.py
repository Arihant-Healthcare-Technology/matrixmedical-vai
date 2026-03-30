"""TravelPerk SCIM API client."""

import time
from typing import Any, Dict, Optional

import requests

from ....domain.models import TravelPerkUser
from ....domain.exceptions import TravelPerkApiError, RateLimitError
from ...config.settings import TravelPerkSettings
from common import get_rate_limiter


class TravelPerkClient:
    """Client for TravelPerk SCIM API."""

    def __init__(
        self,
        settings: Optional[TravelPerkSettings] = None,
        debug: bool = False,
    ):
        """Initialize TravelPerk client.

        Args:
            settings: TravelPerk API settings. If None, loads from environment.
            debug: Enable debug logging
        """
        self.settings = settings or TravelPerkSettings.from_env()
        self.debug = debug
        self._rate_limiter = get_rate_limiter("travelperk")

    def _log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        if not self.settings.api_key:
            raise TravelPerkApiError("Missing TRAVELPERK_API_KEY")
        return {
            "Authorization": f"ApiKey {self.settings.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_rate_limit(self, response: requests.Response) -> int:
        """Extract retry-after seconds from 429 response."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return 60  # Default 60 seconds

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        """Safely parse JSON response."""
        try:
            return response.json()
        except Exception:
            return {"text": response.text[:500]}

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by TravelPerk ID.

        Args:
            user_id: TravelPerk user ID

        Returns:
            User data or None if not found
        """
        self._rate_limiter.acquire()
        url = f"{self.settings.api_base}/api/v2/scim/Users/{user_id}"
        self._log(f"GET {url}")

        response = requests.get(
            url,
            headers=self._headers(),
            timeout=self.settings.timeout,
        )

        if response.status_code == 200:
            return self._safe_json(response)
        if response.status_code == 404:
            return None

        raise TravelPerkApiError(
            f"Failed to get user: {response.text[:500]}",
            status_code=response.status_code,
        )

    def get_user_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Get user by external ID (employeeNumber).

        Args:
            external_id: External ID (employee number)

        Returns:
            User data or None if not found
        """
        self._rate_limiter.acquire()
        url = f"{self.settings.api_base}/api/v2/scim/Users"
        params = {"filter": f'externalId eq "{external_id}"'}
        self._log(f"GET {url}?filter=externalId eq \"{external_id}\"")

        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.settings.timeout,
        )

        if response.status_code == 200:
            data = self._safe_json(response)
            resources = data.get("Resources", [])
            if resources:
                return resources[0]
        return None

    def get_user_by_user_name(self, user_name: str) -> Optional[Dict[str, Any]]:
        """Get user by userName (email).

        Args:
            user_name: User email

        Returns:
            User data or None if not found
        """
        self._rate_limiter.acquire()
        url = f"{self.settings.api_base}/api/v2/scim/Users"
        params = {"filter": f'userName eq "{user_name}"'}
        self._log(f"GET {url}?filter=userName eq \"{user_name}\"")

        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.settings.timeout,
        )

        if response.status_code == 200:
            data = self._safe_json(response)
            resources = data.get("Resources", [])
            if resources:
                return resources[0]
        return None

    def create_user(self, user: TravelPerkUser) -> Dict[str, Any]:
        """Create new user in TravelPerk.

        Args:
            user: TravelPerkUser instance

        Returns:
            Created user data with TravelPerk ID

        Raises:
            TravelPerkApiError: If creation fails
        """
        payload = user.to_api_payload()

        for attempt in range(self.settings.max_retries + 1):
            self._rate_limiter.acquire()
            url = f"{self.settings.api_base}/api/v2/scim/Users"
            self._log(f"POST {url}")

            response = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self.settings.timeout,
            )

            if response.status_code in (200, 201):
                return self._safe_json(response)

            if response.status_code == 429:
                wait_time = self._handle_rate_limit(response)
                self._log(f"Rate limited (429), waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            if response.status_code >= 500 and attempt < self.settings.max_retries:
                self._log(f"POST retry {attempt + 1} after 5xx")
                time.sleep(2 ** attempt)
                continue

            raise TravelPerkApiError(
                f"Failed to create user: {response.text[:500]}",
                status_code=response.status_code,
                response_body=self._safe_json(response),
            )

        raise TravelPerkApiError("Max retries exceeded for create_user")

    def update_user(
        self,
        user_id: str,
        user: TravelPerkUser,
        include_manager: bool = True,
    ) -> Dict[str, Any]:
        """Update existing user using PATCH.

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
        self._log(f"PATCH payload: {patch_payload}")

        for attempt in range(self.settings.max_retries + 1):
            self._rate_limiter.acquire()
            url = f"{self.settings.api_base}/api/v2/scim/Users/{user_id}"
            self._log(f"PATCH {url}")

            response = requests.patch(
                url,
                headers=self._headers(),
                json=patch_payload,
                timeout=self.settings.timeout,
            )

            if response.status_code in (200, 204):
                return self._safe_json(response) if response.status_code == 200 else {"id": user_id}

            if response.status_code == 429:
                wait_time = self._handle_rate_limit(response)
                self._log(f"Rate limited (429), waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            if response.status_code >= 500 and attempt < self.settings.max_retries:
                self._log(f"PATCH retry {attempt + 1} after 5xx")
                time.sleep(2 ** attempt)
                continue

            raise TravelPerkApiError(
                f"Failed to update user: {response.text[:500]}",
                status_code=response.status_code,
                response_body=self._safe_json(response),
            )

        raise TravelPerkApiError("Max retries exceeded for update_user")

    def upsert_user(
        self,
        user: TravelPerkUser,
        include_manager: bool = True,
    ) -> Dict[str, Any]:
        """Create or update user.

        Args:
            user: TravelPerkUser instance
            include_manager: Whether to update manager on existing user

        Returns:
            Dict with action, status, id, and externalId
        """
        # Check if user exists by externalId
        existing = self.get_user_by_external_id(user.external_id)

        if existing:
            user_id = existing.get("id")
            if not user_id:
                raise TravelPerkApiError(
                    f"Existing user found but no id for externalId={user.external_id}"
                )

            result = self.update_user(user_id, user, include_manager=include_manager)
            return {
                "action": "update",
                "status": 200,
                "id": user_id,
                "externalId": user.external_id,
            }
        else:
            # Try to create
            try:
                result = self.create_user(user)
                user_id = result.get("id")
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
                        user_id = existing_by_name.get("id")
                        if user_id:
                            self._log(f"Found by userName, updating: id={user_id}")
                            self.update_user(user_id, user, include_manager=include_manager)
                            return {
                                "action": "update",
                                "status": 200,
                                "id": user_id,
                                "externalId": user.external_id,
                            }
                raise
