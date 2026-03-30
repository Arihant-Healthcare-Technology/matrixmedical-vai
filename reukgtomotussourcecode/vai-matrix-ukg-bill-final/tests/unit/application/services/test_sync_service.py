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
        mock_bill_user_repo.get_by_email.return_value = None
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW001",
            email=sample_employee.email,
            first_name=sample_employee.first_name,
            last_name=sample_employee.last_name,
            role=BillRole.MEMBER,
        )

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "create"
        assert result.entity_id == "NEW001"
        mock_bill_user_repo.create.assert_called_once()

    def test_updates_existing_user(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
        sample_bill_user,
    ):
        """Should update user when found in BILL with changes."""
        # Existing user has different name
        sample_bill_user.first_name = "Jonathan"
        mock_bill_user_repo.get_by_email.return_value = sample_bill_user
        mock_bill_user_repo.update.return_value = sample_bill_user

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "update"
        mock_bill_user_repo.update.assert_called_once()

    def test_skips_unchanged_user(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
        sample_bill_user,
    ):
        """Should skip when no changes detected."""
        mock_bill_user_repo.get_by_email.return_value = sample_bill_user

        result = sync_service.sync_employee(sample_employee)

        assert result.success is True
        assert result.action == "skip"
        mock_bill_user_repo.update.assert_not_called()

    def test_error_missing_email(self, sync_service, sample_employee):
        """Should return error for employee without email."""
        sample_employee.email = None

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "email" in result.message.lower()

    def test_error_on_create_failure(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should return error when create fails."""
        mock_bill_user_repo.get_by_email.return_value = None
        mock_bill_user_repo.create.side_effect = Exception("API Error")

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
        mock_bill_user_repo.get_by_email.return_value = None
        mock_bill_user_repo.create.return_value = sample_employee

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

        # First creates, second updates, third skips
        mock_bill_user_repo.get_by_email.side_effect = [
            None,  # First - will create
            BillUser(  # Second - will update (different name)
                id="EXISTING",
                email="emp1@example.com",
                first_name="Different",
                last_name="Name",
                role=BillRole.MEMBER,
            ),
            BillUser(  # Third - will skip (same data)
                id="EXISTING2",
                email="emp2@example.com",
                first_name="Test",
                last_name="User2",
                role=BillRole.MEMBER,
            ),
        ]
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW",
            email="emp0@example.com",
            first_name="Test",
            last_name="User0",
            role=BillRole.MEMBER,
        )
        mock_bill_user_repo.update.return_value = MagicMock()

        result = sync_service.sync_batch(employees, workers=1)

        assert result.total == 3
        assert result.created == 1
        assert result.updated == 1
        assert result.skipped == 1
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
        """Should fetch and sync active employees."""
        active_employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            email="active@example.com",
            first_name="Active",
            last_name="User",
            status=EmployeeStatus.ACTIVE,
        )
        mock_employee_repo.get_active_employees.return_value = [active_employee]
        mock_bill_user_repo.get_by_email.return_value = None
        mock_bill_user_repo.create.return_value = MagicMock()

        result = sync_service.sync_all()

        assert result.total == 1
        mock_employee_repo.get_active_employees.assert_called()


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

    def test_handles_get_by_email_exception(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
    ):
        """Should handle exception when looking up user."""
        mock_bill_user_repo.get_by_email.side_effect = Exception("Database error")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "Database error" in result.message

    def test_handles_update_exception(
        self,
        sync_service,
        mock_bill_user_repo,
        sample_employee,
        sample_bill_user,
    ):
        """Should handle exception when updating user."""
        # Existing user with different name to trigger update
        sample_bill_user.first_name = "Different"
        mock_bill_user_repo.get_by_email.return_value = sample_bill_user
        mock_bill_user_repo.update.side_effect = Exception("Update failed")

        result = sync_service.sync_employee(sample_employee)

        assert result.success is False
        assert result.action == "error"
        assert "Update failed" in result.message


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

        # Set up returns: create, update, skip, create (fails), error (no email)
        existing_user = BillUser(
            id="EXIST1",
            email="emp1@example.com",
            first_name="Different",  # Different to trigger update
            last_name="Name",
            role=BillRole.MEMBER,
        )
        unchanged_user = BillUser(
            id="EXIST2",
            email="emp2@example.com",
            first_name="Test",  # Same as employee
            last_name="User2",  # Same as employee
            role=BillRole.MEMBER,
        )

        mock_bill_user_repo.get_by_email.side_effect = [
            None,  # emp0 - create
            existing_user,  # emp1 - update
            unchanged_user,  # emp2 - skip
            None,  # emp3 - create (will fail)
        ]
        mock_bill_user_repo.create.side_effect = [
            BillUser(id="NEW0", email="emp0@example.com", first_name="Test", last_name="User0", role=BillRole.MEMBER),
            Exception("Create failed"),  # emp3 fails
        ]
        mock_bill_user_repo.update.return_value = existing_user

        result = sync_service.sync_batch(employees, workers=1)

        assert result.total == 5
        assert result.created == 1  # emp0
        assert result.updated == 1  # emp1
        assert result.skipped == 1  # emp2
        assert result.errors == 2  # emp3 (create failed) + emp4 (no email)

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

        mock_bill_user_repo.get_by_email.return_value = None
        mock_bill_user_repo.create.return_value = BillUser(
            id="NEW",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role=BillRole.MEMBER,
        )

        # Use multiple workers
        result = sync_service.sync_batch(employees, workers=2)

        assert result.total == 3
        assert result.created == 3
