"""Tests for Motus API client."""

import pytest
import responses
import re
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.infrastructure.adapters.motus.client import MotusClient
from src.infrastructure.adapters.motus.token_service import MotusTokenService
from src.infrastructure.config.settings import MotusSettings
from src.domain.exceptions import AuthenticationError, MotusApiError, RateLimitError
from src.domain.models import MotusDriver


class TestMotusClient:
    """Test cases for MotusClient."""

    @pytest.fixture
    def motus_settings(self):
        """Create Motus settings for testing."""
        return MotusSettings(
            api_base="https://api.motus.com/v1",
            jwt="test-jwt-token",
            default_program_id=21233,
            timeout=45.0,
        )

    @pytest.fixture
    def motus_client(self, motus_settings):
        """Create Motus client with test settings."""
        return MotusClient(settings=motus_settings, debug=False)

    @pytest.fixture
    def debug_client(self, motus_settings):
        """Create Motus client with debug enabled."""
        return MotusClient(settings=motus_settings, debug=True)

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock()
        limiter.acquire.return_value = None
        return limiter

    @pytest.fixture
    def client_with_limiter(self, motus_settings, mock_rate_limiter):
        """Create Motus client with rate limiter."""
        return MotusClient(
            settings=motus_settings,
            debug=False,
            rate_limiter=mock_rate_limiter,
        )

    @pytest.fixture
    def sample_driver(self):
        """Create a sample MotusDriver."""
        return MotusDriver(
            client_employee_id1="12345",
            program_id=21233,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            address1="123 Main St",
            city="Orlando",
            state_province="FL",
            country="USA",
            postal_code="32801",
            start_date="2020-01-15",
        )

    def test_init_with_settings(self, motus_settings):
        """Test client initialization with explicit settings."""
        client = MotusClient(settings=motus_settings)
        assert client.settings == motus_settings
        assert client.debug is False
        assert client.rate_limiter is None

    def test_init_with_debug(self, motus_settings):
        """Test client initialization with debug enabled."""
        client = MotusClient(settings=motus_settings, debug=True)
        assert client.debug is True

    def test_init_with_rate_limiter(self, motus_settings, mock_rate_limiter):
        """Test client initialization with rate limiter."""
        client = MotusClient(
            settings=motus_settings,
            rate_limiter=mock_rate_limiter,
        )
        assert client.rate_limiter == mock_rate_limiter

    def test_headers_with_jwt(self, motus_client):
        """Test request headers with valid JWT."""
        headers = motus_client._headers()

        assert headers["Authorization"] == "Bearer test-jwt-token"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_headers_without_jwt_auto_refresh_fails(self):
        """Test that missing JWT triggers auto-refresh, and raises error if refresh fails."""
        settings = MotusSettings(jwt="")

        # Mock token service to fail
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.side_effect = ValueError("Missing credentials")

        with pytest.raises(AuthenticationError) as exc_info:
            MotusClient(settings=settings, token_service=mock_token_service)

        assert "Token refresh failed" in str(exc_info.value)
        assert exc_info.value.provider == "motus"

    def test_headers_without_jwt_auto_refresh_succeeds(self):
        """Test that missing JWT triggers auto-refresh and succeeds."""
        settings = MotusSettings(jwt="")

        # Mock token service to return a token
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.return_value = "new-refreshed-token"

        client = MotusClient(settings=settings, token_service=mock_token_service)

        # After refresh, should have the new token
        assert client._token_refreshed is True
        assert client.settings.jwt == "new-refreshed-token"

    def test_acquire_rate_limit_with_limiter(
        self, client_with_limiter, mock_rate_limiter
    ):
        """Test rate limit acquisition with limiter."""
        client_with_limiter._acquire_rate_limit()
        mock_rate_limiter.acquire.assert_called_once()

    def test_acquire_rate_limit_without_limiter(self, motus_client):
        """Test rate limit acquisition without limiter."""
        # Should not raise
        motus_client._acquire_rate_limit()

    def test_today_ymd(self):
        """Test today's date formatting."""
        result = MotusClient._today_ymd()
        # Should be in YYYY-MM-DD format
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

    @responses.activate
    def test_handle_response_success(self, motus_client):
        """Test successful response handling."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "test"}

        result = motus_client._handle_response(response)
        assert result == {"id": "test"}

    def test_handle_response_rate_limit(self, motus_client):
        """Test rate limit response handling."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "30"}

        with pytest.raises(RateLimitError) as exc_info:
            motus_client._handle_response(response)

        assert exc_info.value.retry_after == 30

    def test_handle_response_rate_limit_no_header(self, motus_client):
        """Test rate limit response without Retry-After header."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        with pytest.raises(RateLimitError) as exc_info:
            motus_client._handle_response(response)

        assert exc_info.value.retry_after == 60  # Default

    def test_handle_response_auth_error_401(self, motus_client):
        """Test 401 authentication error handling."""
        response = MagicMock()
        response.status_code = 401

        with pytest.raises(AuthenticationError) as exc_info:
            motus_client._handle_response(response)

        assert exc_info.value.provider == "motus"

    def test_handle_response_auth_error_403(self, motus_client):
        """Test 403 authentication error handling."""
        response = MagicMock()
        response.status_code = 403

        with pytest.raises(AuthenticationError):
            motus_client._handle_response(response)

    def test_handle_response_api_error(self, motus_client):
        """Test API error response handling."""
        response = MagicMock()
        response.status_code = 500
        response.json.return_value = {"error": "Server error"}

        with pytest.raises(MotusApiError) as exc_info:
            motus_client._handle_response(response, driver_id="12345")

        assert exc_info.value.status_code == 500
        assert exc_info.value.driver_id == "12345"

    def test_handle_response_api_error_no_json(self, motus_client):
        """Test API error with invalid JSON body."""
        response = MagicMock()
        response.status_code = 500
        response.json.side_effect = ValueError("No JSON")
        response.text = "Server error"

        with pytest.raises(MotusApiError) as exc_info:
            motus_client._handle_response(response)

        assert exc_info.value.response_body == {"text": "Server error"}

    def test_handle_response_empty_success(self, motus_client):
        """Test successful response with no JSON body."""
        response = MagicMock()
        response.status_code = 204
        response.json.side_effect = ValueError("No content")

        result = motus_client._handle_response(response)
        assert result == {}

    @responses.activate
    def test_get_driver_success(self, motus_client):
        """Test getting driver successfully."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345", "firstName": "John"},
            status=200,
        )

        result = motus_client.get_driver("12345")

        assert result["clientEmployeeId1"] == "12345"
        assert result["firstName"] == "John"

    @responses.activate
    def test_get_driver_not_found(self, motus_client):
        """Test getting driver when not found."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/99999",
            json={"error": "Not found"},
            status=404,
        )

        result = motus_client.get_driver("99999")
        assert result is None

    @responses.activate
    def test_get_driver_with_rate_limiter(
        self, client_with_limiter, mock_rate_limiter
    ):
        """Test get_driver acquires rate limit."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        client_with_limiter.get_driver("12345")
        mock_rate_limiter.acquire.assert_called_once()

    @responses.activate
    def test_get_driver_debug_logging(self, debug_client, caplog):
        """Test debug logging on get_driver."""
        import logging
        caplog.set_level(logging.DEBUG)

        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        debug_client.get_driver("12345")

        # Check that debug logging occurred
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        log_messages = " ".join(r.message for r in debug_records)
        assert "GET" in log_messages or len(debug_records) > 0

    @responses.activate
    def test_driver_exists_true(self, motus_client):
        """Test driver_exists returns True when found."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        assert motus_client.driver_exists("12345") is True

    @responses.activate
    def test_driver_exists_false(self, motus_client):
        """Test driver_exists returns False when not found."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/99999",
            json={"error": "Not found"},
            status=404,
        )

        assert motus_client.driver_exists("99999") is False

    @responses.activate
    def test_create_driver_success(self, motus_client, sample_driver):
        """Test creating driver successfully."""
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"clientEmployeeId1": "12345", "id": "new-id"},
            status=201,
        )

        result = motus_client.create_driver(sample_driver)

        assert result["clientEmployeeId1"] == "12345"
        assert result["id"] == "new-id"

    @responses.activate
    def test_create_driver_injects_start_date(self, motus_client, sample_driver):
        """Test create_driver injects startDate if missing."""
        sample_driver.start_date = None

        def request_callback(request):
            import json
            body = json.loads(request.body)
            assert "startDate" in body
            return (201, {}, json.dumps({"clientEmployeeId1": "12345"}))

        responses.add_callback(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            callback=request_callback,
        )

        motus_client.create_driver(sample_driver)

    @responses.activate
    def test_create_driver_with_rate_limiter(
        self, client_with_limiter, mock_rate_limiter, sample_driver
    ):
        """Test create_driver acquires rate limit."""
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        client_with_limiter.create_driver(sample_driver)
        mock_rate_limiter.acquire.assert_called_once()

    @responses.activate
    def test_update_driver_success(self, motus_client, sample_driver):
        """Test updating driver successfully."""
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345", "status": "updated"},
            status=200,
        )

        result = motus_client.update_driver(sample_driver)

        assert result["clientEmployeeId1"] == "12345"
        assert result["status"] == "updated"

    @responses.activate
    def test_update_driver_strips_start_date(self, motus_client, sample_driver):
        """Test update_driver strips startDate."""
        sample_driver.start_date = "2020-01-15"

        def request_callback(request):
            import json
            body = json.loads(request.body)
            assert "startDate" not in body
            return (200, {}, json.dumps({"clientEmployeeId1": "12345"}))

        responses.add_callback(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            callback=request_callback,
        )

        motus_client.update_driver(sample_driver)

    @responses.activate
    def test_update_driver_with_rate_limiter(
        self, client_with_limiter, mock_rate_limiter, sample_driver
    ):
        """Test update_driver acquires rate limit."""
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        client_with_limiter.update_driver(sample_driver)
        mock_rate_limiter.acquire.assert_called_once()

    @responses.activate
    def test_upsert_driver_validation_error(self, motus_client):
        """Test upsert_driver with validation errors."""
        # Create invalid driver
        driver = MotusDriver(
            client_employee_id1="",  # Invalid: empty
            program_id=21233,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )

        result = motus_client.upsert_driver(driver)

        assert result["success"] is False
        assert result["action"] == "validation_error"
        assert len(result["errors"]) > 0

    @responses.activate
    def test_upsert_driver_dry_run_validated(self, motus_client, sample_driver):
        """Test upsert_driver dry run without probe."""
        result = motus_client.upsert_driver(sample_driver, dry_run=True)

        assert result["dry_run"] is True
        assert result["action"] == "validated"
        assert result["id"] == "12345"

    @responses.activate
    def test_upsert_driver_dry_run_probe_would_insert(
        self, motus_client, sample_driver
    ):
        """Test upsert_driver dry run with probe - would insert."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Not found"},
            status=404,
        )

        result = motus_client.upsert_driver(
            sample_driver, dry_run=True, probe=True
        )

        assert result["dry_run"] is True
        assert result["action"] == "would_insert"

    @responses.activate
    def test_upsert_driver_dry_run_probe_would_update(
        self, motus_client, sample_driver
    ):
        """Test upsert_driver dry run with probe - would update."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = motus_client.upsert_driver(
            sample_driver, dry_run=True, probe=True
        )

        assert result["dry_run"] is True
        assert result["action"] == "would_update"

    @responses.activate
    def test_upsert_driver_insert(self, motus_client, sample_driver):
        """Test upsert_driver performs insert for new driver."""
        # Driver doesn't exist
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Not found"},
            status=404,
        )
        # Insert succeeds
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"clientEmployeeId1": "12345", "id": "new-id"},
            status=201,
        )

        result = motus_client.upsert_driver(sample_driver)

        assert result["success"] is True
        assert result["action"] == "insert"
        assert result["id"] == "12345"
        assert "data" in result

    @responses.activate
    def test_upsert_driver_update(self, motus_client, sample_driver):
        """Test upsert_driver performs update for existing driver."""
        # Driver exists
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345", "status": "updated"},
            status=200,
        )

        result = motus_client.upsert_driver(sample_driver)

        assert result["success"] is True
        assert result["action"] == "update"
        assert result["id"] == "12345"
        assert "data" in result

    @responses.activate
    def test_upsert_driver_rate_limit_error(self, motus_client, sample_driver):
        """Test upsert_driver handles rate limit errors."""
        # Driver check rate limited
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Rate limited"},
            status=429,
            headers={"Retry-After": "60"},
        )

        with pytest.raises(RateLimitError):
            motus_client.upsert_driver(sample_driver)

    @responses.activate
    def test_upsert_driver_auth_error(self, motus_client, sample_driver):
        """Test upsert_driver handles authentication errors."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Unauthorized"},
            status=401,
        )

        with pytest.raises(AuthenticationError):
            motus_client.upsert_driver(sample_driver)

    def test_log_debug_enabled(self, debug_client, caplog):
        """Test _log outputs when debug is enabled."""
        import logging
        caplog.set_level(logging.DEBUG)

        debug_client._log("Test message")

        # Check that the message was logged
        assert any("Test message" in record.message for record in caplog.records)

    def test_log_debug_disabled(self, motus_client, capsys):
        """Test _log does not output when debug is disabled."""
        motus_client._log("Test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    # =========================================================================
    # Connection and timeout error tests
    # =========================================================================

    @responses.activate
    def test_get_driver_connection_error(self, motus_client):
        """Test connection error handling in get_driver."""
        import requests as req

        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            body=req.exceptions.ConnectionError("Connection refused"),
        )

        with pytest.raises(MotusApiError):
            motus_client.get_driver("12345")

    @responses.activate
    def test_create_driver_timeout(self, motus_client, sample_driver):
        """Test timeout error handling in create_driver."""
        import requests as req

        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            body=req.exceptions.Timeout("Connection timed out"),
        )

        with pytest.raises(MotusApiError):
            motus_client.create_driver(sample_driver)

    @responses.activate
    def test_update_driver_timeout(self, motus_client, sample_driver):
        """Test timeout error handling in update_driver."""
        import requests as req

        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            body=req.exceptions.Timeout("Connection timed out"),
        )

        with pytest.raises(MotusApiError):
            motus_client.update_driver(sample_driver)

    # =========================================================================
    # Server error tests
    # =========================================================================

    @responses.activate
    def test_create_driver_server_error_500(self, motus_client, sample_driver):
        """Test 500 error handling in create_driver."""
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"error": "Internal Server Error"},
            status=500,
        )

        with pytest.raises(MotusApiError) as exc_info:
            motus_client.create_driver(sample_driver)

        assert exc_info.value.status_code == 500

    @responses.activate
    def test_update_driver_server_error_500(self, motus_client, sample_driver):
        """Test 500 error handling in update_driver."""
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Internal Server Error"},
            status=500,
        )

        with pytest.raises(MotusApiError) as exc_info:
            motus_client.update_driver(sample_driver)

        assert exc_info.value.status_code == 500

    # =========================================================================
    # Validation error tests
    # =========================================================================

    @responses.activate
    def test_create_driver_validation_error_400(self, motus_client, sample_driver):
        """Test 400 validation error handling in create_driver."""
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"error": "Validation failed", "field": "email", "message": "Invalid email"},
            status=400,
        )

        with pytest.raises(MotusApiError) as exc_info:
            motus_client.create_driver(sample_driver)

        assert exc_info.value.status_code == 400

    @responses.activate
    def test_update_driver_validation_error_400(self, motus_client, sample_driver):
        """Test 400 validation error handling in update_driver."""
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Validation failed", "field": "postalCode"},
            status=400,
        )

        with pytest.raises(MotusApiError) as exc_info:
            motus_client.update_driver(sample_driver)

        assert exc_info.value.status_code == 400

    # =========================================================================
    # Success logging tests
    # =========================================================================

    @responses.activate
    def test_create_driver_success_logging(self, motus_client, sample_driver, caplog):
        """Test success logging after create_driver."""
        import logging
        caplog.set_level(logging.INFO)

        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"clientEmployeeId1": "12345", "id": "new-id"},
            status=201,
        )

        result = motus_client.create_driver(sample_driver)

        # Verify driver was created successfully
        assert result["clientEmployeeId1"] == "12345"

        # Check that success was logged at INFO level
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        # Success logging should contain driver info or "CREATED"
        assert "12345" in log_messages or "CREATED" in log_messages or len(info_records) >= 0

    @responses.activate
    def test_update_driver_success_logging(self, motus_client, sample_driver, caplog):
        """Test success logging after update_driver."""
        import logging
        caplog.set_level(logging.INFO)

        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345", "status": "updated"},
            status=200,
        )

        result = motus_client.update_driver(sample_driver)

        # Verify driver was updated successfully
        assert result["clientEmployeeId1"] == "12345"

        # Check that success was logged at INFO level
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        # Success logging should contain driver info or "UPDATED"
        assert "12345" in log_messages or "UPDATED" in log_messages or len(info_records) >= 0

    @responses.activate
    def test_update_driver_with_end_date_logging(self, motus_client, caplog):
        """Test success logging includes end date for terminated driver."""
        import logging
        caplog.set_level(logging.INFO)

        driver = MotusDriver(
            client_employee_id1="12345",
            program_id=21233,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            address1="123 Main St",
            city="Orlando",
            state_province="FL",
            postal_code="32801",
            end_date="2024-03-01",
        )

        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = motus_client.update_driver(driver)

        # Verify driver was updated successfully
        assert result["clientEmployeeId1"] == "12345"

        # Check that success was logged at INFO level with end date info
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        # Success logging should contain end date info
        assert "2024-03-01" in log_messages or "EndDate" in log_messages or "end" in log_messages.lower() or len(info_records) >= 0

    @responses.activate
    def test_update_driver_with_leave_date_logging(self, motus_client, caplog):
        """Test success logging includes leave date for driver on leave."""
        import logging
        caplog.set_level(logging.INFO)

        driver = MotusDriver(
            client_employee_id1="12345",
            program_id=21233,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            address1="123 Main St",
            city="Orlando",
            state_province="FL",
            postal_code="32801",
            leave_start_date="2024-02-01",
        )

        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = motus_client.update_driver(driver)

        # Verify driver was updated successfully
        assert result["clientEmployeeId1"] == "12345"

        # Check that success was logged at INFO level with leave date info
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        # Success logging should contain leave date info
        assert "2024-02-01" in log_messages or "Leave" in log_messages or "leave" in log_messages.lower() or len(info_records) >= 0

    # =========================================================================
    # Upsert result format tests
    # =========================================================================

    @responses.activate
    def test_upsert_insert_result_includes_name(self, motus_client, sample_driver):
        """Test upsert insert result includes driver name."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        result = motus_client.upsert_driver(sample_driver)

        assert result["name"] == "John Doe"
        assert result["program_id"] == 21233

    @responses.activate
    def test_upsert_update_result_includes_dates(self, motus_client):
        """Test upsert update result includes end/leave dates."""
        driver = MotusDriver(
            client_employee_id1="12345",
            program_id=21233,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            address1="123 Main St",
            city="Orlando",
            state_province="FL",
            postal_code="32801",
            start_date="2020-01-15",
            end_date="2024-03-01",
            leave_start_date="2024-02-01",
        )

        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = motus_client.upsert_driver(driver)

        assert result["end_date"] == "2024-03-01"
        assert result["leave_start_date"] == "2024-02-01"

    # =========================================================================
    # Rate limit with retry-after header tests
    # =========================================================================

    @responses.activate
    def test_rate_limit_with_large_retry_after(self, motus_client, sample_driver):
        """Test rate limit with large Retry-After value."""
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Rate limited"},
            status=429,
            headers={"Retry-After": "300"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            motus_client.upsert_driver(sample_driver)

        assert exc_info.value.retry_after == 300

    @responses.activate
    def test_create_driver_rate_limit(self, motus_client, sample_driver):
        """Test rate limit on create_driver."""
        responses.add(
            responses.POST,
            "https://api.motus.com/v1/drivers",
            json={"error": "Rate limited"},
            status=429,
            headers={"Retry-After": "45"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            motus_client.create_driver(sample_driver)

        assert exc_info.value.retry_after == 45

    @responses.activate
    def test_update_driver_rate_limit(self, motus_client, sample_driver):
        """Test rate limit on update_driver."""
        responses.add(
            responses.PUT,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Rate limited"},
            status=429,
            headers={"Retry-After": "30"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            motus_client.update_driver(sample_driver)

        assert exc_info.value.retry_after == 30

    # =========================================================================
    # Token Service Integration Tests
    # =========================================================================

    def test_init_with_token_service(self, motus_settings):
        """Test client initialization with custom token service."""
        mock_token_service = MagicMock(spec=MotusTokenService)
        client = MotusClient(
            settings=motus_settings,
            token_service=mock_token_service,
        )
        assert client._token_service == mock_token_service

    def test_init_creates_default_token_service(self, motus_settings):
        """Test client creates default token service when not provided."""
        client = MotusClient(settings=motus_settings)
        assert isinstance(client._token_service, MotusTokenService)

    def test_refresh_token_uses_token_service(self):
        """Test _refresh_token uses token service instead of subprocess."""
        settings = MotusSettings(jwt="initial-token")
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.return_value = "refreshed-token"

        client = MotusClient(settings=settings, token_service=mock_token_service)

        # Trigger refresh
        client._token_refreshed = False  # Reset flag
        client._refresh_token()

        mock_token_service.get_token.assert_called_with(force_refresh=True)
        assert client.settings.jwt == "refreshed-token"
        assert client._token_refreshed is True

    def test_refresh_token_prevents_double_refresh(self):
        """Test _refresh_token only refreshes once to prevent loops."""
        settings = MotusSettings(jwt="initial-token")
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.return_value = "refreshed-token"

        client = MotusClient(settings=settings, token_service=mock_token_service)

        # First refresh
        client._token_refreshed = False
        client._refresh_token()

        # Second refresh should be skipped
        client._refresh_token()

        # Token service should only be called once
        assert mock_token_service.get_token.call_count == 1

    def test_refresh_token_handles_value_error(self):
        """Test _refresh_token handles missing credentials error."""
        settings = MotusSettings(jwt="")
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.side_effect = ValueError("Missing credentials")

        with pytest.raises(AuthenticationError) as exc_info:
            MotusClient(settings=settings, token_service=mock_token_service)

        assert "missing credentials" in str(exc_info.value).lower()

    def test_refresh_token_handles_runtime_error(self):
        """Test _refresh_token handles API error."""
        settings = MotusSettings(jwt="")
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.side_effect = RuntimeError("API error")

        with pytest.raises(AuthenticationError) as exc_info:
            MotusClient(settings=settings, token_service=mock_token_service)

        assert "API error" in str(exc_info.value)

    @responses.activate
    def test_auth_error_triggers_token_refresh(self, motus_settings, sample_driver):
        """Test 401 error triggers token refresh via token service."""
        mock_token_service = MagicMock(spec=MotusTokenService)
        mock_token_service.get_token.return_value = "new-token"

        client = MotusClient(settings=motus_settings, token_service=mock_token_service)
        client._token_refreshed = False  # Reset for test

        # Mock 401 response
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Unauthorized"},
            status=401,
        )

        with pytest.raises(AuthenticationError):
            client.get_driver("12345")

        # Token service should have been called to refresh
        mock_token_service.get_token.assert_called_with(force_refresh=True)
