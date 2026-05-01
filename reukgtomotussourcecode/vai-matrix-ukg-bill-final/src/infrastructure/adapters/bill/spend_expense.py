"""
BILL.com Spend & Expense repository implementation.

This module implements the BillUserRepository interface using the S&E API client.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

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
        self._full_user_cache: Dict[str, Dict[str, Any]] = {}  # email -> full user data

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
        email_lower = user.email.lower().strip() if user.email else ""
        cache_size = len(self._email_cache)
        in_cache = email_lower in self._email_cache

        logger.debug(
            f"UPSERT START: email={user.email}, external_id={user.external_id}, "
            f"role={user.role.value if user.role else 'None'}, "
            f"cache_size={cache_size}, in_cache={in_cache}"
        )

        # Look up existing user by email
        existing = self.get_by_email(user.email)

        if existing:
            # Update existing user
            logger.debug(
                f"UPSERT: Found existing user {user.email} with id={existing.id}, "
                f"proceeding with UPDATE (PATCH)"
            )
            user.id = existing.id
            updated = self.update(user)
            return (updated, "updated")

        logger.debug(
            f"UPSERT: User {user.email} not found in BILL.com, "
            f"proceeding with CREATE (POST)"
        )

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
                    f"CREATE FAILED - 'User already exists' error for {user.email}. "
                    f"This indicates a cache/lookup mismatch. "
                    f"Details: external_id={user.external_id}, cache_size={cache_size}, "
                    f"was_in_cache={in_cache}, error={str(e)[:200]}"
                )
                # Clear cache and try to find the user
                self.clear_cache()
                logger.info(f"Cache cleared, retrying email lookup for {user.email}...")
                existing = self.get_by_email(user.email)

                # Fallback: try to find by external ID if email lookup fails
                if not existing and user.external_id:
                    logger.info(
                        f"Email lookup failed for {user.email}, "
                        f"trying external_id lookup: {user.external_id}"
                    )
                    data = self._client.search_user_by_external_id(user.external_id)
                    if data:
                        existing = BillUser.from_bill_api(data)
                        logger.info(
                            f"Found user by external_id: {user.external_id} -> "
                            f"bill_id={existing.id}, bill_email={existing.email}"
                        )

                if existing:
                    logger.info(
                        f"RECOVERY SUCCESS: Found user {user.email} on retry "
                        f"(bill_id={existing.id}), proceeding with UPDATE"
                    )
                    user.id = existing.id
                    updated = self.update(user)
                    return (updated, "updated")
                else:
                    # User exists but we can't fetch - skip (cannot update without ID)
                    logger.error(
                        f"RECOVERY FAILED: User {user.email} exists in BILL.com "
                        f"(per API error) but cannot be fetched via email or external_id. "
                        f"external_id={user.external_id}. "
                        f"User data will NOT be synced. Manual intervention may be required."
                    )
                    return (user, "skipped")

            # Re-raise other errors with context
            logger.error(
                f"CREATE FAILED for {user.email}: {str(e)}. "
                f"external_id={user.external_id}, role={user.role.value if user.role else 'None'}"
            )
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

    def build_email_cache(self) -> Dict[str, Dict[str, Any]]:
        """
        Pre-populate email cache from all users using cursor pagination.

        Populates both _email_cache (email -> user_id) and
        _full_user_cache (email -> full user data) for efficient
        categorization of employees.

        Returns:
            Dict mapping email -> full user data
        """
        logger.info("Building email cache from BILL.com users (cursor pagination)...")
        all_users = self._client.get_all_users()

        # Clear existing caches
        self._email_cache.clear()
        self._full_user_cache.clear()

        cached_count = 0
        skipped_no_email = 0
        skipped_no_id = 0

        for data in all_users:
            email = data.get("email", "").lower().strip()
            # Use uuid (e.g., "usr_xxx") for API operations, fallback to id
            user_id = data.get("uuid") or data.get("id")

            if not email:
                skipped_no_email += 1
                continue
            if not user_id:
                skipped_no_id += 1
                logger.debug(f"User with email {email} has no ID, skipping cache")
                continue

            self._email_cache[email] = user_id
            self._full_user_cache[email] = data
            cached_count += 1

        logger.info(
            f"Email cache built: {cached_count} users cached "
            f"(from {len(all_users)} total users, "
            f"skipped: {skipped_no_email} no email, {skipped_no_id} no id)"
        )

        # Warn if cache is empty but users were fetched
        if len(all_users) > 0 and cached_count == 0:
            logger.warning(
                "WARNING: Fetched users from BILL.com but cache is empty! "
                "Check if response format has changed (email/id fields missing)"
            )

        # Warn if no users were fetched at all
        if len(all_users) == 0:
            logger.warning(
                "WARNING: No users fetched from BILL.com! "
                "All employees will be categorized as 'to create'"
            )

        return self._full_user_cache

    def categorize_employees(
        self,
        ukg_employees: List["Employee"],  # Forward reference
    ) -> Tuple[List["Employee"], List[Tuple["Employee", str]]]:
        """
        Categorize UKG employees into those needing POST vs PATCH.

        Compares UKG employee emails against cached Bill users to determine
        which employees need to be created (POST) vs updated (PATCH).

        Args:
            ukg_employees: List of employees from UKG

        Returns:
            Tuple of:
            - employees_to_create: List[Employee] not in Bill (need POST)
            - employees_to_update: List[Tuple[Employee, bill_user_id]] in Bill (need PATCH)
        """
        from src.domain.models.employee import Employee

        # Ensure cache is populated
        if not self._email_cache:
            self.build_email_cache()

        logger.info(f"Categorizing {len(ukg_employees)} UKG employees against {len(self._email_cache)} cached BILL users")

        employees_to_create: List[Employee] = []
        employees_to_update: List[Tuple[Employee, str]] = []

        # Log first few cached emails for debugging
        if self._email_cache:
            sample_cached = list(self._email_cache.keys())[:5]
            logger.debug(f"Sample cached emails: {sample_cached}")

        for employee in ukg_employees:
            if not employee.email:
                logger.debug(
                    f"Employee {employee.employee_number} skipped: missing email"
                )
                continue

            email_lower = employee.email.lower().strip()

            if email_lower in self._email_cache:
                bill_user_id = self._email_cache[email_lower]
                employees_to_update.append((employee, bill_user_id))
            else:
                employees_to_create.append(employee)

        logger.info(
            f"Categorization complete: {len(employees_to_create)} to create (POST), "
            f"{len(employees_to_update)} to update (PATCH)"
        )

        # Warn if all employees are being created (suspicious if cache has users)
        if len(employees_to_create) > 0 and len(employees_to_update) == 0 and len(self._email_cache) > 0:
            # Log a sample of emails being created vs cached for debugging
            sample_create = [e.email.lower().strip() for e in employees_to_create[:3] if e.email]
            sample_cached = list(self._email_cache.keys())[:3]
            logger.warning(
                f"WARNING: All employees categorized as 'create' but cache has {len(self._email_cache)} users! "
                f"Sample UKG emails: {sample_create}, Sample cached emails: {sample_cached}"
            )

        return employees_to_create, employees_to_update
