"""
Unit tests for UKG Pro API client.
"""
import pytest
import responses
import re
from unittest.mock import MagicMock, patch

from src.domain.exceptions import ConfigurationError
from src.infrastructure.adapters.ukg.client import UKGClient


class TestUKGClientInit:
    """Tests for UKGClient initialization."""

    def test_init_with_username_password(self):
        """Test initialization with username/password."""
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            username="testuser",
            password="testpass",
            customer_api_key="test-api-key",
        )
        assert client._base_url == "https://service4.ultipro.com"
        client.close()

    def test_init_with_basic_auth_token(self):
        """Test initialization with pre-encoded auth token."""
        import base64
        token = base64.b64encode(b"user:pass").decode()

        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        assert client._base_url == "https://service4.ultipro.com"
        client.close()

    def test_init_missing_api_key_raises(self):
        """Test missing API key raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            UKGClient(
                base_url="https://service4.ultipro.com",
                username="user",
                password="pass",
                customer_api_key="",
            )
        assert "Customer API key" in str(exc_info.value)

    def test_init_missing_credentials_raises(self):
        """Test missing credentials raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            UKGClient(
                base_url="https://service4.ultipro.com",
                customer_api_key="test-api-key",
            )
        assert "credentials" in str(exc_info.value).lower()


class TestGetAuthToken:
    """Tests for _get_auth_token static method."""

    def test_valid_basic_auth_token(self):
        """Test uses provided valid basic auth token."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        result = UKGClient._get_auth_token(token, None, None)
        assert result == token

    def test_invalid_basic_auth_token_falls_back(self):
        """Test invalid token falls back to username/password."""
        result = UKGClient._get_auth_token(
            "not-valid-base64!!!",
            "fallback",
            "pass"
        )
        import base64
        decoded = base64.b64decode(result).decode()
        assert decoded == "fallback:pass"

    def test_encodes_username_password(self):
        """Test encodes username:password."""
        result = UKGClient._get_auth_token(None, "testuser", "testpass")
        import base64
        decoded = base64.b64decode(result).decode()
        assert decoded == "testuser:testpass"

    def test_missing_credentials_raises(self):
        """Test missing credentials raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            UKGClient._get_auth_token(None, None, None)


class TestExtractList:
    """Tests for _extract_list method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    def test_list_returns_list(self, client):
        """Test list input returns list."""
        result = client._extract_list([{"id": 1}, {"id": 2}])
        assert result == [{"id": 1}, {"id": 2}]

    def test_dict_returns_single_item_list(self, client):
        """Test dict input returns single-item list."""
        result = client._extract_list({"id": 1})
        assert result == [{"id": 1}]

    def test_non_container_returns_empty(self, client):
        """Test non-container returns empty list."""
        result = client._extract_list("string")
        assert result == []

    def test_none_returns_empty(self, client):
        """Test None returns empty list."""
        result = client._extract_list(None)
        assert result == []


class TestGetEmploymentDetails:
    """Tests for get_employment_details method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_returns_matching_employee(self, client):
        """Test returns employee matching employeeNumber and companyID."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "companyID": "COMP1",
                "firstName": "John",
            }],
            status=200,
        )

        result = client.get_employment_details("12345", "COMP1")
        assert result is not None
        assert result["employeeNumber"] == "12345"
        assert result["firstName"] == "John"

    @responses.activate
    def test_returns_none_if_not_found(self, client):
        """Test returns None if employee not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        result = client.get_employment_details("99999", "COMP1")
        assert result is None

    @responses.activate
    def test_handles_companyId_lowercase(self, client):
        """Test handles companyId with lowercase 'd'."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "companyId": "COMP1",
                "firstName": "Jane",
            }],
            status=200,
        )

        result = client.get_employment_details("12345", "COMP1")
        assert result is not None
        assert result["firstName"] == "Jane"


class TestGetEmployeeEmploymentDetails:
    """Tests for get_employee_employment_details method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_returns_matching_employee(self, client):
        """Test returns employee employment details."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "companyID": "COMP1",
                "primaryProjectCode": "PROJ001",
            }],
            status=200,
        )

        result = client.get_employee_employment_details("12345", "COMP1")
        assert result is not None
        assert result["primaryProjectCode"] == "PROJ001"


class TestGetPersonDetails:
    """Tests for get_person_details method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_returns_person_details(self, client):
        """Test returns person details for employeeId."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{
                "employeeId": "EMP001",
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john@example.com",
            }],
            status=200,
        )

        result = client.get_person_details("EMP001")
        assert result is not None
        assert result["firstName"] == "John"
        assert result["emailAddress"] == "john@example.com"

    def test_returns_none_for_empty_id(self, client):
        """Test returns None for empty employeeId."""
        result = client.get_person_details("")
        assert result is None

        result = client.get_person_details(None)
        assert result is None

    @responses.activate
    def test_returns_single_result(self, client):
        """Test returns single result if only one."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{
                "employeeId": "OTHER",
                "firstName": "Jane",
            }],
            status=200,
        )

        result = client.get_person_details("EMP001")
        assert result is not None
        assert result["firstName"] == "Jane"


class TestListEmployees:
    """Tests for list_employees method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_returns_employee_list(self, client):
        """Test returns list of employees."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[
                {"employeeNumber": "12345", "employeeStatusCode": "A"},
                {"employeeNumber": "67890", "employeeStatusCode": "T"},
            ],
            status=200,
        )

        result = client.list_employees("COMP1")
        assert len(result) == 2


class TestListActiveEmployees:
    """Tests for list_active_employees method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_filters_active_only(self, client):
        """Test returns only active employees."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[
                {"employeeNumber": "12345", "employeeStatusCode": "A"},
                {"employeeNumber": "67890", "employeeStatusCode": "T"},
                {"employeeNumber": "11111", "employeeStatusCode": "A"},
            ],
            status=200,
        )

        result = client.list_active_employees("COMP1")
        assert len(result) == 2
        assert all(emp["employeeStatusCode"] == "A" for emp in result)


class TestGetSupervisorEmail:
    """Tests for get_supervisor_email method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    def test_returns_direct_supervisor_email(self, client):
        """Test returns direct supervisorEmailAddress."""
        employment_data = {
            "supervisorEmailAddress": "boss@example.com",
        }
        result = client.get_supervisor_email(employment_data)
        assert result == "boss@example.com"

    def test_returns_nested_supervisor_email(self, client):
        """Test returns email from nested supervisor object."""
        employment_data = {
            "supervisor": {
                "emailAddress": "manager@example.com",
            }
        }
        result = client.get_supervisor_email(employment_data)
        assert result == "manager@example.com"

    def test_returns_none_when_no_supervisor(self, client):
        """Test returns None when no supervisor info."""
        employment_data = {}
        result = client.get_supervisor_email(employment_data)
        assert result is None


class TestGetEmployeeFullData:
    """Tests for get_employee_full_data method."""

    @pytest.fixture
    def client(self):
        """Create UKG client for testing."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        c = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )
        yield c
        c.close()

    @responses.activate
    def test_combines_all_data(self, client):
        """Test combines data from all endpoints."""
        # Employment details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "companyID": "COMP1",
                "employeeId": "EMP001",
            }],
            status=200,
        )
        # Employee employment details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{
                "employeeNumber": "12345",
                "companyID": "COMP1",
                "primaryProjectCode": "PROJ001",
            }],
            status=200,
        )
        # Person details
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{
                "employeeId": "EMP001",
                "firstName": "John",
                "lastName": "Doe",
            }],
            status=200,
        )

        result = client.get_employee_full_data("12345", "COMP1")

        assert result["employee_number"] == "12345"
        assert result["company_id"] == "COMP1"
        assert result["employee_id"] == "EMP001"
        assert result["employment"]["companyID"] == "COMP1"
        assert result["person"]["firstName"] == "John"

    @responses.activate
    def test_raises_if_employee_not_found(self, client):
        """Test raises ValueError if employee not found."""
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        with pytest.raises(ValueError) as exc_info:
            client.get_employee_full_data("99999", "COMP1")
        assert "not found" in str(exc_info.value).lower()


class TestContextManager:
    """Tests for context manager protocol."""

    def test_enter_returns_self(self):
        """Test __enter__ returns self."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        with client as c:
            assert c is client

    def test_exit_calls_close(self):
        """Test __exit__ calls close."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        with patch.object(client, 'close') as mock_close:
            with client:
                pass
            mock_close.assert_called_once()


class TestOrgLevelsIntegration:
    """Tests for org-levels API integration."""

    def test_get_org_levels_success(self):
        """Test fetching org-levels from API."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        mock_response = [
            {"glSegment": "100", "code": "ADMIN", "description": "Administration"},
            {"glSegment": "200", "code": "SALES", "description": "Sales Department"},
        ]

        with patch.object(client, '_get_data', return_value=mock_response):
            result = client.get_org_levels()

            assert len(result) == 2
            assert result[0]["glSegment"] == "100"
            assert result[1]["code"] == "SALES"

        client.close()

    def test_build_org_levels_cache(self):
        """Test building org-levels cache."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        mock_response = [
            {"glSegment": "100", "code": "ADMIN", "description": "Administration"},
            {"glSegment": "200", "code": "SALES", "description": "Sales Department"},
        ]

        with patch.object(client, 'get_org_levels', return_value=mock_response):
            cache = client.build_org_levels_cache()

            assert "100" in cache
            assert cache["100"]["code"] == "ADMIN"
            assert cache["100"]["description"] == "Administration"
            assert "200" in cache
            assert cache["200"]["code"] == "SALES"

        client.close()

    def test_get_department_by_gl_segment(self):
        """Test looking up department by glSegment."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        # Pre-populate cache
        client._org_levels_cache = {
            "100": {"code": "ADMIN", "description": "Administration"},
            "200": {"code": "SALES", "description": "Sales Department"},
        }

        result = client.get_department_by_gl_segment("100")

        assert result["code"] == "ADMIN"
        assert result["description"] == "Administration"

        client.close()

    def test_get_department_by_gl_segment_not_found(self):
        """Test looking up non-existent glSegment returns None."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        client._org_levels_cache = {
            "100": {"code": "ADMIN", "description": "Administration"},
        }

        result = client.get_department_by_gl_segment("999")

        assert result is None

        client.close()


class TestCostCenterFormatting:
    """Tests for cost center formatting."""

    def test_format_cost_center_full_format(self):
        """Test formatting cost center as 'primaryProjectCode - code - description'."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        # Pre-populate cache
        client._org_levels_cache = {
            "100": {"code": "ADMIN", "description": "Administration"},
        }

        result = client.format_cost_center("100")

        assert result == "100 - ADMIN - Administration"

        client.close()

    def test_format_cost_center_not_in_cache(self):
        """Test formatting cost center when gl_segment not in cache returns original."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        # Pre-populate cache with some data but not the requested gl_segment
        client._org_levels_cache = {
            "100": {"code": "ADMIN", "description": "Administration"},
        }

        result = client.format_cost_center("999")

        # Should return original when not found in cache
        assert result == "999"

        client.close()

    def test_format_cost_center_empty_input(self):
        """Test formatting empty cost center returns empty string."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        result = client.format_cost_center("")

        assert result == ""

        client.close()

    def test_format_cost_center_builds_cache_if_empty(self):
        """Test format_cost_center builds cache if not present."""
        import base64
        token = base64.b64encode(b"user:pass").decode()
        client = UKGClient(
            base_url="https://service4.ultipro.com",
            basic_auth_token=token,
            customer_api_key="test-api-key",
        )

        mock_org_levels = [
            {"glSegment": "100", "code": "ADMIN", "description": "Administration"},
        ]

        with patch.object(client, 'get_org_levels', return_value=mock_org_levels):
            result = client.format_cost_center("100")

            assert result == "100 - ADMIN - Administration"

        client.close()
