"""
Unit tests for manager/supervisor field implementation.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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


class TestGetSupervisorDetails:
    """Tests for get_supervisor_details function."""

    def test_returns_supervisor_data(self, monkeypatch):
        """Test returns supervisor details when available."""
        builder = get_builder_module(monkeypatch)

        mock_data = [{
            "employeeId": "EMP001",
            "supervisorFirstName": "Jane",
            "supervisorLastName": "Manager"
        }]

        with patch.object(builder, 'get_data', return_value=mock_data):
            result = builder.get_supervisor_details("EMP001")

        assert result["supervisorFirstName"] == "Jane"
        assert result["supervisorLastName"] == "Manager"

    def test_returns_empty_when_not_found(self, monkeypatch):
        """Test returns empty dict when supervisor not found."""
        builder = get_builder_module(monkeypatch)

        with patch.object(builder, 'get_data', return_value=[]):
            result = builder.get_supervisor_details("EMP001")

        assert result == {}

    def test_handles_api_error(self, monkeypatch):
        """Test handles API errors gracefully."""
        builder = get_builder_module(monkeypatch)

        with patch.object(builder, 'get_data', side_effect=SystemExit("API Error")):
            result = builder.get_supervisor_details("EMP001")

        assert result == {}

    def test_matches_employee_id(self, monkeypatch):
        """Test returns correct supervisor when multiple returned."""
        builder = get_builder_module(monkeypatch)

        mock_data = [
            {"employeeId": "EMP002", "supervisorFirstName": "Wrong", "supervisorLastName": "Person"},
            {"employeeId": "EMP001", "supervisorFirstName": "Jane", "supervisorLastName": "Manager"},
        ]

        with patch.object(builder, 'get_data', return_value=mock_data):
            result = builder.get_supervisor_details("EMP001")

        assert result["supervisorFirstName"] == "Jane"

    def test_returns_first_when_no_match(self, monkeypatch):
        """Test returns first item when no exact match."""
        builder = get_builder_module(monkeypatch)

        mock_data = [
            {"employeeId": "OTHER", "supervisorFirstName": "Default", "supervisorLastName": "Manager"}
        ]

        with patch.object(builder, 'get_data', return_value=mock_data):
            result = builder.get_supervisor_details("EMP001")

        assert result["supervisorFirstName"] == "Default"

    def test_handles_dict_response(self, monkeypatch):
        """Test handles single dict response instead of list."""
        builder = get_builder_module(monkeypatch)

        mock_data = {
            "employeeId": "EMP001",
            "supervisorFirstName": "Jane",
            "supervisorLastName": "Manager"
        }

        with patch.object(builder, 'get_data', return_value=mock_data):
            result = builder.get_supervisor_details("EMP001")

        assert result["supervisorFirstName"] == "Jane"


class TestBuildMotusDriverManagerField:
    """Tests for manager field in build_motus_driver."""

    @pytest.fixture
    def mock_api_responses(self):
        """Mock API responses for build_motus_driver."""
        return {
            "employment_details": {
                "employeeNumber": "12345",
                "employeeId": "EMP001",
                "companyID": "J9A6Y",
                "primaryJobCode": "1103",
                "startDate": "2024-01-15"
            },
            "employee_employment": {
                "employeeNumber": "12345",
                "employeeId": "EMP001",
                "primaryProjectCode": "PROJ1",
                "primaryProjectDescription": "Test Project"
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
            "supervisor": {
                "employeeId": "EMP001",
                "supervisorFirstName": "Jane",
                "supervisorLastName": "Manager"
            },
            "location": {
                "description": "Main Office",
                "state": "IL"
            }
        }

    def test_includes_manager_name_in_payload(self, monkeypatch, mock_api_responses):
        """Test manager name is included in customVariables."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return [mock_api_responses["supervisor"]]
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        # Find Manager Name in customVariables
        manager_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Manager Name"),
            None
        )

        assert manager_var is not None
        assert manager_var["value"] == "Jane Manager"

    def test_empty_manager_when_no_supervisor(self, monkeypatch, mock_api_responses):
        """Test empty manager name when no supervisor found."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return []  # No supervisor
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        manager_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Manager Name"),
            None
        )

        assert manager_var is not None
        assert manager_var["value"] == ""

    def test_manager_name_handles_only_first_name(self, monkeypatch, mock_api_responses):
        """Test manager name when only first name available."""
        builder = get_builder_module(monkeypatch)

        mock_api_responses["supervisor"] = {
            "employeeId": "EMP001",
            "supervisorFirstName": "Jane",
            "supervisorLastName": ""
        }

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return [mock_api_responses["supervisor"]]
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        manager_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Manager Name"),
            None
        )

        assert manager_var["value"] == "Jane"

    def test_manager_name_handles_only_last_name(self, monkeypatch, mock_api_responses):
        """Test manager name when only last name available."""
        builder = get_builder_module(monkeypatch)

        mock_api_responses["supervisor"] = {
            "employeeId": "EMP001",
            "supervisorFirstName": "",
            "supervisorLastName": "Manager"
        }

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [mock_api_responses["employment_details"]]
            elif "employee-employment-details" in path:
                return [mock_api_responses["employee_employment"]]
            elif "person-details" in path:
                return [mock_api_responses["person"]]
            elif "supervisor-details" in path:
                return [mock_api_responses["supervisor"]]
            elif "locations" in path:
                return mock_api_responses["location"]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("12345", "J9A6Y")

        manager_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Manager Name"),
            None
        )

        assert manager_var["value"] == "Manager"
