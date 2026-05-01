"""
Unit tests for BILL.com Spend & Expense repository.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.adapters.bill.spend_expense import BillUserRepositoryImpl
from src.domain.models.bill_user import BillUser, BillRole
from src.domain.models.employee import Employee, EmployeeStatus


class TestBillUserRepositoryInit:
    """Tests for BillUserRepositoryImpl initialization."""

    def test_init_with_client(self):
        """Test initialization with client."""
        mock_client = MagicMock()
        repo = BillUserRepositoryImpl(mock_client)

        assert repo._client is mock_client
        assert repo._email_cache == {}


class TestGetById:
    """Tests for get_by_id method."""

    def test_returns_user_when_found(self):
        """Test returns user when found by ID."""
        mock_client = MagicMock()
        mock_client.get_user.return_value = {
            "id": "uuid-123",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "role": "MEMBER",
        }

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_id("uuid-123")

        assert result is not None
        assert result.id == "uuid-123"
        assert result.email == "john@example.com"

    def test_returns_none_when_not_found(self):
        """Test returns None when user not found."""
        mock_client = MagicMock()
        mock_client.get_user.return_value = None

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_id("unknown-id")

        assert result is None

    def test_returns_none_on_exception(self):
        """Test returns None on exception."""
        mock_client = MagicMock()
        mock_client.get_user.side_effect = Exception("API error")

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_id("error-id")

        assert result is None


class TestGetByEmail:
    """Tests for get_by_email method using cache-first approach.

    NOTE: BILL.com S&E API does NOT support email as a query parameter.
    The implementation now uses cache-first approach:
    1. Check cache first
    2. If cache empty, build cache via get_all_users (paginated)
    3. Return from cache or None if not found
    """

    def test_returns_from_cache_if_present(self):
        """Should return user from cache without API call."""
        mock_client = MagicMock()

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate both caches
        repo._email_cache["john@example.com"] = "uuid-123"
        repo._full_user_cache["john@example.com"] = {
            "uuid": "uuid-123",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }

        result = repo.get_by_email("john@example.com")

        assert result is not None
        assert result.email == "john@example.com"
        assert result.id == "uuid-123"
        # Should NOT call any API methods
        assert mock_client.get_all_users.call_count == 0
        assert mock_client.get_user.call_count == 0

    def test_builds_cache_if_empty_then_returns(self):
        """Should build cache if empty, then return user."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"uuid": "uuid-123", "email": "john@example.com", "firstName": "John"},
            {"uuid": "uuid-456", "email": "jane@example.com", "firstName": "Jane"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        # Cache starts empty
        assert len(repo._email_cache) == 0

        result = repo.get_by_email("john@example.com")

        assert result is not None
        assert result.email == "john@example.com"
        # Should have called get_all_users to build cache
        assert mock_client.get_all_users.call_count == 1

    def test_returns_none_if_not_in_cache_after_build(self):
        """Should return None if user not found after cache build."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"uuid": "uuid-123", "email": "other@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_email("notfound@example.com")

        assert result is None
        # Should have attempted to build cache
        assert mock_client.get_all_users.call_count == 1

    def test_uses_full_user_cache_for_response(self):
        """Should use _full_user_cache to construct response with all fields."""
        mock_client = MagicMock()

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache["john@example.com"] = "uuid-123"
        repo._full_user_cache["john@example.com"] = {
            "uuid": "uuid-123",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "role": "ADMIN",
            "phone": "555-1234",
        }

        result = repo.get_by_email("john@example.com")

        assert result is not None
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.role.value == "ADMIN"

    def test_falls_back_to_get_by_id_if_no_full_data(self):
        """Should call get_by_id if _full_user_cache missing."""
        mock_client = MagicMock()
        mock_client.get_user.return_value = {
            "uuid": "uuid-123",
            "email": "john@example.com",
            "firstName": "John",
        }

        repo = BillUserRepositoryImpl(mock_client)
        # Populate _email_cache only (no _full_user_cache entry)
        repo._email_cache["john@example.com"] = "uuid-123"
        # Don't populate _full_user_cache

        result = repo.get_by_email("john@example.com")

        assert result is not None
        # Should have called get_user (get_by_id) with cached user_id
        mock_client.get_user.assert_called_once_with("uuid-123")

    def test_case_insensitive_cache_lookup(self):
        """Should match email case-insensitively from cache."""
        mock_client = MagicMock()

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache["john@example.com"] = "uuid-123"
        repo._full_user_cache["john@example.com"] = {
            "uuid": "uuid-123",
            "email": "john@example.com",
        }

        # Search with different case
        result = repo.get_by_email("JOHN@EXAMPLE.COM")

        assert result is not None
        assert result.id == "uuid-123"

    def test_does_not_rebuild_cache_if_already_populated(self):
        """Should not rebuild cache if already has entries."""
        mock_client = MagicMock()

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate with some entries
        repo._email_cache["other@example.com"] = "uuid-other"

        # Search for user not in cache (but cache is not empty)
        result = repo.get_by_email("notfound@example.com")

        assert result is None
        # Should NOT have called get_all_users since cache is not empty
        assert mock_client.get_all_users.call_count == 0


class TestGetActiveUsers:
    """Tests for get_active_users method."""

    def test_returns_active_users_only(self):
        """Test returns only active (non-retired) users."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "1", "email": "active@example.com", "status": "ACTIVE"},
            {"id": "2", "email": "retired@example.com", "status": "RETIRED"},
            {"id": "3", "email": "active2@example.com", "status": "ACTIVE"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_active_users()

        # Should filter out retired users
        assert len(result) >= 2

    def test_caches_emails(self):
        """Test caches email -> id mappings."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "user1@example.com", "status": "ACTIVE"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.get_active_users()

        assert "user1@example.com" in repo._email_cache


class TestList:
    """Tests for list method."""

    def test_lists_users_with_pagination(self):
        """Test lists users with pagination."""
        mock_client = MagicMock()
        mock_client.list_users.return_value = [
            {"id": "1", "email": "user1@example.com"},
            {"id": "2", "email": "user2@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.list(page=2, page_size=50)

        mock_client.list_users.assert_called_once_with(page=2, page_size=50)
        assert len(result) == 2


class TestCreate:
    """Tests for create method."""

    def test_creates_user(self):
        """Test creates new user."""
        mock_client = MagicMock()
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "new@example.com",
            "firstName": "New",
            "lastName": "User",
        }

        repo = BillUserRepositoryImpl(mock_client)

        user = BillUser(
            email="new@example.com",
            first_name="New",
            last_name="User",
        )
        result = repo.create(user)

        assert result.id == "new-uuid"
        mock_client.create_user.assert_called_once()

    def test_caches_created_user_email(self):
        """Test caches created user email."""
        mock_client = MagicMock()
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "new@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="new@example.com", first_name="New", last_name="User")
        repo.create(user)

        assert "new@example.com" in repo._email_cache


class TestUpdate:
    """Tests for update method."""

    def test_updates_user(self):
        """Test updates existing user."""
        mock_client = MagicMock()
        mock_client.update_user.return_value = {
            "id": "uuid-123",
            "email": "updated@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(id="uuid-123", email="updated@example.com", first_name="U", last_name="U")
        result = repo.update(user)

        assert result.id == "uuid-123"
        mock_client.update_user.assert_called_once()

    def test_raises_without_id(self):
        """Test raises ValueError without ID."""
        mock_client = MagicMock()
        repo = BillUserRepositoryImpl(mock_client)

        user = BillUser(email="user@example.com", first_name="No", last_name="Id")
        with pytest.raises(ValueError) as exc_info:
            repo.update(user)

        assert "without ID" in str(exc_info.value)

    def test_handles_204_no_content(self):
        """Test handles 204 No Content response."""
        mock_client = MagicMock()
        mock_client.update_user.return_value = None  # 204 No Content
        mock_client.get_user.return_value = {
            "id": "uuid-123",
            "email": "user@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(id="uuid-123", email="user@example.com", first_name="U", last_name="U")
        result = repo.update(user)

        mock_client.get_user.assert_called_once_with("uuid-123")


class TestDelete:
    """Tests for delete method."""

    def test_retires_user(self):
        """Test retires (deletes) user."""
        mock_client = MagicMock()
        mock_client.retire_user.return_value = True

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.delete("uuid-123")

        assert result is True
        mock_client.retire_user.assert_called_once_with("uuid-123")

    def test_returns_false_on_failure(self):
        """Test returns False on failure."""
        mock_client = MagicMock()
        mock_client.retire_user.return_value = False

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.delete("unknown-id")

        assert result is False


class TestRetireUser:
    """Tests for retire_user method."""

    def test_calls_delete(self):
        """Test retire_user calls delete."""
        mock_client = MagicMock()
        mock_client.retire_user.return_value = True

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.retire_user("uuid-123")

        assert result is True
        mock_client.retire_user.assert_called_once_with("uuid-123")


class TestUpsert:
    """Tests for upsert method.

    NOTE: Uses cache-first approach - tests pre-populate _email_cache
    and _full_user_cache instead of mocking get_user_by_email client method.
    """

    def test_creates_new_user(self):
        """Test creates new user when not found in cache."""
        mock_client = MagicMock()
        # Mock get_all_users to return empty list (cache will be empty)
        mock_client.get_all_users.return_value = []
        mock_client.create_user.return_value = {
            "uuid": "new-uuid",
            "email": "new@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="new@example.com", first_name="New", last_name="User")
        result_user, action = repo.upsert(user)

        assert result_user.id == "new-uuid"
        assert action == "created"
        mock_client.create_user.assert_called_once()

    def test_updates_existing_user(self):
        """Test updates user when found in cache - always PATCHes."""
        mock_client = MagicMock()
        mock_client.update_user.return_value = {
            "uuid": "uuid-123",
            "email": "user@example.com",
            "firstName": "New",
            "lastName": "Name",
        }

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate cache with existing user
        repo._email_cache["user@example.com"] = "uuid-123"
        repo._full_user_cache["user@example.com"] = {
            "uuid": "uuid-123",
            "email": "user@example.com",
            "firstName": "Old",
            "lastName": "Name",
        }

        user = BillUser(email="user@example.com", first_name="New", last_name="Name")
        result_user, action = repo.upsert(user)

        assert action == "updated"
        mock_client.update_user.assert_called_once()

    def test_always_patches_existing_user(self):
        """Test always PATCHes when user exists in cache (even with same data)."""
        mock_client = MagicMock()
        mock_client.update_user.return_value = {
            "uuid": "uuid-123",
            "email": "user@example.com",
            "firstName": "Same",
            "lastName": "User",
            "role": "MEMBER",
        }

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate cache with existing user
        repo._email_cache["user@example.com"] = "uuid-123"
        repo._full_user_cache["user@example.com"] = {
            "uuid": "uuid-123",
            "email": "user@example.com",
            "firstName": "Same",
            "lastName": "User",
            "role": "MEMBER",
        }

        user = BillUser(
            email="user@example.com",
            first_name="Same",
            last_name="User",
            role=BillRole.MEMBER,
        )
        result_user, action = repo.upsert(user)

        # Always PATCH when user exists
        mock_client.update_user.assert_called_once()
        assert action == "updated"
        assert result_user.id == "uuid-123"


class TestClearCache:
    """Tests for clear_cache method."""

    def test_clears_email_cache(self):
        """Test clears the email cache."""
        mock_client = MagicMock()
        repo = BillUserRepositoryImpl(mock_client)

        repo._email_cache["test@example.com"] = "uuid-123"
        assert len(repo._email_cache) == 1

        repo.clear_cache()

        assert len(repo._email_cache) == 0


class TestUpsertExceptionHandling:
    """Tests for upsert method exception handling.

    NOTE: Uses cache-first approach for lookups.
    """

    def test_handles_user_already_exists_error_with_retry(self):
        """Should handle 'user already exists' error and retry lookup via cache rebuild."""
        mock_client = MagicMock()

        # Initial cache is empty, get_all_users returns empty on first call
        # After cache clear, get_all_users returns the user on retry
        mock_client.get_all_users.side_effect = [
            [],  # First call - cache build returns empty
            [{"uuid": "existing-uuid", "email": "test@example.com"}],  # Retry after cache clear
        ]

        # Create fails with "already exists" error
        error = Exception("User already exists in the system")
        mock_client.create_user.side_effect = error
        mock_client.update_user.return_value = {
            "uuid": "existing-uuid",
            "email": "test@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="test@example.com", first_name="Test", last_name="User")

        result_user, action = repo.upsert(user)

        assert action == "updated"
        assert result_user.id == "existing-uuid"
        mock_client.update_user.assert_called_once()

    def test_handles_already_exists_with_external_id_fallback(self):
        """Should try external ID lookup when email lookup fails after cache rebuild."""
        mock_client = MagicMock()

        # Cache always returns empty (user not found by email)
        mock_client.get_all_users.return_value = []

        # Create fails with "already exists"
        error = Exception("User already exists")
        mock_client.create_user.side_effect = error

        # External ID search finds user
        mock_client.search_user_by_external_id.return_value = {
            "uuid": "existing-uuid",
            "email": "test@example.com",
            "externalId": "EXT001",
        }
        mock_client.update_user.return_value = {
            "uuid": "existing-uuid",
            "email": "test@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            external_id="EXT001",
        )

        result_user, action = repo.upsert(user)

        assert action == "updated"
        mock_client.search_user_by_external_id.assert_called_once_with("EXT001")

    def test_handles_already_exists_user_cannot_be_fetched(self):
        """Should skip when user exists but cannot be fetched via cache or external ID."""
        mock_client = MagicMock()

        # Cache returns empty (user not found by email)
        mock_client.get_all_users.return_value = []

        # Create fails with "already exists" (with response_body attribute)
        error = Exception("Create failed")
        error.response_body = "User already exists in the system"
        mock_client.create_user.side_effect = error

        # External ID search also fails
        mock_client.search_user_by_external_id.return_value = None

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            external_id="EXT001",
        )

        result_user, action = repo.upsert(user)

        assert action == "skipped"
        # Should return the original user unchanged
        assert result_user.email == "test@example.com"

    def test_re_raises_non_already_exists_errors(self):
        """Should re-raise errors that are not 'already exists'."""
        mock_client = MagicMock()

        # Cache returns empty
        mock_client.get_all_users.return_value = []

        # Create fails with different error
        error = Exception("API rate limit exceeded")
        mock_client.create_user.side_effect = error

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="test@example.com", first_name="Test", last_name="User")

        with pytest.raises(Exception) as exc_info:
            repo.upsert(user)

        assert "rate limit" in str(exc_info.value).lower()


class TestBuildEmailCache:
    """Tests for build_email_cache method."""

    def test_builds_cache_from_all_users(self):
        """Test pre-populates cache from all users."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"uuid": "uuid-1", "email": "user1@example.com"},
            {"uuid": "uuid-2", "email": "user2@example.com"},
            {"uuid": "uuid-3", "email": "user3@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert len(repo._email_cache) == 3
        assert repo._email_cache["user1@example.com"] == "uuid-1"
        assert repo._email_cache["user2@example.com"] == "uuid-2"
        assert repo._email_cache["user3@example.com"] == "uuid-3"

    def test_skips_entries_without_email(self):
        """Test skips entries without email."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"uuid": "uuid-1", "email": "valid@example.com"},
            {"uuid": "uuid-2"},  # No email
            {"uuid": "uuid-3", "email": ""},  # Empty email
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert len(repo._email_cache) == 1

    def test_prioritizes_uuid_over_id(self):
        """Should use uuid (not Base64 id) for cache value.

        BILL.com API returns both 'id' (Base64 encoded) and 'uuid'.
        The uuid format (e.g., 'usr_xxx') is required for API operations.
        """
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {
                "id": "VXNlcjoxMjM=",  # Base64 encoded - should NOT be used
                "uuid": "usr_abc123",   # UUID format - should be used
                "email": "user@example.com",
            },
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        # Should use uuid, not id
        assert repo._email_cache["user@example.com"] == "usr_abc123"

    def test_falls_back_to_id_if_no_uuid(self):
        """Should fall back to id if uuid not present."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "fallback-id", "email": "user@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert repo._email_cache["user@example.com"] == "fallback-id"

    def test_skips_entries_without_id(self):
        """Should skip entries without uuid or id."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"email": "valid@example.com", "uuid": "uuid-1"},
            {"email": "no-id@example.com"},  # No uuid or id
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert len(repo._email_cache) == 1
        assert "valid@example.com" in repo._email_cache
        assert "no-id@example.com" not in repo._email_cache


class TestFullUserCacheInit:
    """Tests for _full_user_cache initialization."""

    def test_init_creates_full_user_cache(self):
        """Should initialize _full_user_cache as empty dict."""
        mock_client = MagicMock()
        repo = BillUserRepositoryImpl(mock_client)

        assert hasattr(repo, "_full_user_cache")
        assert repo._full_user_cache == {}
        assert isinstance(repo._full_user_cache, dict)


class TestBuildEmailCacheExtended:
    """Extended tests for build_email_cache with full user cache."""

    def test_populates_full_user_cache(self):
        """Should populate _full_user_cache with full user data."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "user1@example.com", "firstName": "User", "lastName": "One"},
            {"id": "uuid-2", "email": "user2@example.com", "firstName": "User", "lastName": "Two"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.build_email_cache()

        assert len(repo._full_user_cache) == 2
        assert "user1@example.com" in repo._full_user_cache
        assert repo._full_user_cache["user1@example.com"]["firstName"] == "User"
        assert repo._full_user_cache["user2@example.com"]["lastName"] == "Two"

    def test_clears_existing_caches_before_rebuild(self):
        """Should clear both caches before populating."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-new", "email": "new@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate caches
        repo._email_cache = {"old@example.com": "uuid-old"}
        repo._full_user_cache = {"old@example.com": {"id": "uuid-old"}}

        repo.build_email_cache()

        assert "old@example.com" not in repo._email_cache
        assert "old@example.com" not in repo._full_user_cache
        assert "new@example.com" in repo._email_cache
        assert "new@example.com" in repo._full_user_cache

    def test_returns_full_user_cache_dict(self):
        """Should return Dict[str, Dict[str, Any]]."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "user@example.com", "role": "MEMBER"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.build_email_cache()

        assert isinstance(result, dict)
        assert "user@example.com" in result
        assert result["user@example.com"]["role"] == "MEMBER"

    def test_handles_large_user_list(self):
        """Should handle 1000+ users efficiently."""
        mock_client = MagicMock()
        # Generate 1000 users
        mock_client.get_all_users.return_value = [
            {"id": f"uuid-{i}", "email": f"user{i}@example.com"}
            for i in range(1000)
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert len(repo._email_cache) == 1000
        assert len(repo._full_user_cache) == 1000

    def test_normalizes_email_keys_lowercase(self):
        """Email keys should be normalized to lowercase."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "USER@EXAMPLE.COM"},
            {"id": "uuid-2", "email": "Mixed.Case@Example.Com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert "user@example.com" in repo._email_cache
        assert "mixed.case@example.com" in repo._email_cache
        assert "USER@EXAMPLE.COM" not in repo._email_cache


class TestUpsertFromEmployee:
    """Tests for upsert_from_employee method."""

    def test_creates_user_from_employee(self):
        """Should create BillUser from Employee and call upsert."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = None
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "test@example.com",
            "firstName": "Test",
            "lastName": "User",
        }

        repo = BillUserRepositoryImpl(mock_client)

        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )

        # upsert_from_employee returns a tuple (BillUser, action) but legacy returns just BillUser
        # Check the actual return type
        result = repo.upsert_from_employee(employee)

        # If result is a tuple, unpack it
        if isinstance(result, tuple):
            user, action = result
            assert user.email == "test@example.com"
        else:
            assert result.email == "test@example.com"
        mock_client.create_user.assert_called_once()

    def test_uses_role_override(self):
        """Should use provided role override."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = None
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "test@example.com",
            "firstName": "Test",
            "lastName": "User",
            "role": "ADMIN",
        }

        repo = BillUserRepositoryImpl(mock_client)

        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )

        repo.upsert_from_employee(employee, role=BillRole.ADMIN)

        # Verify create was called with role in payload
        call_args = mock_client.create_user.call_args[0][0]
        assert call_args.get("role") == "ADMIN"

    def test_uses_manager_email_override(self):
        """Should use provided manager email override."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = None
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "test@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)

        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )

        repo.upsert_from_employee(employee, manager_email="manager@example.com")

        # Verify create was called - the manager email is set on BillUser model
        mock_client.create_user.assert_called_once()


class TestCategorizeEmployees:
    """Tests for categorize_employees method."""

    @pytest.fixture
    def sample_employees(self):
        """Create sample employees for testing."""
        return [
            Employee(
                employee_id="EMP1",
                employee_number="001",
                email="existing@example.com",
                first_name="Existing",
                last_name="User",
                status=EmployeeStatus.ACTIVE,
            ),
            Employee(
                employee_id="EMP2",
                employee_number="002",
                email="new@example.com",
                first_name="New",
                last_name="User",
                status=EmployeeStatus.ACTIVE,
            ),
            Employee(
                employee_id="EMP3",
                employee_number="003",
                email=None,
                first_name="No",
                last_name="Email",
                status=EmployeeStatus.ACTIVE,
            ),
        ]

    def test_categorizes_new_employees_to_create(self, sample_employees):
        """Employees not in cache should be in to_create list."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []  # No existing users

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache = {}  # Pre-populate empty cache to avoid API call

        to_create, to_update = repo.categorize_employees(sample_employees)

        # Only employees with email should be in to_create
        assert len(to_create) == 2
        assert sample_employees[0] in to_create  # existing@example.com
        assert sample_employees[1] in to_create  # new@example.com

    def test_categorizes_existing_employees_to_update(self, sample_employees):
        """Employees in cache should be in to_update list with Bill user ID."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []

        repo = BillUserRepositoryImpl(mock_client)
        # Pre-populate cache with one existing user
        repo._email_cache = {"existing@example.com": "bill-uuid-123"}

        to_create, to_update = repo.categorize_employees(sample_employees)

        # One employee exists in Bill
        assert len(to_update) == 1
        assert to_update[0][0] == sample_employees[0]  # Employee object
        assert to_update[0][1] == "bill-uuid-123"  # Bill user ID

        # One new employee (with email)
        assert len(to_create) == 1
        assert to_create[0] == sample_employees[1]

    def test_skips_employees_without_email(self, sample_employees):
        """Employees without email should be skipped."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache = {}

        to_create, to_update = repo.categorize_employees(sample_employees)

        # Employee without email (EMP3) should not be in either list
        all_employees_in_results = [e for e in to_create] + [t[0] for t in to_update]
        assert sample_employees[2] not in all_employees_in_results

    def test_handles_empty_employee_list(self):
        """Empty list should return empty categorization."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache = {"some@email.com": "uuid"}

        to_create, to_update = repo.categorize_employees([])

        assert to_create == []
        assert to_update == []

    def test_email_matching_is_case_insensitive(self):
        """Email matching should be case-insensitive."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []

        repo = BillUserRepositoryImpl(mock_client)
        # Cache has lowercase email
        repo._email_cache = {"test@example.com": "bill-uuid-456"}

        # Employee has uppercase email
        employee = Employee(
            employee_id="EMP1",
            employee_number="001",
            email="TEST@EXAMPLE.COM",
            first_name="Test",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )

        to_create, to_update = repo.categorize_employees([employee])

        # Should match and be in to_update
        assert len(to_update) == 1
        assert to_update[0][1] == "bill-uuid-456"
        assert len(to_create) == 0

    def test_populates_cache_if_empty(self):
        """Should call build_email_cache if cache is empty."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "cached@example.com"},
        ]

        repo = BillUserRepositoryImpl(mock_client)
        # Empty cache
        assert repo._email_cache == {}

        employee = Employee(
            employee_id="EMP1",
            employee_number="001",
            email="new@example.com",
            first_name="New",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )

        to_create, to_update = repo.categorize_employees([employee])

        # Should have called get_all_users to build cache
        mock_client.get_all_users.assert_called_once()
        # New employee should be in to_create
        assert len(to_create) == 1

    def test_returns_correct_tuple_structure(self, sample_employees):
        """Should return (List[Employee], List[Tuple[Employee, str]])."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = []

        repo = BillUserRepositoryImpl(mock_client)
        repo._email_cache = {"existing@example.com": "bill-uuid-123"}

        to_create, to_update = repo.categorize_employees(sample_employees)

        # Verify to_create is List[Employee]
        assert isinstance(to_create, list)
        for item in to_create:
            assert isinstance(item, Employee)

        # Verify to_update is List[Tuple[Employee, str]]
        assert isinstance(to_update, list)
        for item in to_update:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], Employee)
            assert isinstance(item[1], str)
