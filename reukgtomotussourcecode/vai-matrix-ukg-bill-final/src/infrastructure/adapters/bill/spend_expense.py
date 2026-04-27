"""
BILL.com Spend & Expense repository implementation.

This module implements the BillUserRepository interface using the S&E API client.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import BillUserRepository
from src.domain.models.bill_user import BillUser
from src.infrastructure.adapters.bill.client import SpendExpenseClient

logger = logging.getLogger(__name__)


class BillUserRepositoryImpl(BillUserRepository):
    """
    BILL.com Spend & Expense user repository implementation.

    Implements the BillUserRepository interface using the S&E API client.
    """

    def __init__(self, client: SpendExpenseClient) -> None:
        """
        Initialize repository.

        Args:
            client: S&E API client
        """
        self._client = client
        self._email_cache: Dict[str, str] = {}  # email -> user_id

    def get_by_id(self, entity_id: str) -> Optional[BillUser]:
        """
        Get user by BILL ID.

        Args:
            entity_id: User UUID

        Returns:
            BillUser if found, None otherwise
        """
        try:
            data = self._client.get_user(entity_id)
            if data:
                return BillUser.from_bill_api(data)
        except Exception as e:
            logger.debug(f"User not found by ID {entity_id}: {e}")

        return None

    def get_by_email(self, email: str) -> Optional[BillUser]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            BillUser if found, None otherwise
        """
        # Check cache first
        email_lower = email.lower().strip()
        if email_lower in self._email_cache:
            user_id = self._email_cache[email_lower]
            logger.debug(f"Email cache hit: {email} → user_id={user_id}")
            return self.get_by_id(user_id)

        # Search via API
        logger.debug(f"Email cache miss: {email}, searching API")
        data = self._client.get_user_by_email(email)
        if data:
            user = BillUser.from_bill_api(data)
            if user.id:
                self._email_cache[email_lower] = user.id
                logger.debug(f"Email cache populated: {email} → {user.id}")
            return user

        logger.debug(f"User not found in BILL.com: {email}")
        return None

    def get_active_users(self) -> List[BillUser]:
        """
        Get all active (non-retired) users.

        Returns:
            List of active users
        """
        all_users = self._client.get_all_users()
        active = []

        for data in all_users:
            user = BillUser.from_bill_api(data)
            if user.is_active:
                active.append(user)
                # Cache email -> id mapping
                if user.email and user.id:
                    self._email_cache[user.email.lower()] = user.id

        return active

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[BillUser]:
        """
        List users with pagination.

        Args:
            page: Page number
            page_size: Page size
            filters: Optional filters (not currently supported by S&E API)

        Returns:
            List of users
        """
        data = self._client.list_users(page=page, page_size=page_size)
        users = []

        for item in data:
            user = BillUser.from_bill_api(item)
            users.append(user)
            # Cache email -> id mapping
            if user.email and user.id:
                self._email_cache[user.email.lower()] = user.id

        return users

    def create(self, entity: BillUser) -> BillUser:
        """
        Create new user in BILL.

        Args:
            entity: User to create

        Returns:
            Created user with ID assigned
        """
        payload = entity.to_api_payload()
        data = self._client.create_user(payload)

        created = BillUser.from_bill_api(data)

        # Cache email -> id mapping
        if created.email and created.id:
            self._email_cache[created.email.lower()] = created.id

        logger.info(f"Created S&E user: {created.email} ({created.id})")
        return created

    def update(self, entity: BillUser) -> BillUser:
        """
        Update existing user in BILL.

        Args:
            entity: User with updated data (must have ID)

        Returns:
            Updated user
        """
        if not entity.id:
            raise ValueError("Cannot update user without ID")

        payload = entity.to_api_payload()
        data = self._client.update_user(entity.id, payload)

        # Handle 204 No Content response
        if not data:
            # Re-fetch to get updated data
            data = self._client.get_user(entity.id)

        updated = BillUser.from_bill_api(data) if data else entity
        logger.info(f"Updated S&E user: {updated.email} ({updated.id})")
        return updated

    def delete(self, entity_id: str) -> bool:
        """
        Delete (retire) a user.

        Args:
            entity_id: User ID to delete

        Returns:
            True if deleted
        """
        result = self._client.retire_user(entity_id)
        if result:
            logger.info(f"Retired S&E user: {entity_id}")
        return result

    def retire_user(self, user_id: str) -> bool:
        """
        Retire (deactivate) a user.

        Args:
            user_id: User ID to retire

        Returns:
            True if retired, False if not found
        """
        return self.delete(user_id)

    def upsert(self, user: BillUser) -> tuple[BillUser, str]:
        """
        Create or update a user based on email lookup.

        Handles the "User already exists" error gracefully by retrying lookup.

        Args:
            user: User data

        Returns:
            Tuple of (BillUser, action) where action is 'created', 'updated', or 'skipped'
        """
        # Look up existing user by email
        existing = self.get_by_email(user.email)

        if existing:
            # Update existing user
            user.id = existing.id
            updated = self.update(user)
            return (updated, "updated")

        # Try to create new user
        try:
            created = self.create(user)
            return (created, "created")
        except Exception as e:
            error_msg = str(e).lower()
            response_body = ""
            if hasattr(e, "response_body") and e.response_body:
                response_body = str(e.response_body).lower()
            combined_error = error_msg + " " + response_body

            # Handle "User already exists" error
            if "already exists" in combined_error:
                logger.warning(
                    f"User {user.email} already exists (API error), retrying lookup..."
                )
                # Clear cache and try to find the user
                self.clear_cache()
                existing = self.get_by_email(user.email)

                if existing:
                    logger.info(f"Found user {user.email} on retry, updating...")
                    user.id = existing.id
                    updated = self.update(user)
                    return (updated, "updated")
                else:
                    # User exists but we can't fetch - skip (cannot update without ID)
                    logger.warning(
                        f"User {user.email} exists in BILL but cannot be fetched. "
                        f"Skipping update (user data remains unchanged in BILL)."
                    )
                    return (user, "skipped")

            # Re-raise other errors
            raise

    def upsert_from_employee(
        self,
        employee: "Employee",  # Forward reference
        role: Optional["BillRole"] = None,
        manager_email: Optional[str] = None,
    ) -> BillUser:
        """
        Upsert user from Employee domain model.

        Args:
            employee: Source Employee
            role: Optional role override
            manager_email: Optional manager email override

        Returns:
            Created or updated BillUser
        """
        from src.domain.models.bill_user import BillRole
        from src.domain.models.employee import Employee

        user = BillUser.from_employee(
            employee,
            role=role,
            manager_email=manager_email,
        )
        return self.upsert(user)

    def clear_cache(self) -> None:
        """Clear the email cache."""
        self._email_cache.clear()

    def build_email_cache(self) -> None:
        """
        Pre-populate email cache from all users.

        Useful before batch operations to reduce API calls.
        """
        logger.info("Building email cache from BILL.com users...")
        all_users = self._client.get_all_users()
        cached_count = 0
        for data in all_users:
            email = data.get("email", "").lower().strip()
            user_id = data.get("id") or data.get("uuid")
            if email and user_id:
                self._email_cache[email] = user_id
                cached_count += 1

        logger.info(
            f"Email cache built: {cached_count} users cached "
            f"(from {len(all_users)} total users)"
        )
