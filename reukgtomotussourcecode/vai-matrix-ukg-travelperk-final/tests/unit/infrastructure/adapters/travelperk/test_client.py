"""Tests for TravelPerk SCIM API client."""

import pytest
import responses
import re
from unittest.mock import MagicMock, patch

from src.infrastructure.adapters.travelperk.client import TravelPerkClient
from src.infrastructure.config.settings import TravelPerkSettings
from src.domain.models import TravelPerkUser, UserName
from src.domain.exceptions import TravelPerkApiError, RateLimitError


class TestTravelPerkClient:
    """Test cases for TravelPerkClient."""

    @pytest.fixture
    def tp_settings(self):
        """Create TravelPerk settings for testing."""
        return TravelPerkSettings(
            api_base="https://app.sandbox-travelperk.com",
            api_key="test-api-key",
            timeout=30.0,
            max_retries=2,
        )

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock()
        limiter.acquire.return_value = None
        return limiter

    @pytest.fixture
    def tp_client(self, tp_settings, mock_rate_limiter):
        """Create TravelPerk client with test settings."""
        with patch("src.infrastructure.adapters.travelperk.client.get_rate_limiter") as mock_get_limiter:
            mock_get_limiter.return_value = mock_rate_limiter
            client = TravelPerkClient(settings=tp_settings, debug=False)
            return client

    @pytest.fixture
    def debug_client(self, tp_settings, mock_rate_limiter):
        """Create TravelPerk client with debug enabled."""
        with patch("src.infrastructure.adapters.travelperk.client.get_rate_limiter") as mock_get_limiter:
            mock_get_limiter.return_value = mock_rate_limiter
            client = TravelPerkClient(settings=tp_settings, debug=True)
            return client

    @pytest.fixture
    def sample_user(self):
        """Create sample TravelPerkUser."""
        return TravelPerkUser(
            external_id="12345",
            user_name="john.doe@example.com",
            name=UserName(given_name="John", family_name="Doe"),
            active=True,
        )

    def test_init_with_settings(self, tp_settings, mock_rate_limiter):
        """Test client initialization with settings."""
        with patch("src.infrastructure.adapters.travelperk.client.get_rate_limiter") as mock_get_limiter:
            mock_get_limiter.return_value = mock_rate_limiter
            client = TravelPerkClient(settings=tp_settings)

            assert client.settings == tp_settings
            assert client.debug is False

    def test_init_with_debug(self, tp_settings, mock_rate_limiter):
        """Test client initialization with debug enabled."""
        with patch("src.infrastructure.adapters.travelperk.client.get_rate_limiter") as mock_get_limiter:
            mock_get_limiter.return_value = mock_rate_limiter
            client = TravelPerkClient(settings=tp_settings, debug=True)

            assert client.debug is True

    def test_headers(self, tp_client):
        """Test request headers generation."""
        headers = tp_client._headers()

        assert headers["Authorization"] == "ApiKey test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_headers_missing_api_key(self, mock_rate_limiter):
        """Test error when API key missing during validation."""
        settings = TravelPerkSettings(
            api_base="https://app.sandbox-travelperk.com",
            api_key="",
        )
        with patch("src.infrastructure.adapters.travelperk.client.get_rate_limiter") as mock_get_limiter:
            mock_get_limiter.return_value = mock_rate_limiter
            # Validation now happens in __init__, raising ValueError
            with pytest.raises(ValueError) as exc_info:
                client = TravelPerkClient(settings=settings)

            assert "TRAVELPERK_API_KEY" in str(exc_info.value)

    def test_handle_rate_limit_with_header(self, tp_client):
        """Test extracting retry-after from response via error handler."""
        from src.infrastructure.adapters.travelperk.error_handler import TravelPerkErrorHandler
        response = MagicMock()
        response.headers = {"Retry-After": "30"}

        result = TravelPerkErrorHandler.extract_retry_after(response)
        assert result == 30

    def test_handle_rate_limit_no_header(self, tp_client):
        """Test default retry-after when header missing."""
        from src.infrastructure.adapters.travelperk.error_handler import TravelPerkErrorHandler
        response = MagicMock()
        response.headers = {}

        result = TravelPerkErrorHandler.extract_retry_after(response)
        assert result == 60

    def test_handle_rate_limit_invalid_header(self, tp_client):
        """Test default retry-after when header invalid."""
        from src.infrastructure.adapters.travelperk.error_handler import TravelPerkErrorHandler
        response = MagicMock()
        response.headers = {"Retry-After": "not-a-number"}

        result = TravelPerkErrorHandler.extract_retry_after(response)
        assert result == 60

    def test_safe_json_success(self, tp_client):
        """Test safe JSON parsing success."""
        response = MagicMock()
        response.json.return_value = {"id": "test"}

        result = tp_client._safe_json(response)
        assert result == {"id": "test"}

    def test_safe_json_error(self, tp_client):
        """Test safe JSON parsing with error."""
        response = MagicMock()
        response.json.side_effect = ValueError("No JSON")
        response.text = "Error response text"

        result = tp_client._safe_json(response)
        assert result["raw_text"] == "Error response text"
        assert "parse_error" in result

    def test_log_debug_enabled(self, debug_client, caplog):
        """Test debug logging when debug enabled."""
        import logging
        with caplog.at_level(logging.DEBUG):
            # The debug flag is now used for more verbose debug logging
            # Let's verify the debug client has debug=True
            assert debug_client.debug is True

    def test_log_debug_disabled(self, tp_client):
        """Test debug mode is disabled by default."""
        # Verify that debug mode is disabled
        assert tp_client.debug is False

    @responses.activate
    def test_get_user_success(self, tp_client):
        """Test getting user by ID successfully."""
        responses.add(
            responses.GET,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-123",
            json={"id": "user-123", "userName": "john@example.com"},
            status=200,
        )

        result = tp_client.get_user("user-123")

        assert result["id"] == "user-123"

    @responses.activate
    def test_get_user_not_found(self, tp_client):
        """Test getting user when not found."""
        responses.add(
            responses.GET,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-999",
            json={"error": "Not found"},
            status=404,
        )

        result = tp_client.get_user("user-999")
        assert result is None

    @responses.activate
    def test_get_user_error(self, tp_client):
        """Test getting user with API error."""
        responses.add(
            responses.GET,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-123",
            json={"error": "Server error"},
            status=500,
        )

        with pytest.raises(TravelPerkApiError) as exc_info:
            tp_client.get_user("user-123")

        assert exc_info.value.status_code == 500

    @responses.activate
    def test_get_user_by_external_id_found(self, tp_client):
        """Test getting user by external ID when found."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": [{"id": "user-123", "externalId": "12345"}]},
            status=200,
        )

        result = tp_client.get_user_by_external_id("12345")

        assert result["id"] == "user-123"
        assert result["externalId"] == "12345"

    @responses.activate
    def test_get_user_by_external_id_not_found(self, tp_client):
        """Test getting user by external ID when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": []},
            status=200,
        )

        result = tp_client.get_user_by_external_id("99999")
        assert result is None

    @responses.activate
    def test_get_user_by_user_name_found(self, tp_client):
        """Test getting user by userName when found."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": [{"id": "user-123", "userName": "john@example.com"}]},
            status=200,
        )

        result = tp_client.get_user_by_user_name("john@example.com")

        assert result["id"] == "user-123"

    @responses.activate
    def test_get_user_by_user_name_not_found(self, tp_client):
        """Test getting user by userName when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": []},
            status=200,
        )

        result = tp_client.get_user_by_user_name("unknown@example.com")
        assert result is None

    @responses.activate
    def test_create_user_success(self, tp_client, sample_user):
        """Test creating user successfully."""
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"id": "new-user-123", "externalId": "12345"},
            status=201,
        )

        result = tp_client.create_user(sample_user)

        assert result["id"] == "new-user-123"

    @responses.activate
    def test_create_user_api_error(self, tp_client, sample_user):
        """Test creating user with API error."""
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"error": "Validation failed"},
            status=400,
        )

        with pytest.raises(TravelPerkApiError) as exc_info:
            tp_client.create_user(sample_user)

        assert exc_info.value.status_code == 400

    @responses.activate
    def test_create_user_rate_limit_retry(self, tp_client, sample_user):
        """Test creating user with rate limit retry."""
        # First call rate limited, second succeeds
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"error": "Rate limited"},
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"id": "new-user-123"},
            status=201,
        )

        with patch("time.sleep"):  # Speed up test
            result = tp_client.create_user(sample_user)

        assert result["id"] == "new-user-123"

    @responses.activate
    def test_update_user_success(self, tp_client, sample_user):
        """Test updating user successfully."""
        responses.add(
            responses.PATCH,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-123",
            json={"id": "user-123", "externalId": "12345"},
            status=200,
        )

        result = tp_client.update_user("user-123", sample_user)

        assert result["id"] == "user-123"

    @responses.activate
    def test_update_user_204_response(self, tp_client, sample_user):
        """Test updating user with 204 No Content response."""
        responses.add(
            responses.PATCH,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-123",
            status=204,
        )

        result = tp_client.update_user("user-123", sample_user)

        assert result == {"id": "user-123"}

    @responses.activate
    def test_update_user_api_error(self, tp_client, sample_user):
        """Test updating user with API error."""
        responses.add(
            responses.PATCH,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/user-123",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(TravelPerkApiError) as exc_info:
            tp_client.update_user("user-123", sample_user)

        assert exc_info.value.status_code == 404

    @responses.activate
    def test_upsert_user_insert(self, tp_client, sample_user):
        """Test upsert creates new user."""
        # User doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": []},
            status=200,
        )
        # Create succeeds
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"id": "new-user-123"},
            status=201,
        )

        result = tp_client.upsert_user(sample_user)

        assert result["action"] == "insert"
        assert result["status"] == 201
        assert result["id"] == "new-user-123"

    @responses.activate
    def test_upsert_user_update(self, tp_client, sample_user):
        """Test upsert updates existing user."""
        # User exists
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": [{"id": "existing-user-123"}]},
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PATCH,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/existing-user-123",
            json={"id": "existing-user-123"},
            status=200,
        )

        result = tp_client.upsert_user(sample_user)

        assert result["action"] == "update"
        assert result["status"] == 200
        assert result["id"] == "existing-user-123"

    @responses.activate
    def test_upsert_user_conflict_fallback(self, tp_client, sample_user):
        """Test upsert handles 409 conflict by finding by userName."""
        # User doesn't exist by externalId
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*filter=externalId.*"),
            json={"Resources": []},
            status=200,
        )
        # Create returns 409 conflict
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"error": "Conflict"},
            status=409,
        )
        # Find by userName
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*filter=userName.*"),
            json={"Resources": [{"id": "existing-user-123"}]},
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PATCH,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users/existing-user-123",
            json={"id": "existing-user-123"},
            status=200,
        )

        result = tp_client.upsert_user(sample_user)

        assert result["action"] == "update"
        assert result["id"] == "existing-user-123"

    @responses.activate
    def test_upsert_user_missing_id_on_existing(self, tp_client, sample_user):
        """Test upsert error when existing user has no ID."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": [{"externalId": "12345"}]},  # No id field
            status=200,
        )

        with pytest.raises(TravelPerkApiError) as exc_info:
            tp_client.upsert_user(sample_user)

        assert "no id" in str(exc_info.value).lower()

    @responses.activate
    def test_upsert_user_missing_id_on_create(self, tp_client, sample_user):
        """Test upsert error when created user has no ID."""
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users\?.*"),
            json={"Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://app.sandbox-travelperk.com/api/v2/scim/Users",
            json={"externalId": "12345"},  # No id field
            status=201,
        )

        with pytest.raises(TravelPerkApiError) as exc_info:
            tp_client.upsert_user(sample_user)

        assert "no id" in str(exc_info.value).lower()
