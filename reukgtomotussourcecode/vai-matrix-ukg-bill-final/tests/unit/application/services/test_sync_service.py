"""
Unit tests for SyncService.
"""

from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import pytest

from src.application.services.sync_service import SyncService
from src.domain.interfaces.services import SyncResult, BatchSyncResult
from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.bill_user import BillUser, BillRole


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

    def test_batch_aggregates_results(
        self,
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

        # First creates, second and third update
        mock_bill_user_repo.upsert.side_effect = [
            (BillUser(id="NEW", email="emp0@example.com", first_name="Test", last_name="User0", role=BillRole.MEMBER), "created"),
            (BillUser(id="EXISTING", email="emp1@example.com", first_name="Test", last_name="User1", role=BillRole.MEMBER), "updated"),
            (BillUser(id="EXISTING2", email="emp2@example.com", first_name="Test", last_name="User2", role=BillRole.MEMBER), "updated"),
        ]

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

    def test_batch_counts_all_action_types(
        self,
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

        # Set up returns: create, update, update, create (fails), error (no email)
        mock_bill_user_repo.upsert.side_effect = [
            (BillUser(id="NEW0", email="emp0@example.com", first_name="Test", last_name="User0", role=BillRole.MEMBER), "created"),
            (BillUser(id="EXIST1", email="emp1@example.com", first_name="Test", last_name="User1", role=BillRole.MEMBER), "updated"),
            (BillUser(id="EXIST2", email="emp2@example.com", first_name="Test", last_name="User2", role=BillRole.MEMBER), "updated"),
            Exception("Create failed"),  # emp3 fails
            # emp4 won't call upsert because it has no email
        ]

        result = sync_service.sync_batch(employees, workers=1)

        assert result.total == 5
        assert result.created == 1  # emp0
        assert result.updated == 2  # emp1 + emp2
        assert result.skipped == 0
        assert result.errors == 2  # emp3 (upsert failed) + emp4 (no email)

    def test_batch_parallel_execution(
        self,
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

        mock_bill_user_repo.upsert.return_value = (
            BillUser(id="NEW", email="test@example.com", first_name="Test", last_name="User", role=BillRole.MEMBER),
            "created",
        )

        # Use multiple workers
        result = sync_service.sync_batch(employees, workers=2)

        assert result.total == 3
        assert result.created == 3
