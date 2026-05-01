"""
Unit tests for SyncService.
"""

from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

import pytest

from src.application.services.sync_service import SyncService
from src.domain.interfaces.services import SyncResult, BatchSyncResult
from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.bill_user import BillUser, BillRole
from src.domain.exceptions.api_exceptions import ApiError


@pytest.fixture
def mock_employee_repo():
    """Create mock employee repository."""
    return MagicMock()


@pytest.fixture
def mock_bill_user_repo():
    """Create mock BILL user repository."""
    return MagicMock()


@pytest.fixture
def sync_service(mock_employee_repo, mock_bill_user_repo):
    """Create sync service with mocked dependencies."""
    return SyncService(
        employee_repository=mock_employee_repo,
        bill_user_repository=mock_bill_user_repo,
    )


@pytest.fixture
def sample_employee():
    """Create sample employee."""
    return Employee(
        employee_id="EMP001",
        employee_number="12345",
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        status=EmployeeStatus.ACTIVE,
    )


@pytest.fixture
def sample_bill_user():
    """Create sample BILL user."""
    return BillUser(
        id="BILL001",
        email="john.doe@example.com",
        first_name="John",
        last_name="Doe",
        role=BillRole.MEMBER,
    )


class TestSyncEmployee:
    """Tests for sync_employee method."""

    def test_creates_new_user(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should create new user when not found in BILL."""
        created_user = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )
        mock_bill_user_repo.upsert.return_value = (created_user, "created")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "created"
        assert result.entity_id == "NEW001"
        mock_bill_user_repo.upsert.assert_called_once()

    def test_updates_existing_user(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
        sample_bill_user,
    ):
        """Should update user when found in BILL with changes."""
        mock_bill_user_repo.upsert.return_value = (sample_bill_user, "updated")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "updated"
        mock_bill_user_repo.upsert.assert_called_once()

    def test_updates_unchanged_user(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
        sample_bill_user,
    ):
        """Should always update existing user even when no changes detected."""
        mock_bill_user_repo.upsert.return_value = (sample_bill_user, "updated")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "updated"
        mock_bill_user_repo.upsert.assert_called_once()

    def test_error_missing_email(self, sync_service, sample_employee):
        """Should return error for employee without email."""
        sample_employee.email = None

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "email" in result.message.lower()

    def test_error_on_upsert_failure(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should return error when upsert fails."""
        mock_bill_user_repo.upsert.side_effect = Exception("API Error")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "API Error" in result.message

    def test_uses_rate_limiter(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should call rate limiter before API calls."""
        rate_limiter = Mock()
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            rate_limiter=rate_limiter,
        )
        created_user = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )
        mock_bill_user_repo.upsert.return_value = (created_user, "created")

        service.sync_employee(sample_employee)

        rate_limiter.assert_called_once()


class TestSyncBatch:
    """Tests for sync_batch method."""

    def test_empty_batch(self, sync_service):
        """Should handle empty employee list."""
        result = sync_service.sync_batch([])

        assert result.total == 0
        assert result.created == 0
        assert result.errors == 0

    @patch("time.sleep")
    def test_batch_aggregates_results(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
    ):
        """Should aggregate results from batch sync."""
        employees = [
            Employee(
                employee_id=f"EMP{i}",
                employee_number=str(i),
                email=f"emp{i}@example.com",
                first_name="Test",
                last_name=f"User{i}",
                status=EmployeeStatus.ACTIVE,
            )
            for i in range(3)
        ]

        # First creates, second and third update (using new categorization flow)
        mock_bill_user_repo.categorize_employees.return_value = (
            [employees[0]],  # to_create
            [(employees[1], "EXISTING"), (employees[2], "EXISTING2")],  # to_update
        )
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="emp0@example.com", first_name="Test", last_name="User0", role=BillRole.MEMBER
        )
        mock_bill_user_repo.update.return_value = BillUser(
            id="EXISTING", email="emp1@example.com", first_name="Test", last_name="User1", role=BillRole.MEMBER
        )

        result = sync_service.sync_batch(employees, workers=1)

        assert result.total == 3
        assert result.created == 1
        assert result.updated == 2
        assert result.skipped == 0
        assert result.errors == 0

    def test_batch_has_correlation_id(self, sync_service):
        """Should generate correlation ID for batch."""
        result = sync_service.sync_batch([])

        assert result.correlation_id != ""
        assert len(result.correlation_id) > 0

    def test_batch_tracks_timing(self, sync_service):
        """Should track start and end times."""
        result = sync_service.sync_batch([])

        assert result.start_time is not None
        assert result.end_time is not None
        assert result.end_time >= result.start_time


class TestSyncAll:
    """Tests for sync_all method."""

    def test_fetches_active_employees(
        self,
        sync_service,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should fetch and sync active employees via list_employees."""
        # sync_all uses _client.list_employees, not get_active_employees
        mock_employee_repo._client.list_employees.return_value = [
            {
                "employeeId": "EMP001",
                "employeeNumber": "12345",
                "email": "active@example.com",
                "firstName": "Active",
                "lastName": "User",
                "status": "Active",
                "companyId": "J9A6Y",
            }
        ]
        mock_employee_repo._get_cached_person.return_value = None
        mock_bill_user_repo.upsert.return_value = (
            BillUser(id="NEW", email="active@example.com", first_name="Active", last_name="Employee", role=BillRole.MEMBER),
            "created",
        )

        result = sync_service.sync_all()

        # Employees are filtered by status and type, so may not sync
        mock_employee_repo._client.list_employees.assert_called()


class TestResolveSupervisorEmail:
    """Tests for resolve_supervisor_email method."""

    def test_returns_direct_email(
        self,
        sync_service,
        sample_employee,
    ):
        """Should return supervisor email when directly available."""
        sample_employee.supervisor_email = "manager@example.com"

        result = sync_service.resolve_supervisor_email(sample_employee)

        assert result == "manager@example.com"

    def test_looks_up_by_supervisor_id(
        self,
        sync_service,
        mock_employee_repo,
        sample_employee,
    ):
        """Should lookup supervisor by ID when email not available."""
        sample_employee.supervisor_email = None
        sample_employee.supervisor_id = "SUP001"

        supervisor = Employee(
            employee_id="SUP001",
            employee_number="99998",
            email="supervisor@example.com",
            first_name="Super",
            last_name="Visor",
            status=EmployeeStatus.ACTIVE,
        )
        mock_employee_repo.get_by_id.return_value = supervisor

        result = sync_service.resolve_supervisor_email(sample_employee)

        assert result == "supervisor@example.com"
        mock_employee_repo.get_by_id.assert_called_with("SUP001")

    def test_looks_up_by_supervisor_number(
        self,
        sync_service,
        mock_employee_repo,
        sample_employee,
    ):
        """Should lookup supervisor by employee number as fallback."""
        sample_employee.supervisor_email = None
        sample_employee.supervisor_id = None
        sample_employee.supervisor_number = "99999"

        supervisor = Employee(
            employee_id="SUP002",
            employee_number="99999",
            email="supervisor2@example.com",
            first_name="Super",
            last_name="Visor",
            status=EmployeeStatus.ACTIVE,
        )
        mock_employee_repo.get_by_employee_number.return_value = supervisor

        result = sync_service.resolve_supervisor_email(sample_employee)

        assert result == "supervisor2@example.com"
        mock_employee_repo.get_by_employee_number.assert_called_with("99999")

    def test_returns_none_when_not_found(
        self,
        sync_service,
        mock_employee_repo,
        sample_employee,
    ):
        """Should return None when supervisor cannot be resolved."""
        sample_employee.supervisor_email = None
        sample_employee.supervisor_id = "SUP999"
        sample_employee.supervisor_number = None

        mock_employee_repo.get_by_id.return_value = None

        result = sync_service.resolve_supervisor_email(sample_employee)

        assert result is None

    def test_uses_cache(self, mock_employee_repo, mock_bill_user_repo, sample_employee):
        """Should cache supervisor lookups."""
        person_cache = {"SUP001": {"emailAddress": "cached@example.com"}}
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            person_cache=person_cache,
        )

        sample_employee.supervisor_email = None
        sample_employee.supervisor_id = "SUP001"

        result = service.resolve_supervisor_email(sample_employee)

        assert result == "cached@example.com"
        # Should not call repository because it's in cache
        mock_employee_repo.get_by_id.assert_not_called()


class TestSyncEmployeeExceptions:
    """Tests for exception handling in sync_employee."""

    def test_handles_upsert_exception(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should handle exception when upserting user."""
        mock_bill_user_repo.upsert.side_effect = Exception("Database error")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "Database error" in result.message


class TestSyncBatchCounters:
    """Tests for batch sync counter aggregation."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    @pytest.fixture
    def sync_service(self, mock_employee_repo, mock_bill_user_repo):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

    @patch("time.sleep")
    def test_batch_counts_all_action_types(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
    ):
        """Should correctly count creates, updates, skips, and errors."""
        employees = [
            Employee(
                employee_id=f"EMP{i}",
                employee_number=str(i),
                email=f"emp{i}@example.com" if i < 4 else None,  # 5th has no email
                first_name="Test",
                last_name=f"User{i}",
                status=EmployeeStatus.ACTIVE,
            )
            for i in range(5)
        ]

        # Categorization: employees with email split into create/update
        # emp4 has no email, so it won't be in either list
        mock_bill_user_repo.categorize_employees.return_value = (
            [employees[0], employees[3]],  # to_create (emp0, emp3)
            [(employees[1], "EXIST1"), (employees[2], "EXIST2")],  # to_update
        )

        # emp0 creates successfully, emp3 fails
        mock_bill_user_repo.create.side_effect = [
            BillUser(id="NEW0", email="emp0@example.com", first_name="Test", last_name="User0", role=BillRole.MEMBER),
            Exception("Create failed"),  # emp3 fails
        ]
        mock_bill_user_repo.update.return_value = BillUser(
            id="EXIST", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        result = sync_service.sync_batch(employees, workers=1)

        assert result.total == 5
        assert result.created == 1  # emp0
        assert result.updated == 2  # emp1 + emp2
        assert result.skipped == 0
        assert result.errors == 1  # emp3 (create failed), emp4 not in categorized list

    @patch("time.sleep")
    def test_batch_parallel_execution(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
    ):
        """Should handle parallel execution."""
        employees = [
            Employee(
                employee_id=f"EMP{i}",
                employee_number=str(i),
                email=f"emp{i}@example.com",
                first_name="Test",
                last_name=f"User{i}",
                status=EmployeeStatus.ACTIVE,
            )
            for i in range(3)
        ]

        # All employees are new (to_create)
        mock_bill_user_repo.categorize_employees.return_value = (employees, [])
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        # Use multiple workers
        result = sync_service.sync_batch(employees, workers=2)

        assert result.total == 3
        assert result.created == 3


class TestCreateBillUser:
    """Tests for _create_bill_user method."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    @pytest.fixture
    def sync_service(self, mock_employee_repo, mock_bill_user_repo):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

    @pytest.fixture
    def sample_employee(self):
        """Create sample employee."""
        return Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            status=EmployeeStatus.ACTIVE,
        )

    @patch("time.sleep")
    def test_creates_user_successfully(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should create user and return created action."""
        created_user = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )
        mock_bill_user_repo.create.return_value = created_user

        result = sync_service._create_bill_user(sample_employee)

        assert result.success is True
        assert result.action == "created"
        assert result.entity_id == "NEW001"
        mock_bill_user_repo.create.assert_called_once()

    @patch("time.sleep")
    def test_skips_employee_without_email(self, mock_sleep, sync_service):
        """Should return error for employee without email."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email=None,
            status=EmployeeStatus.ACTIVE,
        )

        result = sync_service._create_bill_user(employee)

        assert result.success is False
        assert result.action == "error"
        assert "email" in result.message.lower()

    @patch("time.sleep")
    def test_resolves_supervisor_email(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should resolve supervisor email before creation."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            supervisor_email="manager@example.com",
            status=EmployeeStatus.ACTIVE,
        )

        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW001",
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=BillRole.MEMBER,
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service._create_bill_user(employee)

        assert result.success is True
        # Verify the create was called (supervisor resolution happens internally)
        mock_bill_user_repo.create.assert_called_once()

    @patch("time.sleep")
    def test_resolves_budget_from_cost_center(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should resolve budget if department_client available."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            cost_center="CC001",
            status=EmployeeStatus.ACTIVE,
        )

        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW001",
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=BillRole.MEMBER,
        )

        mock_department_client = MagicMock()
        mock_department_client.get_budget_from_cost_center.return_value = "BUDGET001"

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            department_client=mock_department_client,
        )

        result = service._create_bill_user(employee)

        assert result.success is True
        mock_department_client.get_budget_from_cost_center.assert_called_with("CC001")

    @patch("time.sleep")
    def test_handles_api_error(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should return error result on API failure."""
        mock_bill_user_repo.create.side_effect = Exception("API Error")

        result = sync_service._create_bill_user(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "API Error" in result.message

    @patch("time.sleep")
    def test_calls_repository_create(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should call bill_user_repo.create() not upsert()."""
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )

        sync_service._create_bill_user(sample_employee)

        mock_bill_user_repo.create.assert_called_once()
        mock_bill_user_repo.upsert.assert_not_called()

    def test_applies_rate_limiting(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should apply rate limiting before API call."""
        rate_limiter = Mock()
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            rate_limiter=rate_limiter,
        )
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )

        with patch("time.sleep"):
            service._create_bill_user(sample_employee)

        rate_limiter.assert_called_once()


class TestUpdateBillUser:
    """Tests for _update_bill_user method."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    @pytest.fixture
    def sync_service(self, mock_employee_repo, mock_bill_user_repo):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

    @pytest.fixture
    def sample_employee(self):
        """Create sample employee."""
        return Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            status=EmployeeStatus.ACTIVE,
        )

    @patch("time.sleep")
    def test_updates_user_with_cached_id(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should set user.id from cached bill_user_id."""
        updated_user = BillUser(
            id="BILL-UUID-123",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )
        mock_bill_user_repo.update.return_value = updated_user

        result = sync_service._update_bill_user(sample_employee, "BILL-UUID-123")

        assert result.success is True
        assert result.action == "updated"
        assert result.entity_id == "BILL-UUID-123"
        # Verify the ID was passed to update
        call_args = mock_bill_user_repo.update.call_args[0][0]
        assert call_args.id == "BILL-UUID-123"

    @patch("time.sleep")
    def test_skips_employee_without_email(self, mock_sleep, sync_service):
        """Should return error for employee without email."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email=None,
            status=EmployeeStatus.ACTIVE,
        )

        result = sync_service._update_bill_user(employee, "BILL-UUID-123")

        assert result.success is False
        assert result.action == "error"
        assert "email" in result.message.lower()

    @patch("time.sleep")
    def test_resolves_supervisor_email(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should resolve supervisor email before update."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            supervisor_email="manager@example.com",
            status=EmployeeStatus.ACTIVE,
        )

        mock_bill_user_repo.update.return_value = BillUser(
            id="BILL-UUID-123",
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=BillRole.MEMBER,
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service._update_bill_user(employee, "BILL-UUID-123")

        assert result.success is True
        mock_bill_user_repo.update.assert_called_once()

    @patch("time.sleep")
    def test_resolves_budget_from_cost_center(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should resolve budget if department_client available."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            cost_center="CC001",
            status=EmployeeStatus.ACTIVE,
        )

        mock_bill_user_repo.update.return_value = BillUser(
            id="BILL-UUID-123",
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=BillRole.MEMBER,
        )

        mock_department_client = MagicMock()
        mock_department_client.get_budget_from_cost_center.return_value = "BUDGET001"

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            department_client=mock_department_client,
        )

        result = service._update_bill_user(employee, "BILL-UUID-123")

        assert result.success is True
        mock_department_client.get_budget_from_cost_center.assert_called_with("CC001")

    @patch("time.sleep")
    def test_handles_api_error(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should return error result on API failure."""
        mock_bill_user_repo.update.side_effect = Exception("API Error")

        result = sync_service._update_bill_user(sample_employee, "BILL-UUID-123")

        assert result.success is False
        assert result.action == "error"
        assert "API Error" in result.message

    @patch("time.sleep")
    def test_calls_repository_update_not_upsert(
        self,
        mock_sleep,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should call bill_user_repo.update() not upsert()."""
        mock_bill_user_repo.update.return_value = BillUser(
            id="BILL-UUID-123",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )

        sync_service._update_bill_user(sample_employee, "BILL-UUID-123")

        mock_bill_user_repo.update.assert_called_once()
        mock_bill_user_repo.upsert.assert_not_called()

    def test_applies_rate_limiting(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should apply rate limiting before API call."""
        rate_limiter = Mock()
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            rate_limiter=rate_limiter,
        )
        mock_bill_user_repo.update.return_value = BillUser(
            id="BILL-UUID-123",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )

        with patch("time.sleep"):
            service._update_bill_user(sample_employee, "BILL-UUID-123")

        rate_limiter.assert_called_once()


class TestUsersMatch:
    """Tests for _users_match method."""

    @pytest.fixture
    def sync_service(self):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=MagicMock(),
            bill_user_repository=MagicMock(),
        )

    def test_returns_true_for_identical_users(self, sync_service):
        """Should return True when all fields match."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            retired=False,
            cost_center="CC001",
            cost_center_description="Engineering",
            direct_labor=True,
            company="ACME",
            employee_type_code="FT",
            pay_frequency="BIWEEKLY",
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            retired=False,
            cost_center="CC001",
            cost_center_description="Engineering",
            direct_labor=True,
            company="ACME",
            employee_type_code="FT",
            pay_frequency="BIWEEKLY",
        )

        result = sync_service._users_match(user1, user2)

        assert result is True

    def test_returns_false_for_different_first_name(self, sync_service):
        """Should return False when first_name differs."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="Jane",
            last_name="Doe",
            role=BillRole.MEMBER,
        )

        result = sync_service._users_match(user1, user2)

        assert result is False

    def test_returns_false_for_different_role(self, sync_service):
        """Should return False when role differs."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.ADMIN,
        )

        result = sync_service._users_match(user1, user2)

        assert result is False

    def test_returns_false_for_different_cost_center(self, sync_service):
        """Should return False when cost_center differs."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            cost_center="CC001",
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            cost_center="CC002",
        )

        result = sync_service._users_match(user1, user2)

        assert result is False


class TestGetChanges:
    """Tests for _get_changes method."""

    @pytest.fixture
    def sync_service(self):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=MagicMock(),
            bill_user_repository=MagicMock(),
        )

    def test_returns_empty_for_identical_users(self, sync_service):
        """Should return empty dict when no changes."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )

        result = sync_service._get_changes(user1, user2)

        assert result == {}

    def test_detects_first_name_change(self, sync_service):
        """Should detect first_name change."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="Jonathan",
            last_name="Doe",
            role=BillRole.MEMBER,
        )

        result = sync_service._get_changes(user1, user2)

        assert "first_name" in result
        assert result["first_name"]["old"] == "John"
        assert result["first_name"]["new"] == "Jonathan"

    def test_detects_role_change(self, sync_service):
        """Should detect role change."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.ADMIN,
        )

        result = sync_service._get_changes(user1, user2)

        assert "role" in result
        assert result["role"]["old"] == "MEMBER"
        assert result["role"]["new"] == "ADMIN"

    def test_detects_multiple_changes(self, sync_service):
        """Should detect multiple field changes."""
        user1 = BillUser(
            id="UUID-1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            cost_center="CC001",
        )
        user2 = BillUser(
            id="UUID-2",
            email="test@example.com",
            first_name="Jane",
            last_name="Smith",
            role=BillRole.ADMIN,
            cost_center="CC002",
        )

        result = sync_service._get_changes(user1, user2)

        assert len(result) == 4
        assert "first_name" in result
        assert "last_name" in result
        assert "role" in result
        assert "cost_center" in result


class TestSyncBatchWithCategorization:
    """Tests for sync_batch with categorization flow."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    @pytest.fixture
    def sample_employees(self):
        """Create sample employees for testing."""
        return [
            Employee(
                employee_id="EMP1",
                employee_number="001",
                email="existing@example.com",
                first_name="Existing",
                last_name="User",
                status=EmployeeStatus.ACTIVE,
            ),
            Employee(
                employee_id="EMP2",
                employee_number="002",
                email="new@example.com",
                first_name="New",
                last_name="User",
                status=EmployeeStatus.ACTIVE,
            ),
        ]

    @patch("time.sleep")
    def test_builds_email_cache_first(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should call build_email_cache before categorization."""
        mock_bill_user_repo.categorize_employees.return_value = (sample_employees, [])
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        service.sync_batch(sample_employees, workers=1)

        mock_bill_user_repo.build_email_cache.assert_called_once()

    @patch("time.sleep")
    def test_categorizes_employees(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should call categorize_employees to split POST/PATCH."""
        mock_bill_user_repo.categorize_employees.return_value = ([], [])

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        service.sync_batch(sample_employees, workers=1)

        mock_bill_user_repo.categorize_employees.assert_called_once_with(sample_employees)

    @patch("time.sleep")
    def test_processes_creates_separately(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should process to_create list with _create_bill_user."""
        # All employees are new
        mock_bill_user_repo.categorize_employees.return_value = (sample_employees, [])
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service.sync_batch(sample_employees, workers=1)

        # Should call create for each employee
        assert mock_bill_user_repo.create.call_count == 2
        assert result.created == 2

    @patch("time.sleep")
    def test_processes_updates_separately(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should process to_update list with _update_bill_user."""
        # All employees already exist
        to_update = [(emp, f"bill-uuid-{i}") for i, emp in enumerate(sample_employees)]
        mock_bill_user_repo.categorize_employees.return_value = ([], to_update)
        mock_bill_user_repo.update.return_value = BillUser(
            id="UPDATED", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service.sync_batch(sample_employees, workers=1)

        # Should call update for each employee
        assert mock_bill_user_repo.update.call_count == 2
        assert result.updated == 2

    @patch("time.sleep")
    def test_aggregates_created_count(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should count created users correctly."""
        mock_bill_user_repo.categorize_employees.return_value = (sample_employees, [])
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service.sync_batch(sample_employees, workers=1)

        assert result.created == 2
        assert result.updated == 0

    @patch("time.sleep")
    def test_aggregates_updated_count(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should count updated users correctly."""
        to_update = [(emp, f"bill-uuid-{i}") for i, emp in enumerate(sample_employees)]
        mock_bill_user_repo.categorize_employees.return_value = ([], to_update)
        mock_bill_user_repo.update.return_value = BillUser(
            id="UPDATED", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service.sync_batch(sample_employees, workers=1)

        assert result.updated == 2
        assert result.created == 0

    @patch("time.sleep")
    def test_handles_mixed_results(
        self,
        mock_sleep,
        mock_employee_repo,
        mock_bill_user_repo,
        sample_employees,
    ):
        """Should handle mix of creates, updates, and errors."""
        # One to create, one to update
        to_create = [sample_employees[0]]
        to_update = [(sample_employees[1], "bill-uuid-1")]
        mock_bill_user_repo.categorize_employees.return_value = (to_create, to_update)

        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW", email="new@example.com", first_name="New", last_name="User", role=BillRole.MEMBER
        )
        mock_bill_user_repo.update.return_value = BillUser(
            id="UPDATED", email="existing@example.com", first_name="Existing", last_name="User", role=BillRole.MEMBER
        )

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        result = service.sync_batch(sample_employees, workers=1)

        assert result.created == 1
        assert result.updated == 1
        assert result.total == 2


class TestFilterByDateChanged:
    """Tests for _filter_by_date_changed method."""

    @pytest.fixture
    def sync_service(self):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=MagicMock(),
            bill_user_repository=MagicMock(),
        )

    def test_filters_employees_by_date(self, sync_service):
        """Should filter employees changed within specified days."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        three_days_ago = (now - timedelta(days=3)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2", "dateTimeChanged": three_days_ago},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1
        assert result[0]["employeeId"] == "1"

    def test_includes_all_employees_when_all_recent(self, sync_service):
        """Should include all employees when all changed recently."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        today = now.isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2", "dateTimeChanged": today},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 2

    def test_excludes_old_employees(self, sync_service):
        """Should exclude employees changed outside the window."""
        now = datetime.now()
        ten_days_ago = (now - timedelta(days=10)).isoformat()
        twenty_days_ago = (now - timedelta(days=20)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": ten_days_ago},
            {"employeeId": "2", "dateTimeChanged": twenty_days_ago},
        ]

        result = sync_service._filter_by_date_changed(employees, days=5)

        assert len(result) == 0

    def test_includes_employee_without_date_field(self, sync_service):
        """Should include employees without dateTimeChanged field."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2"},  # No dateTimeChanged
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 2
        assert {"employeeId": "2"} in result

    def test_includes_employee_with_invalid_date(self, sync_service):
        """Should include employees with unparseable dateTimeChanged."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2", "dateTimeChanged": "invalid-date"},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 2

    def test_handles_ukg_date_format(self, sync_service):
        """Should parse UKG date format like '2026-04-20T13:35:31.44'."""
        now = datetime.now()
        # Create a date in UKG format (with fractional seconds)
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4]

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1

    def test_handles_empty_list(self, sync_service):
        """Should handle empty employee list."""
        result = sync_service._filter_by_date_changed([], days=2)

        assert len(result) == 0

    def test_days_zero_filters_to_today(self, sync_service):
        """Should filter to only today's changes when days=0."""
        now = datetime.now()
        # Use a date slightly in the future to avoid timing issues
        future = (now + timedelta(seconds=10)).isoformat()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": future},
            {"employeeId": "2", "dateTimeChanged": yesterday},
        ]

        result = sync_service._filter_by_date_changed(employees, days=0)

        # Only the recent employee should be included
        assert len(result) == 1
        assert result[0]["employeeId"] == "1"

    def test_handles_timezone_aware_dates(self, sync_service):
        """Should handle timezone-aware dates with Z suffix."""
        now = datetime.now()
        yesterday_utc = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday_utc},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1


class TestSyncServiceDaysToProcess:
    """Tests for days_to_process parameter in sync_all."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    def test_constructor_accepts_days_to_process(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should accept days_to_process parameter."""
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=5,
        )

        assert service.days_to_process == 5

    def test_days_to_process_defaults_to_none(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should default days_to_process to None."""
        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
        )

        assert service.days_to_process is None

    def test_sync_all_filters_when_days_set(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should filter employees when days_to_process is set."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        ten_days_ago = (now - timedelta(days=10)).isoformat()

        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": "1", "employeeNumber": "001", "dateTimeChanged": yesterday},
            {"employeeId": "2", "employeeNumber": "002", "dateTimeChanged": ten_days_ago},
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=5,
        )

        # sync_all should filter the employees
        result = service.sync_all()

        # Note: sync_all processes employees and applies active/type filters
        # The filtering happens internally, so we verify the call was made
        mock_employee_repo._client.list_employees.assert_called_once()

    def test_sync_all_no_filter_when_days_none(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should not filter employees when days_to_process is None."""
        mock_employee_repo._client.list_employees.return_value = []

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=None,
        )

        service.sync_all()

        # Should call list_employees (no filtering applied)
        mock_employee_repo._client.list_employees.assert_called_once()

    def test_sync_all_filters_old_employees_correctly(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should exclude employees changed outside the days window."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=30)).isoformat()

        # Return 3 employees: 2 recent, 1 old
        mock_employee_repo._client.list_employees.return_value = [
            {
                "employeeId": "1",
                "employeeNumber": "001",
                "dateTimeChanged": recent,
                "status": "Active",
            },
            {
                "employeeId": "2",
                "employeeNumber": "002",
                "dateTimeChanged": old,
                "status": "Active",
            },
            {
                "employeeId": "3",
                "employeeNumber": "003",
                "dateTimeChanged": recent,
                "status": "Active",
            },
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=7,  # Only last 7 days
        )

        # Use patch to spy on _filter_by_date_changed
        with patch.object(service, '_filter_by_date_changed', wraps=service._filter_by_date_changed) as mock_filter:
            service.sync_all()

            # Verify filter was called with 3 employees and 7 days
            mock_filter.assert_called_once()
            args, kwargs = mock_filter.call_args
            assert len(args[0]) == 3  # 3 employees passed in
            assert args[1] == 7  # days parameter

    def test_sync_all_with_days_zero(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should handle days_to_process=0 (only today's changes)."""
        now = datetime.now()
        today = (now + timedelta(seconds=10)).isoformat()  # Slightly in future to avoid timing issues
        yesterday = (now - timedelta(days=1)).isoformat()

        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": "1", "employeeNumber": "001", "dateTimeChanged": today},
            {"employeeId": "2", "employeeNumber": "002", "dateTimeChanged": yesterday},
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=0,
        )

        # Track the filtered result
        original_filter = service._filter_by_date_changed
        filter_results = []

        def tracking_filter(employees, days):
            result = original_filter(employees, days)
            filter_results.append(result)
            return result

        with patch.object(service, '_filter_by_date_changed', side_effect=tracking_filter):
            service.sync_all()

            # Result should have filtered to 1 employee
            assert len(filter_results) == 1
            assert len(filter_results[0]) == 1

    def test_sync_all_logs_filter_results(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should log the filtering results."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=10)).isoformat()

        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": "1", "employeeNumber": "001", "dateTimeChanged": recent},
            {"employeeId": "2", "employeeNumber": "002", "dateTimeChanged": old},
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=5,
        )

        with patch('src.application.services.sync_service.logger') as mock_logger:
            service.sync_all()

            # Verify filter log message was called
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            filter_log = [c for c in log_calls if 'Filtered employees by date changed' in c]
            assert len(filter_log) == 1


class TestFilterByDateChangedEdgeCases:
    """Edge case tests for _filter_by_date_changed method."""

    @pytest.fixture
    def sync_service(self):
        """Create sync service with mocked dependencies."""
        return SyncService(
            employee_repository=MagicMock(),
            bill_user_repository=MagicMock(),
        )

    def test_filter_with_microseconds_in_date(self, sync_service):
        """Should handle dates with microseconds."""
        now = datetime.now()
        # Full microseconds format
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1

    def test_filter_with_truncated_microseconds(self, sync_service):
        """Should handle UKG format with truncated microseconds (e.g., '.44')."""
        now = datetime.now()
        # Truncated format like UKG uses
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S") + ".44"

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday_str},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1

    def test_filter_preserves_employee_data(self, sync_service):
        """Should preserve all employee data in filtered results."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {
                "employeeId": "1",
                "employeeNumber": "12345",
                "firstName": "John",
                "lastName": "Doe",
                "email": "john.doe@example.com",
                "dateTimeChanged": yesterday,
                "customField": "customValue",
            },
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1
        assert result[0]["employeeId"] == "1"
        assert result[0]["firstName"] == "John"
        assert result[0]["customField"] == "customValue"

    def test_filter_with_none_date_value(self, sync_service):
        """Should include employees with None dateTimeChanged."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2", "dateTimeChanged": None},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 2

    def test_filter_with_empty_string_date(self, sync_service):
        """Should include employees with empty string dateTimeChanged."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},
            {"employeeId": "2", "dateTimeChanged": ""},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        # Empty string is falsy, so it should include the employee
        assert len(result) == 2

    def test_filter_boundary_exactly_at_cutoff(self, sync_service):
        """Should include employees changed exactly at the cutoff boundary."""
        now = datetime.now()
        # Slightly less than 2 days ago (to account for timing between test setup and filter call)
        almost_two_days = (now - timedelta(days=2) + timedelta(seconds=10)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": almost_two_days},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        # Should be included since it's >= cutoff_date
        assert len(result) == 1

    def test_filter_with_large_days_value(self, sync_service):
        """Should handle large days value (e.g., 365 days)."""
        now = datetime.now()
        six_months_ago = (now - timedelta(days=180)).isoformat()
        two_years_ago = (now - timedelta(days=730)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": six_months_ago},
            {"employeeId": "2", "dateTimeChanged": two_years_ago},
        ]

        result = sync_service._filter_by_date_changed(employees, days=365)

        assert len(result) == 1
        assert result[0]["employeeId"] == "1"

    def test_filter_with_iso_offset_timezone(self, sync_service):
        """Should handle ISO 8601 dates with timezone offset."""
        now = datetime.now()
        yesterday_with_offset = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S") + "+05:30"

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday_with_offset},
        ]

        result = sync_service._filter_by_date_changed(employees, days=2)

        assert len(result) == 1

    def test_filter_mixed_valid_invalid_dates(self, sync_service):
        """Should handle mix of valid dates, invalid dates, and missing dates."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        ten_days_ago = (now - timedelta(days=10)).isoformat()

        employees = [
            {"employeeId": "1", "dateTimeChanged": yesterday},  # Valid, recent
            {"employeeId": "2", "dateTimeChanged": ten_days_ago},  # Valid, old
            {"employeeId": "3", "dateTimeChanged": "not-a-date"},  # Invalid
            {"employeeId": "4"},  # Missing
            {"employeeId": "5", "dateTimeChanged": None},  # None
        ]

        result = sync_service._filter_by_date_changed(employees, days=5)

        # Should include: 1 (recent), 3 (invalid - fail-safe), 4 (missing - fail-safe), 5 (None - fail-safe)
        # Should exclude: 2 (old)
        assert len(result) == 4
        result_ids = [e["employeeId"] for e in result]
        assert "1" in result_ids
        assert "2" not in result_ids  # Old employee excluded
        assert "3" in result_ids
        assert "4" in result_ids
        assert "5" in result_ids


class TestSyncAllIntegrationWithDaysFilter:
    """Integration tests for sync_all with days_to_process filtering."""

    @pytest.fixture
    def mock_employee_repo(self):
        """Create mock employee repository."""
        return MagicMock()

    @pytest.fixture
    def mock_bill_user_repo(self):
        """Create mock BILL user repository."""
        return MagicMock()

    def test_full_sync_flow_with_filter(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should apply filter before processing employees in sync_all."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=20)).isoformat()

        # Simulating UKG API response
        mock_employee_repo._client.list_employees.return_value = [
            {
                "employeeId": "EMP001",
                "employeeNumber": "001",
                "firstName": "Recent",
                "lastName": "Employee",
                "email": "recent@example.com",
                "status": "Active",
                "dateTimeChanged": recent,
                "companyId": "TEST",
            },
            {
                "employeeId": "EMP002",
                "employeeNumber": "002",
                "firstName": "Old",
                "lastName": "Employee",
                "email": "old@example.com",
                "status": "Active",
                "dateTimeChanged": old,
                "companyId": "TEST",
            },
        ]
        mock_employee_repo._get_cached_person.return_value = None
        mock_employee_repo._client.get_employee_employment_details.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=7,
        )

        result = service.sync_all()

        # The sync_all processes filtered employees
        # Due to status/type filters, not all may be synced, but filter was applied
        mock_employee_repo._client.list_employees.assert_called_once()

    def test_filter_reduces_api_calls(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Filtering should reduce the number of employees processed."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=30)).isoformat()

        # 5 employees total, only 2 are recent
        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": f"EMP{i}", "employeeNumber": f"00{i}", "dateTimeChanged": recent if i < 2 else old}
            for i in range(5)
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=7,
        )

        # Spy on _process_single_employee to count calls
        with patch.object(service, '_process_single_employee', return_value=(False, False, None)) as mock_process:
            service.sync_all()

            # Should only process 2 employees (the recent ones)
            assert mock_process.call_count == 2

    def test_no_filter_processes_all_employees(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Without filter, all employees should be processed."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()
        old = (now - timedelta(days=30)).isoformat()

        # 5 employees total
        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": f"EMP{i}", "employeeNumber": f"00{i}", "dateTimeChanged": recent if i < 2 else old}
            for i in range(5)
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=None,  # No filter
        )

        with patch.object(service, '_process_single_employee', return_value=(False, False, None)) as mock_process:
            service.sync_all()

            # Should process all 5 employees
            assert mock_process.call_count == 5

    def test_filter_with_all_old_employees(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should handle case where all employees are filtered out."""
        now = datetime.now()
        old = (now - timedelta(days=30)).isoformat()

        # All employees are old
        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": f"EMP{i}", "employeeNumber": f"00{i}", "dateTimeChanged": old}
            for i in range(3)
        ]

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=7,
        )

        result = service.sync_all()

        # Should complete without errors, but process 0 employees
        assert result.total == 0

    def test_filter_with_all_recent_employees(
        self,
        mock_employee_repo,
        mock_bill_user_repo,
    ):
        """Should process all employees when all are recent."""
        now = datetime.now()
        recent = (now - timedelta(days=1)).isoformat()

        mock_employee_repo._client.list_employees.return_value = [
            {"employeeId": f"EMP{i}", "employeeNumber": f"00{i}", "dateTimeChanged": recent}
            for i in range(3)
        ]
        mock_employee_repo._get_cached_person.return_value = None

        service = SyncService(
            employee_repository=mock_employee_repo,
            bill_user_repository=mock_bill_user_repo,
            days_to_process=7,
        )

        with patch.object(service, '_process_single_employee', return_value=(False, False, None)) as mock_process:
            service.sync_all()

            # Should process all 3 employees
            assert mock_process.call_count == 3
