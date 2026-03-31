"""
Integration tests using provided test EEIDs.
These tests validate real-world scenarios with mocked UKG data.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Test EEIDs provided for validation
TEST_EEIDS = {
    "new_hires": ["28190", "28203", "28207", "28209", "28210", "28199", "28206", "28189", "28204"],
    "terminations": ["26737", "27991", "28069", "23497", "27938", "23463", "26612", "25213", "28010"],
    "manager_changes": ["28195"],
    "address_phone": ["25336", "26421", "10858", "22299"]
}


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


class TestNewHireProcessing:
    """Tests for new hire employee processing."""

    @pytest.fixture
    def new_hire_data(self):
        """Sample new hire employee data."""
        return {
            "employment_details": {
                "employeeNumber": "28190",
                "employeeId": "EMP28190",
                "companyID": "J9A6Y",
                "primaryJobCode": "1103",  # Eligible FAVR code
                "originalHireDate": "2024-03-15",
                "dateOfTermination": None,
                "employeeStatusStartDate": None,
                "employeeStatusExpectedEndDate": None,
                "employeeStatusCode": "A"
            },
            "employee_employment": {
                "employeeNumber": "28190",
                "employeeId": "EMP28190",
                "primaryProjectCode": "PROJ001"
            },
            "person": {
                "employeeId": "EMP28190",
                "firstName": "New",
                "lastName": "Hire",
                "emailAddress": "new.hire@example.com",
                "addressLine1": "456 Oak Ave",
                "addressCity": "Chicago",
                "addressState": "IL",
                "addressZipCode": "60601"
            }
        }

    def test_new_hire_has_start_date(self, monkeypatch, new_hire_data):
        """Test new hire records include start date."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [new_hire_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [new_hire_data["employee_employment"]]
            elif "person-details" in path:
                return [new_hire_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("28190", "J9A6Y")

        assert result["startDate"] == "2024-03-15"

    def test_new_hire_has_eligible_program_id(self, monkeypatch, new_hire_data):
        """Test new hires with eligible job codes get correct program ID."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [new_hire_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [new_hire_data["employee_employment"]]
            elif "person-details" in path:
                return [new_hire_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("28190", "J9A6Y")

        # Job code 1103 maps to FAVR program ID 21232
        assert result["programId"] == 21232


class TestTerminationProcessing:
    """Tests for termination handling."""

    @pytest.fixture
    def terminated_data(self):
        """Sample terminated employee data."""
        return {
            "employment_details": {
                "employeeNumber": "26737",
                "employeeId": "EMP26737",
                "companyID": "J9A6Y",
                "primaryJobCode": "1103",
                "originalHireDate": "2020-01-15",
                "dateOfTermination": "2024-03-01",
                "employeeStatusStartDate": None,
                "employeeStatusExpectedEndDate": None,
                "employeeStatusCode": "T"
            },
            "employee_employment": {
                "employeeNumber": "26737",
                "employeeId": "EMP26737"
            },
            "person": {
                "employeeId": "EMP26737",
                "firstName": "Terminated",
                "lastName": "Employee",
                "emailAddress": "terminated@example.com"
            }
        }

    def test_terminated_employee_has_end_date(self, monkeypatch, terminated_data):
        """Test terminated employee has endDate populated."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [terminated_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [terminated_data["employee_employment"]]
            elif "person-details" in path:
                return [terminated_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("26737", "J9A6Y")

        assert result["endDate"] == "2024-03-01"

    def test_termination_date_in_custom_variables(self, monkeypatch, terminated_data):
        """Test termination date appears in customVariables."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [terminated_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [terminated_data["employee_employment"]]
            elif "person-details" in path:
                return [terminated_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("26737", "J9A6Y")

        term_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Termination Date"),
            None
        )
        assert term_var is not None
        assert term_var["value"] == "2024-03-01"

    def test_derived_status_is_terminated(self, monkeypatch, terminated_data):
        """Test derived status is Terminated for terminated employee."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [terminated_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [terminated_data["employee_employment"]]
            elif "person-details" in path:
                return [terminated_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("26737", "J9A6Y")

        status_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Derived Status"),
            None
        )
        assert status_var is not None
        assert status_var["value"] == "Terminated"


class TestManagerChanges:
    """Tests for manager change tracking."""

    @pytest.fixture
    def employee_with_manager(self):
        """Sample employee data with manager."""
        return {
            "employment_details": {
                "employeeNumber": "28195",
                "employeeId": "EMP28195",
                "companyID": "J9A6Y",
                "primaryJobCode": "1103",
                "originalHireDate": "2022-06-01"
            },
            "employee_employment": {
                "employeeNumber": "28195",
                "employeeId": "EMP28195"
            },
            "person": {
                "employeeId": "EMP28195",
                "firstName": "Regular",
                "lastName": "Employee",
                "emailAddress": "regular@example.com"
            },
            "supervisor": {
                "employeeId": "EMP28195",
                "supervisorFirstName": "New",
                "supervisorLastName": "Manager"
            }
        }

    def test_manager_name_populated(self, monkeypatch, employee_with_manager):
        """Test manager name is populated for employees."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [employee_with_manager["employment_details"]]
            elif "employee-employment-details" in path:
                return [employee_with_manager["employee_employment"]]
            elif "person-details" in path:
                return [employee_with_manager["person"]]
            elif "supervisor-details" in path:
                return [employee_with_manager["supervisor"]]
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("28195", "J9A6Y")

        manager_var = next(
            (cv for cv in result["customVariables"] if cv["name"] == "Manager Name"),
            None
        )
        assert manager_var is not None
        assert manager_var["value"] == "New Manager"


class TestAddressPhoneUpdates:
    """Tests for address and phone updates."""

    @pytest.fixture
    def employee_data(self):
        """Sample employee data with address and phone."""
        return {
            "employment_details": {
                "employeeNumber": "25336",
                "employeeId": "EMP25336",
                "companyID": "J9A6Y",
                "primaryJobCode": "2817",  # CPM code
                "originalHireDate": "2021-09-01"
            },
            "employee_employment": {
                "employeeNumber": "25336",
                "employeeId": "EMP25336"
            },
            "person": {
                "employeeId": "EMP25336",
                "firstName": "Address",
                "lastName": "Test",
                "emailAddress": "address.test@example.com",
                "addressLine1": "789 Updated St",
                "addressLine2": "Apt 123",
                "addressCity": "New York",
                "addressState": "NY",
                "addressZipCode": "10001",
                "addressCountry": "US",
                "homePhone": "5551234567",
                "mobilePhone": "5559876543"
            }
        }

    def test_address_fields_populated(self, monkeypatch, employee_data):
        """Test all address fields are populated."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [employee_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [employee_data["employee_employment"]]
            elif "person-details" in path:
                return [employee_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("25336", "J9A6Y")

        assert result["address1"] == "789 Updated St"
        assert result["address2"] == "Apt 123"
        assert result["city"] == "New York"
        assert result["stateProvince"] == "NY"
        assert result["postalCode"] == "10001"
        assert result["country"] == "US"

    def test_phone_normalized(self, monkeypatch, employee_data):
        """Test phone number is normalized correctly."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [employee_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [employee_data["employee_employment"]]
            elif "person-details" in path:
                return [employee_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("25336", "J9A6Y")

        # Phone should be normalized to XXX-XXX-XXXX format
        assert result["phone"] == "555-123-4567"

    def test_email_populated(self, monkeypatch, employee_data):
        """Test email is populated."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [employee_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [employee_data["employee_employment"]]
            elif "person-details" in path:
                return [employee_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("25336", "J9A6Y")

        assert result["email"] == "address.test@example.com"

    def test_cpm_program_id_assigned(self, monkeypatch, employee_data):
        """Test CPM job code maps to correct program ID."""
        builder = get_builder_module(monkeypatch)

        def mock_get_data(path, params=None):
            if "employment-details" in path and "employee-" not in path:
                return [employee_data["employment_details"]]
            elif "employee-employment-details" in path:
                return [employee_data["employee_employment"]]
            elif "person-details" in path:
                return [employee_data["person"]]
            elif "supervisor-details" in path:
                return []
            return []

        with patch.object(builder, 'get_data', side_effect=mock_get_data):
            result = builder.build_motus_driver("25336", "J9A6Y")

        # Job code 2817 maps to CPM program ID 21233
        assert result["programId"] == 21233
