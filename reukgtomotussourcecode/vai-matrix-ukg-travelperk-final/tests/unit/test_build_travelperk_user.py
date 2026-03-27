"""
Unit tests for build-travelperk-user.py module.
Tests UKG data fetching, date normalization, and SCIM payload building.
"""
import os
import re
import sys
import json
import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_builder_module(monkeypatch):
    """Helper to get fresh builder module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "builder",
        str(Path(__file__).parent.parent.parent / "build-travelperk-user.py")
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


class TestGetToken:
    """Tests for _get_token function."""

    def test_uses_basic_b64_if_provided(self, monkeypatch):
        """Test uses UKG_BASIC_B64 if valid."""
        import base64
        valid_b64 = base64.b64encode(b"user:pass").decode()
        monkeypatch.setenv("UKG_BASIC_B64", valid_b64)

        builder = get_builder_module(monkeypatch)
        result = builder._get_token()
        assert result == valid_b64

    def test_encodes_username_password(self, monkeypatch):
        """Test encodes username:password if no B64 provided."""
        monkeypatch.setenv("UKG_BASIC_B64", "")
        monkeypatch.setenv("UKG_USERNAME", "testuser")
        monkeypatch.setenv("UKG_PASSWORD", "testpass")

        builder = get_builder_module(monkeypatch)
        result = builder._get_token()

        import base64
        decoded = base64.b64decode(result).decode()
        assert decoded == "testuser:testpass"

    def test_missing_credentials_raises(self, monkeypatch):
        """Test raises SystemExit if credentials missing."""
        monkeypatch.setenv("UKG_BASIC_B64", "")
        monkeypatch.setenv("UKG_USERNAME", "")
        monkeypatch.setenv("UKG_PASSWORD", "")

        builder = get_builder_module(monkeypatch)
        with pytest.raises(SystemExit) as exc_info:
            builder._get_token()
        assert "Missing" in str(exc_info.value)

    def test_invalid_b64_falls_back(self, monkeypatch):
        """Test falls back to username/password if B64 invalid."""
        monkeypatch.setenv("UKG_BASIC_B64", "not-valid-base64!!!")
        monkeypatch.setenv("UKG_USERNAME", "fallback")
        monkeypatch.setenv("UKG_PASSWORD", "pass")
        monkeypatch.setenv("DEBUG", "1")

        builder = get_builder_module(monkeypatch)
        result = builder._get_token()

        import base64
        decoded = base64.b64decode(result).decode()
        assert decoded == "fallback:pass"


class TestHeaders:
    """Tests for headers function."""

    def test_headers_contains_authorization(self, monkeypatch):
        """Test headers include Authorization."""
        builder = get_builder_module(monkeypatch)
        h = builder.headers()
        assert "Authorization" in h
        assert h["Authorization"].startswith("Basic ")

    def test_headers_contains_api_key(self, monkeypatch):
        """Test headers include US-CUSTOMER-API-KEY."""
        builder = get_builder_module(monkeypatch)
        h = builder.headers()
        assert "US-CUSTOMER-API-KEY" in h

    def test_headers_missing_api_key_raises(self, monkeypatch):
        """Test raises SystemExit if API key missing."""
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "")

        builder = get_builder_module(monkeypatch)
        with pytest.raises(SystemExit) as exc_info:
            builder.headers()
        assert "UKG_CUSTOMER_API_KEY" in str(exc_info.value)


class TestToIsoYmd:
    """Tests for to_iso_ymd date normalization."""

    def test_iso_datetime_with_z(self, monkeypatch):
        """Test ISO datetime with Z suffix."""
        builder = get_builder_module(monkeypatch)
        result = builder.to_iso_ymd("2024-12-15T10:30:00Z")
        assert result == "2024-12-15"

    def test_iso_datetime_with_offset(self, monkeypatch):
        """Test ISO datetime with timezone offset."""
        builder = get_builder_module(monkeypatch)
        result = builder.to_iso_ymd("2024-06-20T14:00:00-05:00")
        assert result == "2024-06-20"

    def test_plain_date(self, monkeypatch):
        """Test plain YYYY-MM-DD date."""
        builder = get_builder_module(monkeypatch)
        result = builder.to_iso_ymd("2024-01-01")
        assert result == "2024-01-01"

    def test_empty_returns_empty(self, monkeypatch):
        """Test empty input returns empty string."""
        builder = get_builder_module(monkeypatch)
        assert builder.to_iso_ymd("") == ""
        assert builder.to_iso_ymd(None) == ""

    def test_invalid_format_returns_empty(self, monkeypatch):
        """Test invalid format returns empty string."""
        builder = get_builder_module(monkeypatch)
        assert builder.to_iso_ymd("not-a-date") == ""
        assert builder.to_iso_ymd("12/31/2024") == ""


class TestGetEmployeeEmploymentDetails:
    """Tests for get_employee_employment_details function."""

    @responses.activate
    def test_returns_matching_employee(
        self, monkeypatch, sample_ukg_employee_employment_details
    ):
        """Test returns employee matching employeeNumber and companyID."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )

        result = builder.get_employee_employment_details("12345", "J9A6Y")
        assert result["employeeNumber"] == "12345"
        assert result["companyID"] == "J9A6Y"

    @responses.activate
    def test_returns_empty_if_not_found(self, monkeypatch):
        """Test returns empty dict if employee not found."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[],
            status=200,
        )

        result = builder.get_employee_employment_details("99999", "J9A6Y")
        assert result == {}

    @responses.activate
    def test_handles_dict_response(
        self, monkeypatch, sample_ukg_employee_employment_details
    ):
        """Test handles dict response (not list)."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=sample_ukg_employee_employment_details,
            status=200,
        )

        result = builder.get_employee_employment_details("12345", "J9A6Y")
        assert result["employeeNumber"] == "12345"


class TestGetPersonDetails:
    """Tests for get_person_details function."""

    @responses.activate
    def test_returns_person_details(self, monkeypatch, sample_ukg_person_details):
        """Test returns person details for employeeId."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        result = builder.get_person_details("EMP001")
        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"

    def test_raises_if_no_employee_id(self, monkeypatch):
        """Test raises SystemExit if employeeId is None."""
        builder = get_builder_module(monkeypatch)

        with pytest.raises(SystemExit) as exc_info:
            builder.get_person_details(None)
        assert "employeeid" in str(exc_info.value).lower()

    @responses.activate
    def test_returns_first_item_if_no_exact_match(self, monkeypatch):
        """Test returns first item if no exact match."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "OTHER", "firstName": "Jane"}],
            status=200,
        )

        result = builder.get_person_details("EMP001")
        assert result["firstName"] == "Jane"


class TestBuildTravelperkUser:
    """Tests for build_travelperk_user function."""

    @responses.activate
    def test_builds_complete_payload(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test builds complete SCIM user payload."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        result = builder.build_travelperk_user("12345", "J9A6Y")

        assert result["externalId"] == "12345"
        assert result["userName"] == "john.doe@example.com"
        assert result["name"]["givenName"] == "John"
        assert result["name"]["familyName"] == "Doe"
        assert result["active"] is True
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in result["schemas"]

    @responses.activate
    def test_sets_active_false_for_terminated(
        self, monkeypatch,
        sample_terminated_employee,
        sample_ukg_person_details
    ):
        """Test sets active=false for terminated employee."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[{**sample_terminated_employee, "employeeID": "EMP999"}],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{**sample_ukg_person_details, "employeeId": "EMP999"}],
            status=200,
        )

        result = builder.build_travelperk_user("99999", "J9A6Y")
        assert result["active"] is False

    @responses.activate
    def test_includes_cost_center(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test includes costCenter from primaryProjectCode."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        result = builder.build_travelperk_user("12345", "J9A6Y")

        enterprise_ext = result["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"]
        assert enterprise_ext.get("costCenter") == "PROJ001"

    @responses.activate
    def test_raises_if_no_employee(self, monkeypatch):
        """Test raises SystemExit if employee not found."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[],
            status=200,
        )

        with pytest.raises(SystemExit) as exc_info:
            builder.build_travelperk_user("99999", "J9A6Y")
        assert "no employee-employment-details" in str(exc_info.value)

    @responses.activate
    def test_raises_if_no_email(
        self, monkeypatch, sample_ukg_employee_employment_details
    ):
        """Test raises SystemExit if no email address."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[{"employeeId": "EMP001", "firstName": "John", "lastName": "Doe", "emailAddress": ""}],
            status=200,
        )

        with pytest.raises(SystemExit) as exc_info:
            builder.build_travelperk_user("12345", "J9A6Y")
        assert "no emailAddress" in str(exc_info.value)

    @responses.activate
    def test_includes_emails_array(
        self, monkeypatch,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details
    ):
        """Test includes emails array in payload."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employee-employment-details.*"),
            json=[sample_ukg_employee_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/person-details.*"),
            json=[sample_ukg_person_details],
            status=200,
        )

        result = builder.build_travelperk_user("12345", "J9A6Y")

        assert len(result["emails"]) == 1
        assert result["emails"][0]["value"] == "john.doe@example.com"
        assert result["emails"][0]["primary"] is True


class TestGetData:
    """Tests for get_data HTTP wrapper."""

    @responses.activate
    def test_successful_request(self, monkeypatch):
        """Test successful HTTP request."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"status": "ok"},
            status=200,
        )

        result = builder.get_data("/test/endpoint")
        assert result == {"status": "ok"}

    @responses.activate
    def test_with_params(self, monkeypatch):
        """Test request with query params."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"filtered": True},
            status=200,
        )

        result = builder.get_data("/test/endpoint", {"key": "value"})
        assert result == {"filtered": True}

    @responses.activate
    def test_http_error_raises(self, monkeypatch):
        """Test HTTP error raises exception."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"error": "not found"},
            status=404,
        )

        with pytest.raises(Exception):
            builder.get_data("/test/endpoint")

    @responses.activate
    def test_returns_empty_on_json_parse_error(self, monkeypatch):
        """Test returns empty dict on JSON parse error."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            body="not json",
            status=200,
        )

        result = builder.get_data("/test/endpoint")
        assert result == {}
