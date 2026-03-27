"""
Unit tests for UKG Employee Repository.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.adapters.ukg.repository import UKGEmployeeRepository
from src.domain.models.employee import Employee


class TestUKGEmployeeRepositoryInit:
    """Tests for UKGEmployeeRepository initialization."""

    def test_init_with_client(self):
        """Test initialization with client."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        assert repo._client is mock_client
        assert repo._default_company_id is None
        assert repo._person_cache == {}

    def test_init_with_default_company_id(self):
        """Test initialization with default company ID."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")

        assert repo._default_company_id == "J9A6Y"


class TestGetCompanyId:
    """Tests for _get_company_id method."""

    def test_returns_provided_company_id(self):
        """Test returns provided company ID."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client, default_company_id="DEFAULT")

        result = repo._get_company_id("PROVIDED")
        assert result == "PROVIDED"

    def test_falls_back_to_default(self):
        """Test falls back to default company ID."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client, default_company_id="DEFAULT")

        result = repo._get_company_id()
        assert result == "DEFAULT"

    def test_raises_when_no_company_id(self):
        """Test raises ValueError when no company ID available."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        with pytest.raises(ValueError) as exc_info:
            repo._get_company_id()
        assert "company_id is required" in str(exc_info.value)


class TestGetById:
    """Tests for get_by_id method."""

    def test_returns_employee_from_person_and_employment(self):
        """Test returns employee combining person and employment data."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = {
            "employeeNumber": "12345",
            "companyId": "J9A6Y",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }
        mock_client.get_employment_details.return_value = {
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
            "employeeStatusCode": "A",
            "jobTitle": "Developer",
        }

        repo = UKGEmployeeRepository(mock_client)
        result = repo.get_by_id("EMP001")

        assert result is not None
        assert result.employee_number == "12345"

    def test_returns_none_when_person_not_found(self):
        """Test returns None when person not found."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client)
        result = repo.get_by_id("UNKNOWN")

        assert result is None

    def test_returns_basic_employee_without_employment(self):
        """Test returns basic employee when employment data unavailable."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = {
            "firstName": "Jane",
            "lastName": "Smith",
            "emailAddress": "jane.smith@example.com",
            "workPhone": "555-1234",
        }

        repo = UKGEmployeeRepository(mock_client)
        result = repo.get_by_id("EMP002")

        assert result is not None
        assert result.first_name == "Jane"
        assert result.last_name == "Smith"
        assert result.email == "jane.smith@example.com"


class TestGetByEmployeeNumber:
    """Tests for get_by_employee_number method."""

    def test_returns_employee(self):
        """Test returns employee by employee number."""
        mock_client = MagicMock()
        mock_client.get_employee_full_data.return_value = {
            "employee_number": "12345",
            "company_id": "J9A6Y",
            "employee_id": "EMP001",
            "employment": {
                "employeeNumber": "12345",
                "companyID": "J9A6Y",
                "firstName": "John",
                "lastName": "Doe",
            },
            "person": {
                "emailAddress": "john.doe@example.com",
            },
        }

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_employee_number("12345")

        assert result is not None
        mock_client.get_employee_full_data.assert_called_once_with("12345", "J9A6Y")

    def test_returns_none_when_not_found(self):
        """Test returns None when employee not found."""
        mock_client = MagicMock()
        mock_client.get_employee_full_data.side_effect = ValueError("not found")

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_employee_number("99999")

        assert result is None


class TestGetActiveEmployees:
    """Tests for get_active_employees method."""

    def test_returns_active_employees(self):
        """Test returns list of active employees."""
        mock_client = MagicMock()
        mock_client.list_active_employees.return_value = [
            {"employeeNumber": "12345", "employeeId": "EMP001"},
            {"employeeNumber": "67890", "employeeId": "EMP002"},
        ]
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_active_employees()

        assert len(result) == 2
        mock_client.list_active_employees.assert_called_once_with(
            company_id="J9A6Y", page=1, page_size=200
        )

    def test_uses_provided_company_id(self):
        """Test uses provided company ID."""
        mock_client = MagicMock()
        mock_client.list_active_employees.return_value = []

        repo = UKGEmployeeRepository(mock_client, default_company_id="DEFAULT")
        repo.get_active_employees(company_id="SPECIFIC")

        mock_client.list_active_employees.assert_called_with(
            company_id="SPECIFIC", page=1, page_size=200
        )


class TestList:
    """Tests for list method."""

    def test_list_all_employees(self):
        """Test lists all employees."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeNumber": "12345"},
            {"employeeNumber": "67890"},
        ]

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.list()

        assert len(result) == 2

    def test_list_active_only(self):
        """Test lists active employees only."""
        mock_client = MagicMock()
        mock_client.list_active_employees.return_value = [
            {"employeeNumber": "12345"},
        ]

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.list(filters={"status": "active"})

        assert len(result) == 1
        mock_client.list_active_employees.assert_called_once()


class TestReadOnlyOperations:
    """Tests for read-only operation restrictions."""

    def test_create_raises_not_implemented(self):
        """Test create raises NotImplementedError."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        with pytest.raises(NotImplementedError) as exc_info:
            repo.create(MagicMock())
        assert "read-only" in str(exc_info.value)

    def test_update_raises_not_implemented(self):
        """Test update raises NotImplementedError."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        with pytest.raises(NotImplementedError) as exc_info:
            repo.update(MagicMock())
        assert "read-only" in str(exc_info.value)

    def test_delete_raises_not_implemented(self):
        """Test delete raises NotImplementedError."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        with pytest.raises(NotImplementedError) as exc_info:
            repo.delete("EMP001")
        assert "read-only" in str(exc_info.value)


class TestGetPersonDetails:
    """Tests for get_person_details method."""

    def test_returns_cached_person_details(self):
        """Test returns cached person details."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = {"firstName": "John"}

        repo = UKGEmployeeRepository(mock_client)

        # First call - should hit API
        result1 = repo.get_person_details("EMP001")
        assert result1 == {"firstName": "John"}

        # Second call - should use cache
        result2 = repo.get_person_details("EMP001")
        assert result2 == {"firstName": "John"}

        # API should only be called once
        mock_client.get_person_details.assert_called_once()

    def test_returns_empty_dict_for_unknown_id(self):
        """Test returns empty dict for unknown employee ID."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client)
        result = repo.get_person_details("UNKNOWN")

        assert result == {}


class TestClearCache:
    """Tests for clear_cache method."""

    def test_clears_person_cache(self):
        """Test clears the person details cache."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = {"firstName": "John"}

        repo = UKGEmployeeRepository(mock_client)
        repo.get_person_details("EMP001")

        assert len(repo._person_cache) == 1

        repo.clear_cache()

        assert len(repo._person_cache) == 0


class TestResolveSupervisorEmail:
    """Tests for resolve_supervisor_email method."""

    def test_returns_existing_supervisor_email(self):
        """Test returns existing supervisor email."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        employee = MagicMock()
        employee.supervisor_email = "manager@example.com"

        result = repo.resolve_supervisor_email(employee)

        assert result == "manager@example.com"

    def test_resolves_from_metadata(self):
        """Test resolves supervisor email from metadata."""
        mock_client = MagicMock()
        mock_client.get_supervisor_email.return_value = "boss@example.com"

        repo = UKGEmployeeRepository(mock_client)

        employee = MagicMock()
        employee.supervisor_email = None
        employee.metadata = {
            "ukg_data": {"supervisorEmailAddress": "boss@example.com"},
            "person_data": None,
        }

        result = repo.resolve_supervisor_email(employee)

        assert result == "boss@example.com"

    def test_fetches_employment_data_if_missing(self):
        """Test fetches employment data if not in metadata."""
        mock_client = MagicMock()
        mock_client.get_employment_details.return_value = {"supervisorEmailAddress": "sup@example.com"}
        mock_client.get_supervisor_email.return_value = "sup@example.com"

        repo = UKGEmployeeRepository(mock_client)

        employee = MagicMock()
        employee.supervisor_email = None
        employee.employee_number = "12345"
        employee.company_id = "J9A6Y"
        employee.metadata = {}

        result = repo.resolve_supervisor_email(employee)

        mock_client.get_employment_details.assert_called_once_with("12345", "J9A6Y")


class TestGetCachedPerson:
    """Tests for _get_cached_person method."""

    def test_returns_none_for_empty_id(self):
        """Test returns None for empty employee ID."""
        mock_client = MagicMock()
        repo = UKGEmployeeRepository(mock_client)

        result = repo._get_cached_person("")

        assert result is None
        mock_client.get_person_details.assert_not_called()

    def test_caches_person_details(self):
        """Test caches person details on first call."""
        mock_client = MagicMock()
        mock_client.get_person_details.return_value = {"firstName": "Jane"}

        repo = UKGEmployeeRepository(mock_client)

        result1 = repo._get_cached_person("EMP001")
        result2 = repo._get_cached_person("EMP001")

        assert result1 == {"firstName": "Jane"}
        assert result2 == {"firstName": "Jane"}
        mock_client.get_person_details.assert_called_once_with("EMP001")


class TestGetByEmail:
    """Tests for get_by_email method."""

    def test_returns_employee_when_found(self):
        """Test returns employee when email matches."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeId": "EMP001", "employeeNumber": "12345"},
        ]
        mock_client.get_person_details.return_value = {
            "emailAddress": "john.doe@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_email("john.doe@example.com")

        assert result is not None
        assert result.email == "john.doe@example.com"

    def test_returns_none_when_not_found(self):
        """Test returns None when email not found."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeId": "EMP001", "employeeNumber": "12345"},
        ]
        mock_client.get_person_details.return_value = {
            "emailAddress": "other@example.com",
        }

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_email("notfound@example.com")

        assert result is None

    def test_handles_empty_employee_list(self):
        """Test returns None when no employees."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = []

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_email("john@example.com")

        assert result is None

    def test_paginates_through_employees(self):
        """Test paginates through multiple pages."""
        mock_client = MagicMock()
        # First page returns 200 items, second page returns less
        mock_client.list_employees.side_effect = [
            [{"employeeId": f"EMP{i}", "employeeNumber": str(i)} for i in range(200)],
            [{"employeeId": "EMP200", "employeeNumber": "200"}],
        ]
        mock_client.get_person_details.side_effect = [None] * 200 + [
            {"emailAddress": "target@example.com", "firstName": "Target"}
        ]

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_by_email("target@example.com")

        assert result is not None
        assert mock_client.list_employees.call_count == 2


class TestGetEmployeesWithSupervisor:
    """Tests for get_employees_with_supervisor method."""

    def test_returns_direct_reports(self):
        """Test returns employees reporting to supervisor."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeId": "EMP001", "supervisorEmployeeId": "SUP001"},
            {"employeeId": "EMP002", "supervisorEmployeeId": "SUP002"},
            {"employeeId": "EMP003", "supervisorEmployeeId": "SUP001"},
        ]
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_employees_with_supervisor("SUP001")

        assert len(result) == 2

    def test_returns_empty_list_when_no_reports(self):
        """Test returns empty list when no direct reports."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeId": "EMP001", "supervisorEmployeeId": "SUP002"},
        ]

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_employees_with_supervisor("SUP001")

        assert len(result) == 0

    def test_handles_nested_supervisor_field(self):
        """Test handles supervisor field in nested object."""
        mock_client = MagicMock()
        mock_client.list_employees.return_value = [
            {"employeeId": "EMP001", "supervisor": {"employeeId": "SUP001"}},
        ]
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_employees_with_supervisor("SUP001")

        assert len(result) == 1

    def test_paginates_through_employees(self):
        """Test paginates through multiple pages."""
        mock_client = MagicMock()
        mock_client.list_employees.side_effect = [
            [{"employeeId": f"EMP{i}", "supervisorEmployeeId": "OTHER"} for i in range(200)],
            [{"employeeId": "EMP200", "supervisorEmployeeId": "SUP001"}],
        ]
        mock_client.get_person_details.return_value = None

        repo = UKGEmployeeRepository(mock_client, default_company_id="J9A6Y")
        result = repo.get_employees_with_supervisor("SUP001")

        assert len(result) == 1
        assert mock_client.list_employees.call_count == 2
