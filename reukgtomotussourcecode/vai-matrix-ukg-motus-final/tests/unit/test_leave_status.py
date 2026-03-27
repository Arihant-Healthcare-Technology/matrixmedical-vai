"""
Unit tests for leave of absence status handling.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_builder_module(monkeypatch):
    """Helper to get fresh builder module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "builder",
        str(Path(__file__).parent.parent.parent / "build-motus-driver.py")
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


class TestDetermineEmploymentStatus:
    """Tests for determine_employment_status function."""

    def test_returns_leave_when_on_leave(self, monkeypatch):
        """Test returns 'Leave' when employee is on leave."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "2024-03-01",
            "leaveEndDate": None,
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "Leave"

    def test_returns_active_when_leave_ended(self, monkeypatch):
        """Test returns status code when leave has ended."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "2024-01-01",
            "leaveEndDate": "2024-02-01",
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "A"  # Returns status code, not 'Leave'

    def test_returns_terminated_when_terminated(self, monkeypatch):
        """Test returns 'Terminated' when employee terminated."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "T",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": "2024-03-15"
        }

        result = builder.determine_employment_status(employment)

        assert result == "Terminated"

    def test_returns_status_code_for_active(self, monkeypatch):
        """Test returns status code for active employee."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "A"

    def test_returns_active_when_no_status_code(self, monkeypatch):
        """Test returns 'Active' when no status code."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "Active"

    def test_handles_missing_fields(self, monkeypatch):
        """Test handles missing fields gracefully."""
        builder = get_builder_module(monkeypatch)

        employment = {}  # Empty dict

        result = builder.determine_employment_status(employment)

        assert result == "Active"

    def test_leave_takes_priority_over_status_code(self, monkeypatch):
        """Test leave status takes priority over status code."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",  # Active status code
            "leaveStartDate": "2024-03-01",
            "leaveEndDate": None,  # Still on leave
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "Leave"  # Leave takes priority

    def test_termination_handles_various_date_formats(self, monkeypatch):
        """Test termination detection works with date string."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": None,
            "leaveEndDate": None,
            "terminationDate": "2024-03-15T00:00:00Z"  # ISO format
        }

        result = builder.determine_employment_status(employment)

        assert result == "Terminated"

    def test_empty_string_leave_date_treated_as_no_leave(self, monkeypatch):
        """Test empty string leave date is treated as no leave."""
        builder = get_builder_module(monkeypatch)

        employment = {
            "employeeStatusCode": "A",
            "leaveStartDate": "",  # Empty string
            "leaveEndDate": None,
            "terminationDate": None
        }

        result = builder.determine_employment_status(employment)

        assert result == "A"  # Not on leave


class TestLeaveStatusInPayload:
    """Tests for leave status in driver payload."""

    @pytest.fixture
    def mock_api_responses(self):
        """Mock API responses for build_motus_driver."""
        return {
            "employment_details": {
                "employeeNumber": "12345",
                "employeeId": "EMP001",
                "companyID": "J9A6Y",
                "primaryJobCode": "1103",
                "leaveStartDate": "2024-03-01",
                "leaveEndDate": None,
                "terminationDate": None,
                "employeeStatusCode": "A"
            },
            "employee_employment": {
                "employeeNumber": "12345",
                "employeeId": "EMP001",
                "primaryProjectCode": "PROJ1"
            },
            "person": {
                "employeeId": "EMP001",
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john@example.com",
                "addressLine1": "123 Main St",
                "addressCity": "Springfield",
                "addressState": "IL",
                "addressZipCode": "62701"
            },
            "location": {
                "description": "Main Office",
                "state": "IL"
            }
        }

    def test_derived_status_in_custom_variables(self, monkeypatch, mock_api_responses):
        """Test derived status appears in customVariables."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return []
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        status_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Derived Status"),
            None
        )

        assert status_var is not None
        assert status_var["value"] == "Leave"

    def test_derived_status_active(self, monkeypatch, mock_api_responses):
        """Test derived status is Active for normal employee."""
        builder = get_builder_module(monkeypatch)

        # Remove leave dates
        mock_api_responses["employment_details"]["leaveStartDate"] = None
        mock_api_responses["employment_details"]["leaveEndDate"] = None

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return []
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        status_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Derived Status"),
            None
        )

        assert status_var is not None
        assert status_var["value"] == "A"  # Uses status code

    def test_derived_status_terminated(self, monkeypatch, mock_api_responses):
        """Test derived status is Terminated for terminated employee."""
        builder = get_builder_module(monkeypatch)

        # Set termination date
        mock_api_responses["employment_details"]["leaveStartDate"] = None
        mock_api_responses["employment_details"]["terminationDate"] = "2024-03-15"

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return []
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        status_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Derived Status"),
            None
        )

        assert status_var is not None
        assert status_var["value"] == "Terminated"
