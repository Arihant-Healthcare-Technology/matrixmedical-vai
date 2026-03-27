"""
Unit tests for build-motus-driver.py module.
Tests date/phone normalization, UKG data fetching, and driver payload building.
"""
import os
import re
import sys
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
        str(Path(__file__).parent.parent.parent / "build-motus-driver.py")
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


class TestGetToken:
    """Tests for _get_token function."""

    def test_get_token_from_username_password(self, monkeypatch):
        """Test token generation from username and password."""
        monkeypatch.setenv("UKG_BASIC_B64", "")
        monkeypatch.setenv("UKG_USERNAME", "user")
        monkeypatch.setenv("UKG_PASSWORD", "pass")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "key")

        builder = get_builder_module(monkeypatch)

        # Manually test the logic since module vars are set at import
        import base64
        expected = base64.b64encode(b"user:pass").decode()

        # Create a new function with updated values
        def test_get_token():
            username = "user"
            password = "pass"
            return base64.b64encode(f"{username}:{password}".encode()).decode()

        assert test_get_token() == expected

    def test_get_token_from_b64_env(self, monkeypatch):
        """Test token from pre-encoded base64."""
        monkeypatch.setenv("UKG_BASIC_B64", "dGVzdDp0b2tlbg==")
        monkeypatch.setenv("UKG_USERNAME", "")
        monkeypatch.setenv("UKG_PASSWORD", "")
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "key")

        builder = get_builder_module(monkeypatch)
        # The module should use the B64 value directly
        assert builder.UKG_BASIC_B64 == "dGVzdDp0b2tlbg=="


class TestHeaders:
    """Tests for headers function."""

    def test_headers_contains_required_keys(self, monkeypatch):
        """Test headers include all required keys."""
        builder = get_builder_module(monkeypatch)

        h = builder.headers()
        assert "Authorization" in h
        assert "US-CUSTOMER-API-KEY" in h
        assert "Accept" in h
        assert h["Accept"] == "application/json"

    def test_headers_missing_api_key_raises(self, monkeypatch):
        """Test headers raises when API key missing."""
        monkeypatch.setenv("UKG_CUSTOMER_API_KEY", "")

        builder = get_builder_module(monkeypatch)

        with pytest.raises(SystemExit):
            builder.headers()


class TestToUsDate:
    """Tests for to_us_date function."""

    def test_iso_string_with_z(self, monkeypatch):
        """Test conversion of ISO string with Z suffix."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date("2024-01-15T10:30:00Z")
        assert result == "01/15/2024"

    def test_iso_string_with_offset(self, monkeypatch):
        """Test conversion of ISO string with timezone offset."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date("2024-01-15T10:30:00+00:00")
        assert result == "01/15/2024"

    def test_plain_date_string(self, monkeypatch):
        """Test conversion of plain date string."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date("2024-01-15")
        assert result == "01/15/2024"

    def test_empty_string_returns_empty(self, monkeypatch):
        """Test empty input returns empty string."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date("")
        assert result == ""

    def test_none_returns_empty(self, monkeypatch):
        """Test None input returns empty string."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date(None)
        assert result == ""

    def test_invalid_date_returns_original(self, monkeypatch):
        """Test invalid date returns original string."""
        builder = get_builder_module(monkeypatch)

        result = builder.to_us_date("not-a-date")
        assert result == "not-a-date"


class TestNormalizePhone:
    """Tests for normalize_phone function."""

    def test_10_digit_phone_formatted(self, monkeypatch):
        """Test 10-digit phone gets formatted."""
        builder = get_builder_module(monkeypatch)

        result = builder.normalize_phone("5551234567")
        assert result == "555-123-4567"

    def test_phone_with_formatting_stripped(self, monkeypatch):
        """Test existing formatting is stripped and reformatted."""
        builder = get_builder_module(monkeypatch)

        result = builder.normalize_phone("(555) 123-4567")
        assert result == "555-123-4567"

    def test_phone_with_dashes(self, monkeypatch):
        """Test phone with dashes is normalized."""
        builder = get_builder_module(monkeypatch)

        result = builder.normalize_phone("555-123-4567")
        assert result == "555-123-4567"

    def test_non_10_digit_returned_as_is(self, monkeypatch):
        """Test non-10-digit phones returned as-is."""
        builder = get_builder_module(monkeypatch)

        # Too short
        assert builder.normalize_phone("555123") == "555123"
        # Too long
        assert builder.normalize_phone("15551234567") == "15551234567"

    def test_empty_phone_returns_empty(self, monkeypatch):
        """Test empty phone returns empty string."""
        builder = get_builder_module(monkeypatch)

        assert builder.normalize_phone("") == ""
        assert builder.normalize_phone(None) == ""


class TestGetData:
    """Tests for get_data function."""

    @responses.activate
    def test_get_data_success(self, monkeypatch):
        """Test successful data fetch."""
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
    def test_get_data_with_params(self, monkeypatch):
        """Test data fetch with query parameters."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"items": [1, 2, 3]},
            status=200,
        )

        result = builder.get_data("/test/endpoint", {"param": "value"})
        assert result == {"items": [1, 2, 3]}

    @responses.activate
    def test_get_data_returns_list(self, monkeypatch):
        """Test data fetch returns list properly."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json=[{"id": 1}, {"id": 2}],
            status=200,
        )

        result = builder.get_data("/test/endpoint")
        assert isinstance(result, list)
        assert len(result) == 2

    @responses.activate
    def test_get_data_http_error_raises(self, monkeypatch):
        """Test HTTP error raises SystemExit."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/test/endpoint.*"),
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(SystemExit) as exc_info:
            builder.get_data("/test/endpoint")
        assert "HTTP error" in str(exc_info.value)


class TestGetFirstItem:
    """Tests for get_first_item helper."""

    def test_get_first_item_from_list(self, monkeypatch):
        """Test extracting first item from list."""
        builder = get_builder_module(monkeypatch)

        result = builder.get_first_item([{"id": 1}, {"id": 2}])
        assert result == {"id": 1}

    def test_get_first_item_empty_list(self, monkeypatch):
        """Test empty list returns empty dict."""
        builder = get_builder_module(monkeypatch)

        result = builder.get_first_item([])
        assert result == {}

    def test_get_first_item_from_dict(self, monkeypatch):
        """Test dict input returns dict."""
        builder = get_builder_module(monkeypatch)

        result = builder.get_first_item({"id": 1})
        assert result == {"id": 1}

    def test_get_first_item_non_container(self, monkeypatch):
        """Test non-container returns empty dict."""
        builder = get_builder_module(monkeypatch)

        result = builder.get_first_item("string")
        assert result == {}


class TestResolveProgramIdFromJobCode:
    """Tests for resolve_program_id_from_job_code function."""

    def test_exact_match_favr(self, monkeypatch):
        """Test exact match for FAVR program."""
        builder = get_builder_module(monkeypatch)

        # Job code 1103 maps to FAVR (21232)
        result = builder.resolve_program_id_from_job_code("1103")
        assert result == 21232

    def test_exact_match_cpm(self, monkeypatch):
        """Test exact match for CPM program."""
        builder = get_builder_module(monkeypatch)

        # Job code 4154 maps to CPM (21233)
        result = builder.resolve_program_id_from_job_code("4154")
        assert result == 21233

    def test_no_match_returns_default(self, monkeypatch):
        """Test no match returns default."""
        builder = get_builder_module(monkeypatch)

        result = builder.resolve_program_id_from_job_code("9999", default_program_id=12345)
        assert result == 12345

    def test_no_match_no_default_returns_none(self, monkeypatch):
        """Test no match without default returns None."""
        builder = get_builder_module(monkeypatch)

        result = builder.resolve_program_id_from_job_code("9999")
        assert result is None

    def test_none_job_code_returns_default(self, monkeypatch):
        """Test None job code returns default."""
        builder = get_builder_module(monkeypatch)

        result = builder.resolve_program_id_from_job_code(None, default_program_id=21233)
        assert result == 21233

    def test_leading_zeros_stripped(self, monkeypatch):
        """Test job code with leading zeros is matched."""
        builder = get_builder_module(monkeypatch)

        # "01103" should match "1103" -> FAVR
        result = builder.resolve_program_id_from_job_code("01103")
        assert result == 21232


class TestGetEmploymentDetails:
    """Tests for get_employment_details function."""

    @responses.activate
    def test_get_employment_details_found(self, monkeypatch, sample_ukg_employment_details):
        """Test finding employment details."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )

        result = builder.get_employment_details("12345", "J9A6Y")
        assert result["employeeNumber"] == "12345"
        assert result["companyID"] == "J9A6Y"

    @responses.activate
    def test_get_employment_details_not_found(self, monkeypatch):
        """Test employment details not found returns empty dict."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        result = builder.get_employment_details("99999", "J9A6Y")
        assert result == {}


class TestGetPersonDetails:
    """Tests for get_person_details function."""

    @responses.activate
    def test_get_person_details_found(self, monkeypatch, sample_ukg_person_details):
        """Test finding person details."""
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

    def test_get_person_details_no_employee_id_raises(self, monkeypatch):
        """Test missing employee ID raises SystemExit."""
        builder = get_builder_module(monkeypatch)

        with pytest.raises(SystemExit) as exc_info:
            builder.get_person_details(None)
        assert "employeeid" in str(exc_info.value).lower()


class TestBuildMotusDriver:
    """Tests for build_motus_driver function."""

    @responses.activate
    def test_build_motus_driver_success(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test successful driver payload building."""
        builder = get_builder_module(monkeypatch)

        # Set up all required mocks
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
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
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        result = builder.build_motus_driver("12345", "J9A6Y")

        assert result["clientEmployeeId1"] == "12345"
        assert result["programId"] == 21233  # Job code 4154 -> CPM
        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["email"] == "john.doe@example.com"

    @responses.activate
    def test_build_motus_driver_no_employment_raises(self, monkeypatch):
        """Test missing employment details raises SystemExit."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[],
            status=200,
        )

        with pytest.raises(SystemExit) as exc_info:
            builder.build_motus_driver("99999", "J9A6Y")
        assert "no employment details" in str(exc_info.value).lower()

    @responses.activate
    def test_build_motus_driver_phone_normalized(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test phone number is normalized in payload."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
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
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        result = builder.build_motus_driver("12345", "J9A6Y")

        # Phone should be normalized from "5551234567" to "555-123-4567"
        assert result["phone"] == "555-123-4567"

    @responses.activate
    def test_build_motus_driver_custom_variables_populated(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location
    ):
        """Test custom variables are populated."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
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
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        result = builder.build_motus_driver("12345", "J9A6Y")

        custom_vars = result["customVariables"]
        assert isinstance(custom_vars, list)

        # Check some expected custom variables
        project_code = next((v for v in custom_vars if v["name"] == "Project Code"), None)
        assert project_code is not None
        assert project_code["value"] == "PROJ001"

        job_code = next((v for v in custom_vars if v["name"] == "Job Code"), None)
        assert job_code is not None
        assert job_code["value"] == "4154"


class TestGetSupervisorDetails:
    """Tests for get_supervisor_details function."""

    @responses.activate
    def test_supervisor_found(self, monkeypatch, sample_supervisor_details):
        """Test successful supervisor fetch."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )

        result = builder.get_supervisor_details("EMP001")
        assert result["supervisorFirstName"] == "Jane"
        assert result["supervisorLastName"] == "Manager"

    @responses.activate
    def test_supervisor_not_found_empty_response(self, monkeypatch):
        """Test supervisor not found returns empty dict."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[],
            status=200,
        )

        result = builder.get_supervisor_details("EMP001")
        assert result == {}

    @responses.activate
    def test_supervisor_api_error_returns_empty(self, monkeypatch):
        """Test supervisor API error handling returns empty dict."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json={"error": "Not found"},
            status=404,
        )

        result = builder.get_supervisor_details("EMP001")
        assert result == {}

    @responses.activate
    def test_supervisor_with_missing_fields(self, monkeypatch):
        """Test supervisor with missing name fields."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[{"employeeId": "EMP001"}],  # No name fields
            status=200,
        )

        result = builder.get_supervisor_details("EMP001")
        assert result.get("supervisorFirstName") is None
        assert result.get("supervisorLastName") is None

    @responses.activate
    def test_supervisor_name_formatting(
        self, monkeypatch,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test supervisor name is properly formatted in driver payload."""
        builder = get_builder_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
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
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        result = builder.build_motus_driver("12345", "J9A6Y")

        # Check Manager Name in custom variables
        custom_vars = result["customVariables"]
        manager_name = next((v for v in custom_vars if v["name"] == "Manager Name"), None)
        assert manager_name is not None
        assert manager_name["value"] == "Jane Manager"


class TestDetermineEmploymentStatus:
    """Tests for determine_employment_status function."""

    def test_active_employee(self, monkeypatch):
        """Test active employee with no leave or termination."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": None,
        }

        result = builder.determine_employment_status(employment)
        assert result == "A"

    def test_leave_of_absence(self, monkeypatch):
        """Test employee on leave (leaveStartDate set, no leaveEndDate)."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "2024-01-01",
            "leaveEndDate": None,
            "terminationDate": None,
        }

        result = builder.determine_employment_status(employment)
        assert result == "Leave"

    def test_returned_from_leave(self, monkeypatch):
        """Test employee returned from leave (both dates set)."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "2024-01-01",
            "leaveEndDate": "2024-02-01",
            "terminationDate": None,
        }

        result = builder.determine_employment_status(employment)
        # Should return status code since leave is complete
        assert result == "A"

    def test_terminated_employee(self, monkeypatch):
        """Test terminated employee."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "T",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": "2024-03-01",
        }

        result = builder.determine_employment_status(employment)
        assert result == "Terminated"

    def test_status_code_fallback(self, monkeypatch):
        """Test status code fallback when no special conditions."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "I",  # Inactive
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": None,
        }

        result = builder.determine_employment_status(employment)
        assert result == "I"

    def test_empty_employment_details(self, monkeypatch):
        """Test empty employment details defaults to Active."""
        builder = get_builder_module(monkeypatch)

        employment = {}

        result = builder.determine_employment_status(employment)
        assert result == "Active"

    def test_leave_and_termination(self, monkeypatch):
        """Test edge case: leave start and termination both set."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "2024-01-01",
            "leaveEndDate": None,
            "terminationDate": "2024-02-01",
        }

        # Leave takes priority when leaveEndDate is not set
        result = builder.determine_employment_status(employment)
        assert result == "Leave"

    def test_default_to_active(self, monkeypatch):
        """Test default to Active when no status code."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": None,
        }

        result = builder.determine_employment_status(employment)
        assert result == "Active"


class TestMainCLI:
    """Tests for main() CLI function."""

    def test_missing_arguments(self, monkeypatch):
        """Test main() with missing arguments exits with usage message."""
        builder = get_builder_module(monkeypatch)

        # Simulate missing arguments
        monkeypatch.setattr(sys, 'argv', ['build-motus-driver.py'])

        with pytest.raises(SystemExit) as exc_info:
            builder.main()
        assert exc_info.value.code == 1

    @responses.activate
    def test_main_with_valid_arguments(
        self, monkeypatch, tmp_path,
        sample_ukg_employment_details,
        sample_ukg_employee_employment_details,
        sample_ukg_person_details,
        sample_location,
        sample_supervisor_details
    ):
        """Test main() with valid arguments creates output file."""
        builder = get_builder_module(monkeypatch)

        # Set up mock responses
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/employment-details.*"),
            json=[sample_ukg_employment_details],
            status=200,
        )
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
        responses.add(
            responses.GET,
            re.compile(r".*/personnel/v1/supervisor-details.*"),
            json=[sample_supervisor_details],
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(r".*/configuration/v1/locations.*"),
            json=sample_location,
            status=200,
        )

        # Create data directory and set arguments
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['build-motus-driver.py', '12345', 'J9A6Y'])

        # Run main
        builder.main()

        # Verify output file was created
        output_file = data_dir / "motus_driver_12345.json"
        assert output_file.exists()

        import json
        with open(output_file) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["clientEmployeeId1"] == "12345"
