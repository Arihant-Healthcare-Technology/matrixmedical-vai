"""
Integration tests for BILL.com Spend & Expense API client.

Tests verify BILL S&E client behavior with mocked HTTP responses.
Run with: pytest tests/integration/test_bill_se_integration.py -v -m integration
"""
from unittest.mock import patch, MagicMock

import pytest
import responses

from src.infrastructure.adapters.bill.spend_expense import BillSpendExpenseClient
from src.domain.exceptions.api_exceptions import BillApiError


@pytest.mark.integration
class TestBillSEAuthentication:
    """Test BILL S&E client authentication."""

    def test_bill_se_authentication_valid_token(self, mock_bill_se_settings):
        """Test authentication with valid API token."""
        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        headers = client._headers()

        assert "apiToken" in headers
        assert headers["apiToken"] == "test_se_token"

    def test_bill_se_authentication_missing_token_raises_error(self):
        """Test that missing API token raises error."""
        settings = MagicMock()
        settings.api_base = "https://gateway.stage.bill.com/connect/v3/spend"
        settings.api_token = MagicMock()
        settings.api_token.get_secret_value.return_value = ""
        settings.timeout = 30.0

        with pytest.raises(BillApiError, match="Missing BILL_SE_API_TOKEN"):
            client = BillSpendExpenseClient(settings=settings)
            client._headers()


@pytest.mark.integration
class TestBillSEGetUser:
    """Test BILL S&E user retrieval operations."""

    @responses.activate
    def test_bill_se_get_user_by_email(
        self, mock_bill_se_settings, sample_bill_user_list_response, bill_se_base_url
    ):
        """Test fetching user by email."""
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users",
            json=sample_bill_user_list_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.get_user_by_email("john.doe@example.com")

        assert result is not None
        assert result["email"] == "john.doe@example.com"

    @responses.activate
    def test_bill_se_get_user_by_email_not_found(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test fetching user by email when not found."""
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users",
            json={"users": [], "pagination": {"totalCount": 0}},
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.get_user_by_email("nonexistent@example.com")

        assert result is None

    @responses.activate
    def test_bill_se_get_user_by_id(
        self, mock_bill_se_settings, sample_bill_user_response, bill_se_base_url
    ):
        """Test fetching user by UUID."""
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users/usr_12345",
            json=sample_bill_user_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.get_user_by_id("usr_12345")

        assert result is not None
        assert result["uuid"] == "usr_12345"

    @responses.activate
    def test_bill_se_get_user_by_id_not_found(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test fetching user by UUID when not found."""
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users/usr_nonexistent",
            json={"error": "User not found"},
            status=404,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.get_user_by_id("usr_nonexistent")

        assert result is None


@pytest.mark.integration
class TestBillSECreateUser:
    """Test BILL S&E user creation operations."""

    @responses.activate
    def test_bill_se_create_user(
        self, mock_bill_se_settings, sample_bill_user_response,
        sample_bill_user_create_payload, bill_se_base_url
    ):
        """Test creating a new user."""
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json=sample_bill_user_response,
            status=201,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.create_user(sample_bill_user_create_payload)

        assert result is not None
        assert result["uuid"] == "usr_12345"
        assert result["email"] == "john.doe@example.com"

    @responses.activate
    def test_bill_se_create_user_validation_error(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test creating user with validation error."""
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json={"error": "Invalid email format"},
            status=400,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.create_user({"email": "invalid-email"})

        assert exc_info.value.status_code == 400

    @responses.activate
    def test_bill_se_create_user_duplicate(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test creating duplicate user returns conflict."""
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json={"error": "User already exists"},
            status=409,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.create_user({"email": "existing@example.com"})

        assert exc_info.value.status_code == 409


@pytest.mark.integration
class TestBillSEUpdateUser:
    """Test BILL S&E user update operations."""

    @responses.activate
    def test_bill_se_update_user(
        self, mock_bill_se_settings, sample_bill_user_response, bill_se_base_url
    ):
        """Test updating an existing user."""
        updated_response = {**sample_bill_user_response, "lastName": "Smith"}
        responses.add(
            responses.PATCH,
            f"{bill_se_base_url}/users/usr_12345",
            json=updated_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.update_user("usr_12345", {"lastName": "Smith"})

        assert result is not None
        assert result["lastName"] == "Smith"

    @responses.activate
    def test_bill_se_update_user_not_found(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test updating non-existent user."""
        responses.add(
            responses.PATCH,
            f"{bill_se_base_url}/users/usr_nonexistent",
            json={"error": "User not found"},
            status=404,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.update_user("usr_nonexistent", {"lastName": "Smith"})

        assert exc_info.value.status_code == 404


@pytest.mark.integration
class TestBillSEUpsertUser:
    """Test BILL S&E user upsert operations."""

    @responses.activate
    def test_bill_se_upsert_user_create(
        self, mock_bill_se_settings, sample_bill_user_response,
        sample_bill_user_create_payload, bill_se_base_url
    ):
        """Test upsert creates user when not exists."""
        # First check if user exists (returns empty)
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users",
            json={"users": [], "pagination": {"totalCount": 0}},
            status=200,
        )
        # Then create the user
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json=sample_bill_user_response,
            status=201,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.upsert_user(sample_bill_user_create_payload)

        assert result["action"] == "created"
        assert result["uuid"] == "usr_12345"

    @responses.activate
    def test_bill_se_upsert_user_update(
        self, mock_bill_se_settings, sample_bill_user_response,
        sample_bill_user_list_response, sample_bill_user_create_payload, bill_se_base_url
    ):
        """Test upsert updates user when exists."""
        # First check if user exists (returns user)
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users",
            json=sample_bill_user_list_response,
            status=200,
        )
        # Then update the user
        responses.add(
            responses.PATCH,
            f"{bill_se_base_url}/users/usr_12345",
            json=sample_bill_user_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.upsert_user(sample_bill_user_create_payload)

        assert result["action"] == "updated"
        assert result["uuid"] == "usr_12345"


@pytest.mark.integration
class TestBillSERateLimiting:
    """Test BILL S&E rate limiting behavior."""

    @responses.activate
    def test_bill_se_rate_limiting_429(
        self, mock_bill_se_settings, sample_bill_user_response, bill_se_base_url
    ):
        """Test handling of 429 Too Many Requests."""
        # First request returns 429
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users/usr_12345",
            json={"error": "Too Many Requests"},
            status=429,
            headers={"Retry-After": "1"},
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users/usr_12345",
            json=sample_bill_user_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.get_user_by_id("usr_12345")

        assert result is not None
        assert len(responses.calls) == 2

    @responses.activate
    def test_bill_se_rate_limiting_max_retries_exceeded(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test that max retries exceeded raises error."""
        # All requests return 429
        for _ in range(5):
            responses.add(
                responses.GET,
                f"{bill_se_base_url}/users/usr_12345",
                json={"error": "Too Many Requests"},
                status=429,
                headers={"Retry-After": "1"},
            )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        with pytest.raises(BillApiError):
            client.get_user_by_id("usr_12345")


@pytest.mark.integration
class TestBillSEUserRoles:
    """Test BILL S&E user role operations."""

    @responses.activate
    def test_bill_se_user_roles_member(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test creating user with MEMBER role."""
        response = {
            "uuid": "usr_member",
            "email": "member@example.com",
            "role": "MEMBER",
        }
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json=response,
            status=201,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.create_user({
            "email": "member@example.com",
            "firstName": "Test",
            "lastName": "Member",
            "role": "MEMBER",
        })

        assert result["role"] == "MEMBER"

    @responses.activate
    def test_bill_se_user_roles_admin(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test creating user with ADMIN role."""
        response = {
            "uuid": "usr_admin",
            "email": "admin@example.com",
            "role": "ADMIN",
        }
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json=response,
            status=201,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.create_user({
            "email": "admin@example.com",
            "firstName": "Test",
            "lastName": "Admin",
            "role": "ADMIN",
        })

        assert result["role"] == "ADMIN"

    @responses.activate
    def test_bill_se_invalid_token(
        self, mock_bill_se_settings, bill_se_base_url
    ):
        """Test handling of invalid API token."""
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users/current",
            json={"error": "Unauthorized"},
            status=401,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.get_current_user()

        assert exc_info.value.status_code == 401


@pytest.mark.integration
class TestBillSERetireUser:
    """Test BILL S&E user retirement operations."""

    @responses.activate
    def test_bill_se_retire_user(
        self, mock_bill_se_settings, sample_bill_user_response, bill_se_base_url
    ):
        """Test retiring a user."""
        retired_response = {**sample_bill_user_response, "retired": True}
        responses.add(
            responses.PATCH,
            f"{bill_se_base_url}/users/usr_12345",
            json=retired_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.update_user("usr_12345", {"retired": True})

        assert result["retired"] is True

    @responses.activate
    def test_bill_se_reactivate_user(
        self, mock_bill_se_settings, sample_bill_user_response, bill_se_base_url
    ):
        """Test reactivating a retired user."""
        active_response = {**sample_bill_user_response, "retired": False}
        responses.add(
            responses.PATCH,
            f"{bill_se_base_url}/users/usr_12345",
            json=active_response,
            status=200,
        )

        client = BillSpendExpenseClient(settings=mock_bill_se_settings)
        result = client.update_user("usr_12345", {"retired": False})

        assert result["retired"] is False
