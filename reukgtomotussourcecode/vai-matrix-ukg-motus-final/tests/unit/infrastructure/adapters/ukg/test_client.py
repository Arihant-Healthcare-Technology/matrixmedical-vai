"""Tests for UKG API client."""

import pytest
import responses
import re
from unittest.mock import patch

from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.config.settings import UKGSettings
from src.domain.exceptions import UkgApiError


class TestUKGClient:
    """Test cases for UKGClient."""

    @pytest.fixture
    def ukg_settings(self):
        """Create UKG settings for testing."""
        return UKGSettings(
            base_url="https://service4.ultipro.com",
            username="testuser",
            password="testpass",
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

    def test_init_with_debug(self, ukg_settings):
        """Test client initialization with debug enabled."""
        client = UKGClient(settings=ukg_settings, debug=True)
        assert client.debug is True

    def test_headers(self, ukg_client, ukg_settings):
        """Test request headers generation."""
        headers = ukg_client._headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["US-CUSTOMER-API-KEY"] == ukg_settings.customer_api_key
        assert headers["Accept"] == "application/json"

    @responses.activate
    def test_get_success(self, ukg_client):
        """Test successful GET request."""
        responses.add(
            responses.GET,
            "https://service4.ultipro.com/test/endpoint",
            json={"key": "value"},
            status=200,
        )

        result = ukg_client._get("/test/endpoint")
        assert result == {"key": "value"}

    @responses.activate
    def test_get_with_params(self, ukg_client):
        """Test GET request with query parameters."""
        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"data": "test"},
            status=200,
        )

        result = ukg_client._get("/test/endpoint", params={"foo": "bar"})
        assert result == {"data": "test"}

    @responses.activate
    def test_get_http_error(self, ukg_client):
        """Test HTTP error handling."""
        responses.add(
            responses.GET,
            "https://service4.ultipro.com/test/endpoint",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(UkgApiError) as exc_info:
            ukg_client._get("/test/endpoint")

        assert exc_info.value.status_code == 404

    @responses.activate
    def test_get_json_parse_error(self, ukg_client):
        """Test JSON parse error handling."""
        responses.add(
            responses.GET,
            "https://service4.ultipro.com/test/endpoint",
            body="invalid json",
            status=200,
            content_type="application/json",
        )

        with pytest.raises(UkgApiError) as exc_info:
            ukg_client._get("/test/endpoint")

        assert "JSON parse error" in str(exc_info.value)

    @responses.activate
    def test_get_debug_logging(self, debug_client, capsys):
        """Test debug logging output."""
        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"key": "value"},
            status=200,
        )

        debug_client._get("/test/endpoint")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out

    def test_get_first_item_from_list(self, ukg_client):
        """Test extracting first item from list."""
        data = [{"id": 1}, {"id": 2}]
        result = UKGClient._get_first_item(data)
        assert result == {"id": 1}

    def test_get_first_item_from_empty_list(self, ukg_client):
        """Test extracting first item from empty list."""
        result = UKGClient._get_first_item([])
        assert result == {}

    def test_get_first_item_from_dict(self, ukg_client):
        """Test extracting first item from dict."""
        data = {"id": 1, "name": "test"}
        result = UKGClient._get_first_item(data)
        assert result == data

    def test_get_first_item_from_invalid(self, ukg_client):
        """Test extracting first item from invalid type."""
        result = UKGClient._get_first_item("string")
        assert result == {}

    @responses.activate
    def test_get_employment_details_success(
        self, ukg_client, sample_ukg_employment_details
    ):
        """Test getting employment details successfully."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
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
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        result = ukg_client.get_employment_details("99999", "J9A6Y")
        assert result == {}

    @responses.activate
    def test_get_employment_details_wrong_company(
        self, ukg_client, sample_ukg_employment_details
    ):
        """Test getting employment details with wrong company ID."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )

        result = ukg_client.get_employment_details("12345", "WRONG")
        assert result == {}

    @responses.activate
    def test_get_employee_employment_details_success(
        self, ukg_client, sample_ukg_employee_employment_details
    ):
        """Test getting employee employment details successfully."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )

        result = ukg_client.get_employee_employment_details("12345", "J9A6Y")

        assert result["employeeNumber"] == "12345"
        assert result["companyID"] == "J9A6Y"

    @responses.activate
    def test_get_employee_employment_details_not_found(self, ukg_client):
        """Test getting employee employment details when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[],
            status=200,
        )

        result = ukg_client.get_employee_employment_details("99999", "J9A6Y")
        assert result == {}

    @responses.activate
    def test_get_person_details_success(
        self, ukg_client, sample_ukg_person_details
    ):
        """Test getting person details successfully."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
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
        with pytest.raises(UkgApiError) as exc_info:
            ukg_client.get_person_details("")

        assert "No employeeId available" in str(exc_info.value)

    @responses.activate
    def test_get_supervisor_details_success(
        self, ukg_client, sample_supervisor_details
    ):
        """Test getting supervisor details successfully."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )

        result = ukg_client.get_supervisor_details("EMP001")

        assert result["employeeId"] == "EMP001"
        assert result["supervisorFirstName"] == "Jane"

    @responses.activate
    def test_get_supervisor_details_not_found(self, ukg_client):
        """Test getting supervisor details when not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json={"error": "Not found"},
            status=404,
        )

        result = ukg_client.get_supervisor_details("EMP001")
        assert result == {}

    @responses.activate
    def test_get_supervisor_details_debug_warning(self, debug_client, capsys):
        """Test supervisor not found debug warning."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json={"error": "Not found"},
            status=404,
        )

        debug_client.get_supervisor_details("EMP001")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    @responses.activate
    def test_get_location_success(self, ukg_client, sample_location):
        """Test getting location details successfully."""
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations/LOC001.*"),
            json=sample_location,
            status=200,
        )

        result = ukg_client.get_location("LOC001")

        assert result["locationCode"] == "LOC001"
        assert result["description"] == "Orlando Office"

    def test_get_location_empty_code(self, ukg_client):
        """Test getting location with empty code."""
        result = ukg_client.get_location("")
        assert result == {}

    @responses.activate
    def test_get_location_fallback_to_query(self, ukg_client, sample_location):
        """Test location fallback to query param endpoint."""
        # First call fails
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations/LOC001.*"),
            json={"error": "Not found"},
            status=404,
        )
        # Fallback succeeds
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations\?.*"),
            json=sample_location,
            status=200,
        )

        result = ukg_client.get_location("LOC001")
        assert result["locationCode"] == "LOC001"

    @responses.activate
    def test_get_location_both_fail(self, ukg_client):
        """Test getting location when both endpoints fail."""
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json={"error": "Not found"},
            status=404,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json={"error": "Not found"},
            status=404,
        )

        result = ukg_client.get_location("LOC001")
        assert result == {}

    @responses.activate
    def test_get_all_employment_details_by_company_list(self, ukg_client):
        """Test getting all employment details returns list."""
        employees = [
            {"employeeNumber": "12345", "companyID": "J9A6Y"},
            {"employeeNumber": "12346", "companyID": "J9A6Y"},
        ]
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=employees,
            status=200,
        )

        result = ukg_client.get_all_employment_details_by_company("J9A6Y")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["employeeNumber"] == "12345"

    @responses.activate
    def test_get_all_employment_details_by_company_dict_with_items(self, ukg_client):
        """Test getting all employment details with dict items response."""
        employees = {"items": [{"employeeNumber": "12345"}]}
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=employees,
            status=200,
        )

        result = ukg_client.get_all_employment_details_by_company("J9A6Y")

        assert isinstance(result, list)
        assert len(result) == 1

    @responses.activate
    def test_get_all_employment_details_by_company_single_dict(self, ukg_client):
        """Test getting all employment details with single dict response."""
        employee = {"employeeNumber": "12345", "companyID": "J9A6Y"}
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=employee,
            status=200,
        )

        result = ukg_client.get_all_employment_details_by_company("J9A6Y")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["employeeNumber"] == "12345"

    @responses.activate
    def test_get_all_employment_details_by_company_empty(self, ukg_client):
        """Test getting all employment details returns empty list."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[],
            status=200,
        )

        result = ukg_client.get_all_employment_details_by_company("J9A6Y")

        assert isinstance(result, list)
        assert len(result) == 0

    @responses.activate
    def test_connection_error(self, ukg_client):
        """Test connection error handling."""
        import requests as req

        responses.add(
            responses.GET,
            "https://service4.ultipro.com/test/endpoint",
            body=req.exceptions.ConnectionError("Connection refused"),
        )

        with pytest.raises(UkgApiError):
            ukg_client._get("/test/endpoint")

    @responses.activate
    def test_timeout_error(self, ukg_client):
        """Test timeout error handling."""
        import requests

        responses.add(
            responses.GET,
            "https://service4.ultipro.com/test/endpoint",
            body=requests.exceptions.Timeout("Timeout"),
        )

        with pytest.raises(UkgApiError):
            ukg_client._get("/test/endpoint")
