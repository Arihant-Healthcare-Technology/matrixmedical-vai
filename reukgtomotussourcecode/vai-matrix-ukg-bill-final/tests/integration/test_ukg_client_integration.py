"""
Integration tests for UKG API client.

Tests verify UKG client behavior with mocked HTTP responses.
Run with: pytest tests/integration/test_ukg_client_integration.py -v -m integration
"""
import base64
from unittest.mock import patch, MagicMock

import pytest
import responses

from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.config.settings import UKGSettings
from src.domain.exceptions.api_exceptions import UkgApiError, AuthenticationError


@pytest.mark.integration
class TestUKGClientAuthentication:
    """Test UKG client authentication mechanisms."""

    def test_ukg_authentication_basic_username_password(self, mock_ukg_settings):
        """Test authentication using username and password."""
        client = UKGClient(settings=mock_ukg_settings)

        # Verify token is generated correctly
        expected_token = base64.b64encode(b"test_user:test_pass").decode()
        assert client._get_token() == expected_token

    def test_ukg_authentication_b64_token(self):
        """Test authentication using pre-encoded base64 token."""
        settings = MagicMock()
        settings.base_url = "https://service4.ultipro.com"
        settings.username = ""
        settings.password = ""
        settings.basic_b64 = base64.b64encode(b"preencoded:credentials").decode()
        settings.customer_api_key = "test_api_key"
        settings.timeout = 45.0

        client = UKGClient(settings=settings)
        token = client._get_token()

        assert token == settings.basic_b64

    def test_ukg_authentication_missing_credentials_raises_error(self):
        """Test that missing credentials raises AuthenticationError."""
        settings = MagicMock()
        settings.base_url = "https://service4.ultipro.com"
        settings.username = ""
        settings.password = ""
        settings.basic_b64 = ""
        settings.customer_api_key = "test_api_key"
        settings.timeout = 45.0

        client = UKGClient(settings=settings)

        with pytest.raises(AuthenticationError, match="Missing UKG_USERNAME"):
            client._get_token()

    def test_ukg_authentication_missing_api_key_raises_error(self):
        """Test that missing API key raises AuthenticationError."""
        settings = MagicMock()
        settings.base_url = "https://service4.ultipro.com"
        settings.username = "test_user"
        settings.password = "test_pass"
        settings.basic_b64 = None
        settings.customer_api_key = ""
        settings.timeout = 45.0

        client = UKGClient(settings=settings)

        with pytest.raises(AuthenticationError, match="Missing UKG_CUSTOMER_API_KEY"):
            client._headers()


@pytest.mark.integration
class TestUKGClientGetEmploymentDetails:
    """Test UKG client employment details retrieval."""

    @responses.activate
    def test_ukg_get_employment_details_single(
        self, mock_ukg_settings, sample_ukg_employment_details, ukg_base_url
    ):
        """Test fetching employment details for a single employee."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employment_details],
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_employment_details("12345", "J9A6Y")

        assert result["employeeNumber"] == "12345"
        assert result["companyID"] == "J9A6Y"

    @responses.activate
    def test_ukg_get_employment_details_by_company(
        self, mock_ukg_settings, sample_ukg_employment_details_list, ukg_base_url
    ):
        """Test fetching all employment details for a company."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_all_employment_details_by_company("J9A6Y")

        assert len(result) == 3
        assert all(emp["companyID"] == "J9A6Y" for emp in result)

    @responses.activate
    def test_ukg_get_employment_details_not_found(
        self, mock_ukg_settings, ukg_base_url
    ):
        """Test fetching employment details when employee not found."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[],
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_employment_details("99999", "J9A6Y")

        assert result == {}


@pytest.mark.integration
class TestUKGClientGetPersonDetails:
    """Test UKG client person details retrieval."""

    @responses.activate
    def test_ukg_get_person_details(
        self, mock_ukg_settings, sample_ukg_person_details, ukg_base_url
    ):
        """Test fetching person details for an employee."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_person_details("EMP001-UUID")

        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["emailAddress"] == "john.doe@example.com"

    @responses.activate
    def test_ukg_get_person_details_not_found(
        self, mock_ukg_settings, ukg_base_url
    ):
        """Test fetching person details when not found."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[],
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_person_details("NONEXISTENT")

        assert result == {}


@pytest.mark.integration
class TestUKGClientPagination:
    """Test UKG client pagination handling."""

    @responses.activate
    def test_ukg_pagination_handling(
        self, mock_ukg_settings, generate_employees, ukg_base_url
    ):
        """Test handling of large result sets."""
        large_employee_list = generate_employees(100)

        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=large_employee_list,
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_all_employment_details_by_company("J9A6Y")

        assert len(result) == 100

    @responses.activate
    def test_ukg_normalize_list_dict_response(
        self, mock_ukg_settings, sample_ukg_employment_details_list, ukg_base_url
    ):
        """Test normalization of dict response with items key."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json={"items": sample_ukg_employment_details_list},
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_all_employment_details_by_company("J9A6Y")

        assert len(result) == 3


@pytest.mark.integration
class TestUKGClientFiltering:
    """Test UKG client filtering capabilities."""

    @responses.activate
    def test_ukg_employee_type_filtering(
        self, mock_ukg_settings, sample_ukg_employment_details_list, ukg_base_url
    ):
        """Test filtering by employee type codes."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_all_employment_details_by_company(
            "J9A6Y",
            employee_type_codes=["FTC"]
        )

        # Should only return FTC employees
        assert all(emp["employeeTypeCode"] == "FTC" for emp in result)

    @responses.activate
    def test_ukg_employee_type_filtering_multiple_codes(
        self, mock_ukg_settings, sample_ukg_employment_details_list, ukg_base_url
    ):
        """Test filtering by multiple employee type codes."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )

        client = UKGClient(settings=mock_ukg_settings)
        result = client.get_all_employment_details_by_company(
            "J9A6Y",
            employee_type_codes=["FTC", "HRC"]
        )

        assert len(result) >= 2


@pytest.mark.integration
class TestUKGClientErrorHandling:
    """Test UKG client error handling."""

    @responses.activate
    def test_ukg_timeout_handling(self, mock_ukg_settings, ukg_base_url):
        """Test handling of request timeout."""
        import requests

        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        client = UKGClient(settings=mock_ukg_settings)

        with pytest.raises(requests.exceptions.Timeout):
            client.get_all_employment_details_by_company("J9A6Y")

    @responses.activate
    def test_ukg_invalid_credentials(self, mock_ukg_settings, ukg_base_url):
        """Test handling of 401 unauthorized response."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json={"error": "Unauthorized"},
            status=401,
        )

        client = UKGClient(settings=mock_ukg_settings)

        with pytest.raises(UkgApiError) as exc_info:
            client.get_all_employment_details_by_company("J9A6Y")

        assert exc_info.value.status_code == 401

    @responses.activate
    def test_ukg_server_error(self, mock_ukg_settings, ukg_base_url):
        """Test handling of 500 server error."""
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json={"error": "Internal Server Error"},
            status=500,
        )

        client = UKGClient(settings=mock_ukg_settings)

        with pytest.raises(UkgApiError) as exc_info:
            client.get_all_employment_details_by_company("J9A6Y")

        assert exc_info.value.status_code == 500

    @responses.activate
    def test_ukg_empty_employee_id_raises_error(self, mock_ukg_settings):
        """Test that empty employee_id raises ValueError."""
        client = UKGClient(settings=mock_ukg_settings)

        with pytest.raises(ValueError, match="employee_id is required"):
            client.get_person_details("")


@pytest.mark.integration
class TestUKGClientHeaders:
    """Test UKG client header construction."""

    def test_ukg_headers_construction(self, mock_ukg_settings):
        """Test that headers are constructed correctly."""
        client = UKGClient(settings=mock_ukg_settings)
        headers = client._headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["US-CUSTOMER-API-KEY"] == "test_api_key"
        assert headers["Accept"] == "application/json"
