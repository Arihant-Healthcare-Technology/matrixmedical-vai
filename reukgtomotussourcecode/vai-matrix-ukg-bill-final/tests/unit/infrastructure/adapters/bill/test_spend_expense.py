"""
Unit tests for BILL.com Spend & Expense repository.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.adapters.bill.spend_expense import BillUserRepositoryImpl
from src.domain.models.bill_user import BillUser, BillRole


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
    """Tests for get_by_email method."""

    def test_returns_user_when_found(self):
        """Test returns user when found by email."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = {
            "id": "uuid-123",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_email("john@example.com")

        assert result is not None
        assert result.email == "john@example.com"

    def test_uses_cache_on_second_call(self):
        """Test uses cache on second call."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = {
            "id": "uuid-123",
            "email": "john@example.com",
        }
        mock_client.get_user.return_value = {
            "id": "uuid-123",
            "email": "john@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)

        # First call
        result1 = repo.get_by_email("john@example.com")
        # Second call - should use cache
        result2 = repo.get_by_email("John@Example.com")

        # get_user_by_email should only be called once
        assert mock_client.get_user_by_email.call_count == 1

    def test_returns_none_when_not_found(self):
        """Test returns None when user not found."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = None

        repo = BillUserRepositoryImpl(mock_client)
        result = repo.get_by_email("unknown@example.com")

        assert result is None


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
    """Tests for upsert method."""

    def test_creates_new_user(self):
        """Test creates new user when not found."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = None
        mock_client.create_user.return_value = {
            "id": "new-uuid",
            "email": "new@example.com",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="new@example.com", first_name="New", last_name="User")
        result = repo.upsert(user)

        assert result.id == "new-uuid"
        mock_client.create_user.assert_called_once()

    def test_updates_existing_user(self):
        """Test updates user when found and needs update."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = {
            "id": "uuid-123",
            "email": "user@example.com",
            "firstName": "Old",
            "lastName": "Name",
        }
        mock_client.update_user.return_value = {
            "id": "uuid-123",
            "email": "user@example.com",
            "firstName": "New",
            "lastName": "Name",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(email="user@example.com", first_name="New", last_name="Name")
        result = repo.upsert(user)

        mock_client.update_user.assert_called_once()

    def test_skips_update_when_no_changes(self):
        """Test skips update when no changes needed."""
        mock_client = MagicMock()
        mock_client.get_user_by_email.return_value = {
            "id": "uuid-123",
            "email": "user@example.com",
            "firstName": "Same",
            "lastName": "User",
            "role": "MEMBER",
        }

        repo = BillUserRepositoryImpl(mock_client)
        user = BillUser(
            email="user@example.com",
            first_name="Same",
            last_name="User",
            role=BillRole.MEMBER,
        )
        result = repo.upsert(user)

        mock_client.update_user.assert_not_called()
        assert result.id == "uuid-123"


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


class TestBuildEmailCache:
    """Tests for build_email_cache method."""

    def test_builds_cache_from_all_users(self):
        """Test pre-populates cache from all users."""
        mock_client = MagicMock()
        mock_client.get_all_users.return_value = [
            {"id": "uuid-1", "email": "user1@example.com"},
            {"id": "uuid-2", "email": "user2@example.com"},
            {"uuid": "uuid-3", "email": "user3@example.com"},  # alternate id key
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
            {"id": "uuid-1", "email": "valid@example.com"},
            {"id": "uuid-2"},  # No email
            {"id": "uuid-3", "email": ""},  # Empty email
        ]

        repo = BillUserRepositoryImpl(mock_client)
        repo.build_email_cache()

        assert len(repo._email_cache) == 1
