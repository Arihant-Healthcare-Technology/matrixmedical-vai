"""
Integration tests for TravelPerk SCIM API client.

Tests verify TravelPerk client behavior with mocked HTTP responses.
Run with: pytest tests/integration/test_travelperk_client_integration.py -v -m integration
"""
from unittest.mock import patch, MagicMock

import pytest
import responses

from src.infrastructure.adapters.travelperk.client import TravelPerkClient
from src.infrastructure.config.settings import TravelPerkSettings
from src.domain.models.travelperk_user import TravelPerkUser, UserName
from src.domain.exceptions.api_exceptions import TravelPerkApiError, RateLimitError


@pytest.fixture
def mock_travelperk_settings():
    """Create mock TravelPerk settings."""
    settings = MagicMock()
    settings.api_base = "https://app.sandbox-travelperk.com"
    settings.api_key = "test_api_key"
    settings.timeout = 60.0
    settings.max_retries = 2
    return settings


@pytest.fixture
def travelperk_base_url():
    """TravelPerk API base URL."""
    return "https://app.sandbox-travelperk.com"


@pytest.fixture
def sample_travelperk_user():
    """Create sample TravelPerk user."""
    return TravelPerkUser(
        external_id="12345",
        user_name="john.doe@example.com",
        name=UserName(given_name="John", family_name="Doe"),
        active=True,
        cost_center="PROJ001",
    )


@pytest.mark.integration
class TestTravelPerkAuthentication:
    """Test TravelPerk client authentication."""

    def test_travelperk_authentication_valid_key(self, mock_travelperk_settings):
        """Test authentication with valid API key."""
        client = TravelPerkClient(settings=mock_travelperk_settings)
        headers = client._headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "ApiKey test_api_key"

    def test_travelperk_authentication_missing_key_raises_error(self):
        """Test that missing API key raises error."""
        settings = MagicMock()
        settings.api_base = "https://app.sandbox-travelperk.com"
        settings.api_key = ""
        settings.timeout = 60.0

        client = TravelPerkClient(settings=settings)

        with pytest.raises(TravelPerkApiError, match="Missing TRAVELPERK_API_KEY"):
            client._headers()


@pytest.mark.integration
class TestTravelPerkGetUser:
    """Test TravelPerk user retrieval operations."""

    @responses.activate
    def test_travelperk_get_user_by_id(
        self, mock_travelperk_settings, sample_travelperk_user_response, travelperk_base_url
    ):
        """Test fetching user by TravelPerk ID."""
        user_id = sample_travelperk_user_response["id"]
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/{user_id}",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user(user_id)

        assert result is not None
        assert result["id"] == user_id

    @responses.activate
    def test_travelperk_get_user_by_id_not_found(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test fetching user by ID when not found."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/nonexistent",
            json={"error": "Not Found"},
            status=404,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user("nonexistent")

        assert result is None

    @responses.activate
    def test_travelperk_get_user_by_external_id(
        self, mock_travelperk_settings, sample_travelperk_scim_list_response, travelperk_base_url
    ):
        """Test fetching user by external ID."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_scim_list_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user_by_external_id("12345")

        assert result is not None
        assert result["externalId"] == "12345"

    @responses.activate
    def test_travelperk_get_user_by_external_id_not_found(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test fetching user by external ID when not found."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user_by_external_id("99999")

        assert result is None

    @responses.activate
    def test_travelperk_get_user_by_username(
        self, mock_travelperk_settings, sample_travelperk_scim_list_response, travelperk_base_url
    ):
        """Test fetching user by username (email)."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_scim_list_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user_by_user_name("john.doe@example.com")

        assert result is not None
        assert result["userName"] == "john.doe@example.com"


@pytest.mark.integration
class TestTravelPerkCreateUser:
    """Test TravelPerk user creation operations."""

    @responses.activate
    def test_travelperk_create_user_without_manager(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, travelperk_base_url
    ):
        """Test creating user without manager reference."""
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_user_response,
            status=201,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.create_user(sample_travelperk_user)

        assert result is not None
        assert result["id"] == "tp-user-123"

    @responses.activate
    def test_travelperk_create_user_with_manager(
        self, mock_travelperk_settings, sample_travelperk_user_response, travelperk_base_url
    ):
        """Test creating user with manager reference."""
        user_with_manager = TravelPerkUser(
            external_id="12345",
            user_name="john.doe@example.com",
            name=UserName(given_name="John", family_name="Doe"),
            active=True,
            cost_center="PROJ001",
            manager_id="tp-manager-123",
        )

        response_with_manager = {
            **sample_travelperk_user_response,
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "manager": {"value": "tp-manager-123"}
            }
        }
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=response_with_manager,
            status=201,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.create_user(user_with_manager)

        assert result is not None
        # Verify manager was included in request
        request_body = responses.calls[0].request.body
        assert "manager" in request_body

    @responses.activate
    def test_travelperk_create_user_validation_error(
        self, mock_travelperk_settings, sample_travelperk_user, travelperk_base_url
    ):
        """Test creating user with validation error."""
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"detail": "Invalid email format"},
            status=400,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)

        with pytest.raises(TravelPerkApiError) as exc_info:
            client.create_user(sample_travelperk_user)

        assert exc_info.value.status_code == 400


@pytest.mark.integration
class TestTravelPerkUpdateUser:
    """Test TravelPerk user update operations."""

    @responses.activate
    def test_travelperk_update_user_patch(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, travelperk_base_url
    ):
        """Test updating user with PATCH."""
        user_id = "tp-user-123"
        responses.add(
            responses.PATCH,
            f"{travelperk_base_url}/api/v2/scim/Users/{user_id}",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.update_user(user_id, sample_travelperk_user)

        assert result is not None

    @responses.activate
    def test_travelperk_update_user_not_found(
        self, mock_travelperk_settings, sample_travelperk_user, travelperk_base_url
    ):
        """Test updating non-existent user."""
        responses.add(
            responses.PATCH,
            f"{travelperk_base_url}/api/v2/scim/Users/nonexistent",
            json={"detail": "User not found"},
            status=404,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)

        with pytest.raises(TravelPerkApiError) as exc_info:
            client.update_user("nonexistent", sample_travelperk_user)

        assert exc_info.value.status_code == 404


@pytest.mark.integration
class TestTravelPerkUpsertUser:
    """Test TravelPerk user upsert operations."""

    @responses.activate
    def test_travelperk_upsert_user_create(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, travelperk_base_url
    ):
        """Test upsert creates user when not exists."""
        # Check if exists returns empty
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        # Create user
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_user_response,
            status=201,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.upsert_user(sample_travelperk_user)

        assert result["action"] == "insert"
        assert result["id"] == "tp-user-123"

    @responses.activate
    def test_travelperk_upsert_user_update(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, sample_travelperk_scim_list_response, travelperk_base_url
    ):
        """Test upsert updates user when exists."""
        # Check if exists returns user
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Update user
        responses.add(
            responses.PATCH,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.upsert_user(sample_travelperk_user)

        assert result["action"] == "update"
        assert result["id"] == "tp-user-123"

    @responses.activate
    def test_travelperk_upsert_user_conflict_409(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, sample_travelperk_scim_list_response, travelperk_base_url
    ):
        """Test upsert handles 409 conflict by finding by userName."""
        # Check by externalId returns empty
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        # Create returns 409 conflict
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"detail": "User already exists"},
            status=409,
        )
        # Search by userName finds user
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Update user
        responses.add(
            responses.PATCH,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.upsert_user(sample_travelperk_user)

        assert result["action"] == "update"


@pytest.mark.integration
class TestTravelPerkRateLimiting:
    """Test TravelPerk rate limiting behavior."""

    @responses.activate
    def test_travelperk_rate_limiting_429(
        self, mock_travelperk_settings, sample_travelperk_user_response, travelperk_base_url
    ):
        """Test handling of 429 Too Many Requests."""
        # First request returns 429
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json={"detail": "Too Many Requests"},
            status=429,
            headers={"Retry-After": "1"},
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user("tp-user-123")

        assert result is not None
        assert len(responses.calls) == 2

    @responses.activate
    def test_travelperk_rate_limiting_max_retries_exceeded(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test that max retries exceeded raises error."""
        for _ in range(5):
            responses.add(
                responses.GET,
                f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
                json={"detail": "Too Many Requests"},
                status=429,
                headers={"Retry-After": "1"},
            )

        client = TravelPerkClient(settings=mock_travelperk_settings)

        with pytest.raises(TravelPerkApiError):
            client.get_user("tp-user-123")


@pytest.mark.integration
class TestTravelPerkSCIMFilter:
    """Test TravelPerk SCIM filter syntax."""

    @responses.activate
    def test_travelperk_scim_filter_external_id(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test SCIM filter for externalId."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        client.get_user_by_external_id("12345")

        # Verify filter syntax
        request_url = responses.calls[0].request.url
        assert 'filter=externalId' in request_url or 'externalId' in request_url

    @responses.activate
    def test_travelperk_scim_filter_username(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test SCIM filter for userName."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        client.get_user_by_user_name("test@example.com")

        request_url = responses.calls[0].request.url
        assert 'filter=userName' in request_url or 'userName' in request_url


@pytest.mark.integration
class TestTravelPerkSCIMSchema:
    """Test TravelPerk SCIM schema validation."""

    @responses.activate
    def test_travelperk_scim_schema_in_create_request(
        self, mock_travelperk_settings, sample_travelperk_user,
        sample_travelperk_user_response, travelperk_base_url
    ):
        """Test that create request includes correct SCIM schemas."""
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_user_response,
            status=201,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        client.create_user(sample_travelperk_user)

        request_body = responses.calls[0].request.body
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in request_body


@pytest.mark.integration
class TestTravelPerkRetryOn5xx:
    """Test TravelPerk retry on 5xx errors."""

    @responses.activate
    def test_travelperk_retry_on_5xx(
        self, mock_travelperk_settings, sample_travelperk_user_response, travelperk_base_url
    ):
        """Test retry on 500 server error."""
        # First request returns 500
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json={"detail": "Internal Server Error"},
            status=500,
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json=sample_travelperk_user_response,
            status=200,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)
        result = client.get_user("tp-user-123")

        assert result is not None


@pytest.mark.integration
class TestTravelPerkInvalidApiKey:
    """Test TravelPerk invalid API key handling."""

    @responses.activate
    def test_travelperk_invalid_api_key(
        self, mock_travelperk_settings, travelperk_base_url
    ):
        """Test handling of invalid API key."""
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-user-123",
            json={"detail": "Invalid API key"},
            status=401,
        )

        client = TravelPerkClient(settings=mock_travelperk_settings)

        with pytest.raises(TravelPerkApiError) as exc_info:
            client.get_user("tp-user-123")

        assert exc_info.value.status_code == 401
