"""
BILL.com Spend & Expense API client.

This module provides the S&E API client for user management.
"""

import logging
from typing import Any, Dict, List, Optional

from src.infrastructure.adapters.bill.base_client import BillClient
from src.infrastructure.config.constants import (
    BATCH_TIMEOUT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class SpendExpenseClient(BillClient):
    """
    BILL.com Spend & Expense API client.

    Provides operations for S&E user management.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """Initialize S&E client."""
        # Ensure we're using the S&E endpoint
        if not api_base.endswith("/spend"):
            api_base = api_base.rstrip("/") + "/spend"

        super().__init__(
            api_base=api_base,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )

    # =========================================================================
    # User Operations
    # =========================================================================

    def list_users(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """
        List all S&E users.

        Args:
            page: Page number
            page_size: Page size

        Returns:
            List of user dicts
        """
        params = {"page": page, "pageSize": page_size}
        response = self._http.get("/users", params=params)
        data = self._handle_response(response)
        return self._extract_items(data, ["users", "items", "data"])

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get S&E user by ID.

        Args:
            user_id: User UUID

        Returns:
            User dict
        """
        response = self._http.get(f"/users/{user_id}")
        return self._handle_response(response)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find S&E user by email.

        Args:
            email: User email

        Returns:
            User dict or None if not found
        """
        email_lower = email.lower().strip()

        # Paginate through all users
        for user in self._paginate("/users", item_keys=["users"]):
            if user.get("email", "").lower().strip() == email_lower:
                return user

        return None

    def create_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new S&E user.

        Args:
            payload: User creation payload

        Returns:
            Created user dict
        """
        email = payload.get("email", "unknown")
        role = payload.get("role", "N/A")
        cost_center = payload.get("costCenter", "N/A")
        logger.info(
            f"API request: POST /users, email={email}, role={role}, "
            f"cost_center={cost_center}"
        )
        response = self._http.post("/users", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201])
        user_id = result.get("uuid") or result.get("id")
        logger.info(
            f"API response: status={response.status_code}, "
            f"user_id={user_id}, email={email}"
        )
        return result

    def update_user(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing S&E user.

        Args:
            user_id: User UUID
            payload: Update payload

        Returns:
            Updated user dict
        """
        fields = list(payload.keys())
        logger.info(
            f"API request: PATCH /users/{user_id}, fields={fields}"
        )
        response = self._http.patch(f"/users/{user_id}", json=payload)
        result = self._handle_response(response, [200, 204])
        response_id = result.get("uuid") or result.get("id") if result else user_id
        logger.info(
            f"API response: status={response.status_code}, "
            f"user_id={response_id}, updated_fields={fields}"
        )
        return result

    def retire_user(self, user_id: str) -> bool:
        """
        Retire (deactivate) S&E user.

        Note: In BILL S&E, you retire users via DELETE endpoint.

        Args:
            user_id: User UUID

        Returns:
            True if retired successfully
        """
        logger.info(f"API request: DELETE /users/{user_id}")
        response = self._http.delete(f"/users/{user_id}")
        self._handle_response(response, [200, 204])
        logger.info(
            f"API response: status={response.status_code}, "
            f"user_id={user_id}, action=retired"
        )
        return True

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all S&E users (paginated)."""
        return self._paginate("/users", item_keys=["users"])
