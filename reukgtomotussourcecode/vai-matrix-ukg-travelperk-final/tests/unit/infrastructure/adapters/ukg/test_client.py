"""Tests for UKG API client."""

import pytest
import responses
import re
from unittest.mock import patch, MagicMock

from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.config.settings import UKGSettings
from src.domain.exceptions import UkgApiError, AuthenticationError, NotFoundError


class TestUKGClient:
    """Test cases for UKGClient."""

    @pytest.fixture
    def ukg_settings(self):
        """Create UKG settings for testing."""
        return UKGSettings(
            base_url="https://service4.ultipro.com",
            username="testuser",
            password="testpass",
            basic_b64="",
            customer_api_key="test-api-key",
            timeout=30.0,
        )

    @pytest.fixture
    def ukg_settings_with_b64(self):
        """Create UKG settings with base64 token."""
        return UKGSettings(
            base_url="https://service4.ultipro.com",
            username="",
            password="",
            basic_b64="dGVzdHVzZXI6dGVzdHBhc3M=",  # testuser:testpass
            customer_api_key="test-api-key",
            timeout=30.0,
        )

    @pytest.fixture
    def ukg_client(self, ukg_settings):
        """Create UKG client with test settings."""
        return UKGClient(settings=ukg_settings, debug=False)

    @pytest.fixture
    def debug_client(self, ukg_settings):
        """Create UKG client with debug enabled."""
        return UKGClient(settings=ukg_settings, debug=True)

    def test_init_with_settings(self, ukg_settings):
        """Test client initialization with explicit settings."""
        client = UKGClient(settings=ukg_settings)
        assert client.settings == ukg_settings
        assert client.debug is False
        assert client._authenticator is not None

    def test_init_with_debug(self, ukg_settings):
        """Test client initialization with debug enabled."""
        client = UKGClient(settings=ukg_settings, debug=True)
        assert client.debug is True

    def test_get_token_from_credentials(self, ukg_client):
        """Test getting token from username/password."""
        import base64

        token = ukg_client._authenticator.get_token()
        expected = base64.b64encode(b"testuser:testpass").decode()
        assert token == expected

    def test_get_token_caches_result(self, ukg_client):
        """Test token is cached after first call."""
        token1 = ukg_client._authenticator.get_token()
        token2 = ukg_client._authenticator.get_token()
        assert token1 == token2

    def test_get_token_from_b64(self, ukg_settings_with_b64):
        """Test getting token from pre-encoded base64."""
        client = UKGClient(settings=ukg_settings_with_b64)
        token = client._authenticator.get_token()
        assert token == "dGVzdHVzZXI6dGVzdHBhc3M="

    def test_get_token_missing_credentials(self):
        """Test error when credentials missing."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="",
            password="",
            basic_b64="",
            customer_api_key="test-api-key",
        )
        # Validation now happens during client init, so expect error there
        with pytest.raises(ValueError) as exc_info:
            client = UKGClient(settings=settings)

        assert "Missing UKG_USERNAME/UKG_PASSWORD" in str(exc_info.value)

    def test_headers(self, ukg_client):
        """Test request headers generation."""
        headers = ukg_client._authenticator.get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["US-CUSTOMER-API-KEY"] == "test-api-key"
        assert headers["Accept"] == "application/json"

    def test_headers_missing_api_key(self):
        """Test error when API key missing."""
        settings = UKGSettings(
            base_url="https://service4.ultipro.com",
            username="testuser",
            password="testpass",
            basic_b64="",
            customer_api_key="",
        )
        # Validation now happens during client init
        with pytest.raises(ValueError) as exc_info:
            client = UKGClient(settings=settings)

        assert "Missing UKG_CUSTOMER_API_KEY" in str(exc_info.value)

    @responses.activate
    def test_get_success(self, ukg_client):
        """Test successful GET request."""
        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"key": "value"},
            status=200,
        )

        result = ukg_client._get("/test/endpoint")
        assert result == {"key": "value"}

    @responses.activate
    def test_get_http_error(self, ukg_client):
        """Test HTTP error handling."""
        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            ukg_client._get("/test/endpoint")

        assert exc_info.value.status_code == 404

    @responses.activate
    def test_get_invalid_json(self, ukg_client):
        """Test handling of invalid JSON response."""
        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            body="not json",
            status=200,
        )

        result = ukg_client._get("/test/endpoint")
        assert result == {}

    @responses.activate
    def test_get_debug_logging(self, debug_client, caplog):
        """Test debug logging output."""
        import logging

        with caplog.at_level(logging.DEBUG):
            responses.add(
                responses.GET,
                re.compile(r".*/test/endpoint.*"),
                json={"key": "value"},
                status=200,
            )

            debug_client._get("/test/endpoint")

        # Debug client should have debug=True
        assert debug_client.debug is True

    def test_normalize_list_from_list(self, ukg_client):
        """Test normalizing list response."""
        data = [{"id": 1}, {"id": 2}]
        result = ukg_client._normalize_list(data)
        assert result == data

    def test_normalize_list_from_dict_with_items(self, ukg_client):
        """Test normalizing dict with items key."""
        data = {"items": [{"id": 1}]}
        result = ukg_client._normalize_list(data)
        assert result == [{"id": 1}]

    def test_normalize_list_from_dict_without_items(self, ukg_client):
        """Test normalizing dict without items key."""
        data = {"id": 1}
        result = ukg_client._normalize_list(data)
        assert result == [{"id": 1}]

    def test_normalize_list_from_invalid(self, ukg_client):
        """Test normalizing invalid data."""
        result = ukg_client._normalize_list("string")
        assert result == []

    @responses.activate
    def test_get_employment_details_success(self, ukg_client):
        """Test getting employment details successfully."""
        employee_data = {
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeID": "EMP001",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[employee_data],
            status=200,
        )

        result = ukg_client.get_employment_details("12345", "J9A6Y")

        assert result["employeeNumber"] == "12345"
        assert result["companyID"] == "J9A6Y"

    @responses.activate
    def test_get_employment_details_not_found(self, ukg_client):
        """Test getting employment details when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[],
            status=200,
        )

        result = ukg_client.get_employment_details("99999", "J9A6Y")
        assert result == {}

    @responses.activate
    def test_get_employment_details_wrong_company(self, ukg_client):
        """Test getting employment details with wrong company."""
        employee_data = {
            "employeeNumber": "12345",
            "companyID": "OTHER",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[employee_data],
            status=200,
        )

        result = ukg_client.get_employment_details("12345", "J9A6Y")
        assert result == {}

    @responses.activate
    def test_get_all_employment_details_by_company(self, ukg_client, caplog):
        """Test getting all employment details for company."""
        import logging

        employees = [
            {"employeeNumber": "12345", "employeeTypeCode": "FTC"},
            {"employeeNumber": "12346", "employeeTypeCode": "PTC"},
        ]
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=employees,
            status=200,
        )

        with caplog.at_level(logging.INFO):
            result = ukg_client.get_all_employment_details_by_company("J9A6Y")

        assert len(result) == 2
        # Verify logging happened
        assert any("J9A6Y" in record.message for record in caplog.records)

    @responses.activate
    def test_get_all_employment_details_with_filter(self, ukg_client, capsys):
        """Test getting all employment details with type filter."""
        employees = [
            {"employeeNumber": "12345", "employeeTypeCode": "FTC"},
            {"employeeNumber": "12346", "employeeTypeCode": "PTC"},
        ]
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=employees,
            status=200,
        )

        result = ukg_client.get_all_employment_details_by_company(
            "J9A6Y", employee_type_codes=["FTC"]
        )

        assert len(result) == 1
        assert result[0]["employeeTypeCode"] == "FTC"

    @responses.activate
    def test_get_person_details_success(self, ukg_client):
        """Test getting person details successfully."""
        person_data = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[person_data],
            status=200,
        )

        result = ukg_client.get_person_details("EMP001")

        assert result["employeeId"] == "EMP001"
        assert result["firstName"] == "John"

    @responses.activate
    def test_get_person_details_not_found(self, ukg_client):
        """Test getting person details when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[],
            status=200,
        )

        result = ukg_client.get_person_details("EMP999")
        assert result == {}

    def test_get_person_details_no_employee_id(self, ukg_client):
        """Test getting person details with no employee ID."""
        with pytest.raises(ValueError) as exc_info:
            ukg_client.get_person_details("")

        assert "employee_id is required" in str(exc_info.value)

    @responses.activate
    def test_get_all_supervisor_details(self, ukg_client):
        """Test getting all supervisor details."""
        supervisors = [
            {"employeeId": "EMP001", "supervisorEmployeeId": "MGR001"},
            {"employeeId": "EMP002", "supervisorEmployeeId": "MGR001"},
        ]
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-supervisor-details.*"),
            json=supervisors,
            status=200,
        )

        result = ukg_client.get_all_supervisor_details()

        assert len(result) == 2
        assert result[0]["employeeId"] == "EMP001"
