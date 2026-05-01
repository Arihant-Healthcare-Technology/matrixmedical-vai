"""
BILL.com Spend & Expense API client.

This module provides the S&E API client for user management.
"""

import logging
import time
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
        return self._extract_items(data, ["results", "users", "items", "data"])

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

        Tries multiple strategies:
        1. Direct email filter query (if API supports it)
        2. Paginate through all users as fallback

        Args:
            email: User email

        Returns:
            User dict or None if not found
        """
        email_lower = email.lower().strip()

        # Strategy 1: Try direct email filter (some BILL APIs support this)
        try:
            params = {"email": email_lower}
            response = self._http.get("/users", params=params)
            if response.status_code == 200:
                data = self._handle_response(response)
                items = self._extract_items(data, ["results", "users", "items", "data"])
                if items:
                    # Return first matching user
                    for user in items:
                        if user.get("email", "").lower().strip() == email_lower:
                            logger.info(f"Found user by email filter: {email}")
                            return user
        except Exception as e:
            logger.debug(f"Email filter search failed: {e}")

        # Strategy 2: Paginate through all users
        logger.debug(f"Searching for {email} via pagination...")
        for user in self._paginate("/users", item_keys=["results", "users"]):
            if user.get("email", "").lower().strip() == email_lower:
                logger.info(f"Found user via pagination: {email}")
                return user

        logger.warning(f"User not found in BILL: {email}")
        return None

    def search_user_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Find S&E user by external ID (employee number).

        Args:
            external_id: External ID (employee number)

        Returns:
            User dict or None if not found
        """
        # Try direct externalId filter
        try:
            params = {"externalId": external_id}
            response = self._http.get("/users", params=params)
            if response.status_code == 200:
                data = self._handle_response(response)
                items = self._extract_items(data, ["results", "users", "items", "data"])
                if items:
                    for user in items:
                        if user.get("externalId") == external_id:
                            logger.debug(f"Found user by externalId: {external_id}")
                            return user
        except Exception as e:
            logger.debug(f"ExternalId search failed: {e}")

        # Fallback: paginate through all users
        for user in self._paginate("/users", item_keys=["results", "users"]):
            if user.get("externalId") == external_id:
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
        external_id = payload.get("externalId", "N/A")
        role = payload.get("role", "N/A")
        cost_center = payload.get("costCenter", "N/A")
        first_name = payload.get("firstName", "N/A")
        last_name = payload.get("lastName", "N/A")

        logger.info(
            f"API CREATE REQUEST: POST /users\n"
            f"  email={email}, external_id={external_id}, role={role}\n"
            f"  name={first_name} {last_name}, cost_center={cost_center}"
        )
        response = self._http.post("/users", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201], request_payload=payload)
        user_id = result.get("uuid") or result.get("id")
        logger.info(
            f"API CREATE SUCCESS: email={email}, bill_user_id={user_id}, "
            f"status={response.status_code}"
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
        email = payload.get("email", "N/A")
        external_id = payload.get("externalId", "N/A")

        logger.info(
            f"API UPDATE REQUEST: PATCH /users/{user_id}\n"
            f"  email={email}, external_id={external_id}\n"
            f"  fields_to_update={fields}"
        )
        response = self._http.patch(f"/users/{user_id}", json=payload)
        result = self._handle_response(response, [200, 204], request_payload=payload)
        response_id = result.get("uuid") or result.get("id") if result else user_id
        logger.info(
            f"API UPDATE SUCCESS: email={email}, bill_user_id={response_id}, "
            f"status={response.status_code}, updated_fields={fields}"
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
        logger.info(f"API RETIRE REQUEST: DELETE /users/{user_id}")
        response = self._http.delete(f"/users/{user_id}")
        self._handle_response(response, [200, 204])
        logger.info(
            f"API RETIRE SUCCESS: bill_user_id={user_id}, status={response.status_code}"
        )
        return True

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all S&E users using cursor-based pagination."""
        return self.get_all_users_with_cursor_pagination()

    def get_all_users_with_cursor_pagination(
        self, max_per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch all S&E users using cursor-based pagination.

        Bill S&E API uses nextPage cursor instead of page numbers.
        Uses `max` query param for page size and `nextPage` for cursor.

        Args:
            max_per_page: Maximum users per page (Bill API max is 100)

        Returns:
            List of all user dicts
        """
        all_users: List[Dict[str, Any]] = []
        next_page_cursor: Optional[str] = None
        page_count = 0

        while True:
            # Rate limiting delay before each request
            time.sleep(5)
            page_count += 1

            # Build query params
            params: Dict[str, Any] = {"max": max_per_page}
            if next_page_cursor:
                params["nextPage"] = next_page_cursor

            logger.info(
                f"Fetching Bill users page {page_count} "
                f"(cursor={next_page_cursor or 'initial'})"
            )

            response = self._http.get("/users", params=params)
            data = self._handle_response(response)

            # Log response structure on first page for debugging
            if page_count == 1:
                response_keys = list(data.keys()) if isinstance(data, dict) else "not a dict"
                logger.info(f"BILL.com /users response keys: {response_keys}")

            # Extract results from response - handle various API response formats
            # BILL.com may return users under "results", "users", "items", or "data" keys
            results = self._extract_items(data, ["results", "users", "items", "data"])
            all_users.extend(results)

            # Log sample user structure on first page for debugging
            if page_count == 1 and results:
                sample_user_keys = list(results[0].keys()) if isinstance(results[0], dict) else "not a dict"
                logger.info(f"Sample user keys: {sample_user_keys}")
                sample_email = results[0].get("email", "NO EMAIL KEY")
                sample_id = results[0].get("id") or results[0].get("uuid", "NO ID KEY")
                logger.info(f"Sample user: email={sample_email}, id={sample_id}")

            logger.info(
                f"Page {page_count}: fetched {len(results)} users "
                f"(total: {len(all_users)})"
            )

            # Check for next page cursor
            next_page_cursor = data.get("nextPage")
            if not next_page_cursor:
                break  # No more pages

        logger.info(
            f"Pagination complete: {len(all_users)} total users "
            f"from {page_count} pages"
        )
        return all_users
