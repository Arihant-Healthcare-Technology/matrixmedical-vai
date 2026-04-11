"""
Unit tests for batch commands for S&E operations.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestRunSyncAll:
    """Tests for run_sync_all function."""

    def test_returns_one_on_errors(self):
        """Test returns 1 when there are errors."""
        from src.presentation.cli.batch_commands import run_sync_all

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 5
            total = 5
            created = 0
            updated = 0
            skipped = 0
            success_rate = 0.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_all.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        result = run_sync_all(mock_container)

        assert result == 1

    def test_returns_one_on_exception(self):
        """Test returns 1 on exception."""
        from src.presentation.cli.batch_commands import run_sync_all

        mock_container = MagicMock()
        mock_container.sync_service.side_effect = Exception("Sync failed")

        result = run_sync_all(mock_container)

        assert result == 1

    def test_returns_zero_on_dry_run(self):
        """Test returns 0 on dry run mode."""
        from src.presentation.cli.batch_commands import run_sync_all

        mock_container = MagicMock()
        mock_employee_repo = MagicMock()

        mock_employee = MagicMock()
        mock_employee.email = "test@example.com"
        mock_employee.full_name = "Test User"
        mock_employee_repo.get_active_employees.return_value = iter([mock_employee])

        mock_container.employee_repository.return_value = mock_employee_repo

        result = run_sync_all(mock_container, dry_run=True)

        assert result == 0

    def test_returns_zero_on_success(self):
        """Test returns 0 on successful sync."""
        from src.presentation.cli.batch_commands import run_sync_all

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 0
            total = 5
            created = 3
            updated = 2
            skipped = 0
            success_rate = 100.0
            duration = 2.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_all.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        result = run_sync_all(mock_container)

        assert result == 0

    def test_passes_company_id_filter(self):
        """Test passes company_id filter to sync."""
        from src.presentation.cli.batch_commands import run_sync_all

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 0
            total = 1
            created = 1
            updated = 0
            skipped = 0
            success_rate = 100.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_all.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        result = run_sync_all(mock_container, company_id="J9A6Y")

        mock_sync_service.sync_all.assert_called_once()
        call_kwargs = mock_sync_service.sync_all.call_args.kwargs
        assert call_kwargs.get("company_id") == "J9A6Y"


class TestRunSyncBatch:
    """Tests for run_sync_batch function."""

    def test_returns_one_on_file_error(self):
        """Test returns 1 on file error."""
        from src.presentation.cli.batch_commands import run_sync_batch

        mock_container = MagicMock()

        result = run_sync_batch(mock_container, "/nonexistent/file.json")

        assert result == 1

    def test_returns_one_on_invalid_json(self, tmp_path):
        """Test returns 1 on invalid JSON."""
        from src.presentation.cli.batch_commands import run_sync_batch

        employee_file = tmp_path / "employees.json"
        employee_file.write_text("not valid json{")

        mock_container = MagicMock()

        result = run_sync_batch(mock_container, str(employee_file))

        assert result == 1

    def test_returns_zero_on_dry_run(self, tmp_path):
        """Test returns 0 on dry run mode."""
        from src.presentation.cli.batch_commands import run_sync_batch

        employee_file = tmp_path / "employees.json"
        employee_file.write_text(json.dumps([
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"}
        ]))

        mock_container = MagicMock()

        result = run_sync_batch(mock_container, str(employee_file), dry_run=True)

        assert result == 0

    def test_returns_zero_on_success(self, tmp_path):
        """Test returns 0 on successful sync."""
        from src.presentation.cli.batch_commands import run_sync_batch

        employee_file = tmp_path / "employees.json"
        employee_file.write_text(json.dumps([
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"}
        ]))

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 0
            total = 1
            created = 1
            updated = 0
            skipped = 0
            success_rate = 100.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_batch.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        result = run_sync_batch(mock_container, str(employee_file))

        assert result == 0

    def test_returns_one_on_sync_errors(self, tmp_path):
        """Test returns 1 when sync has errors."""
        from src.presentation.cli.batch_commands import run_sync_batch

        employee_file = tmp_path / "employees.json"
        employee_file.write_text(json.dumps([
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"}
        ]))

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 1
            total = 1
            created = 0
            updated = 0
            skipped = 0
            success_rate = 0.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_batch.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        result = run_sync_batch(mock_container, str(employee_file))

        assert result == 1

    def test_returns_one_on_exception(self, tmp_path):
        """Test returns 1 on exception."""
        from src.presentation.cli.batch_commands import run_sync_batch

        employee_file = tmp_path / "employees.json"
        employee_file.write_text(json.dumps([
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"}
        ]))

        mock_container = MagicMock()
        mock_container.sync_service.side_effect = Exception("Service failed")

        result = run_sync_batch(mock_container, str(employee_file))

        assert result == 1


class TestRunExportCsv:
    """Tests for run_export_csv function."""

    def test_returns_zero_on_empty_employees(self):
        """Test returns 0 when no employees found."""
        from src.presentation.cli.batch_commands import run_export_csv

        mock_container = MagicMock()
        mock_employee_repo = MagicMock()
        mock_employee_repo.get_active_employees.return_value = iter([])
        mock_container.employee_repository.return_value = mock_employee_repo

        result = run_export_csv(mock_container, "/tmp/output.csv")

        assert result == 0

    def test_returns_zero_on_success(self, tmp_path):
        """Test returns 0 on successful export."""
        from src.presentation.cli.batch_commands import run_export_csv

        output_path = tmp_path / "output.csv"

        mock_container = MagicMock()
        mock_employee_repo = MagicMock()

        mock_employee = MagicMock()
        mock_employee.email = "test@example.com"
        mock_employee.first_name = "Test"
        mock_employee.last_name = "User"
        mock_employee.supervisor_email = None
        mock_employee.phone = "555-1234"
        mock_employee.employee_number = "12345"

        mock_employee_repo.get_active_employees.return_value = iter([mock_employee])
        mock_container.employee_repository.return_value = mock_employee_repo

        # Mock the mapper and BillUser to return proper CSV row
        mock_bill_user = MagicMock()
        mock_bill_user.to_csv_row.return_value = {
            "first name": "Test",
            "last name": "User",
            "email address": "test@example.com",
            "role": "Member",
        }

        with patch("src.infrastructure.adapters.bill.mappers.map_employee_to_bill_user", return_value=mock_bill_user):
            result = run_export_csv(mock_container, str(output_path))

        assert result == 0
        assert output_path.exists()

    def test_returns_one_on_exception(self, tmp_path):
        """Test returns 1 on exception."""
        from src.presentation.cli.batch_commands import run_export_csv

        mock_container = MagicMock()
        mock_container.employee_repository.side_effect = Exception("Repo failed")

        result = run_export_csv(mock_container, str(tmp_path / "output.csv"))

        assert result == 1

    def test_includes_manager_column(self, tmp_path):
        """Test includes manager column when requested."""
        from src.presentation.cli.batch_commands import run_export_csv
        import csv

        output_path = tmp_path / "output.csv"

        mock_container = MagicMock()
        mock_employee_repo = MagicMock()

        mock_employee = MagicMock()
        mock_employee.email = "test@example.com"
        mock_employee.first_name = "Test"
        mock_employee.last_name = "User"
        mock_employee.supervisor_email = "manager@example.com"
        mock_employee.phone = "555-1234"
        mock_employee.employee_number = "12345"

        mock_employee_repo.get_active_employees.return_value = iter([mock_employee])
        mock_container.employee_repository.return_value = mock_employee_repo

        # Mock the mapper and BillUser to return proper CSV row with manager
        mock_bill_user = MagicMock()
        mock_bill_user.to_csv_row.return_value = {
            "first name": "Test",
            "last name": "User",
            "email address": "test@example.com",
            "role": "Member",
            "manager": "manager@example.com",
        }

        with patch("src.infrastructure.adapters.bill.mappers.map_employee_to_bill_user", return_value=mock_bill_user):
            result = run_export_csv(
                mock_container,
                str(output_path),
                include_managers=True,
            )

        assert result == 0

        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            assert "manager" in reader.fieldnames


class TestPrivateFunctions:
    """Tests for private helper functions."""

    def test_load_employees_from_file(self, tmp_path):
        """Test _load_employees_from_file function."""
        from src.presentation.cli.batch_commands import _load_employees_from_file

        test_file = tmp_path / "employees.json"
        test_file.write_text(json.dumps([
            {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"},
            {"employeeNumber": "67890", "firstName": "Jane", "lastName": "Smith"},
        ]))

        result = _load_employees_from_file(str(test_file))

        assert len(result) == 2

    def test_load_employees_from_dict_format(self, tmp_path):
        """Test loads employees from dict format."""
        from src.presentation.cli.batch_commands import _load_employees_from_file

        test_file = tmp_path / "employees.json"
        test_file.write_text(json.dumps({
            "employees": [
                {"employeeNumber": "12345", "firstName": "John", "lastName": "Doe"}
            ]
        }))

        result = _load_employees_from_file(str(test_file))

        assert len(result) == 1


class TestPrintFunctions:
    """Tests for print helper functions (now in utils.py)."""

    def test_print_preview_with_email(self, capsys):
        """Test print_preview with email attribute."""
        from src.presentation.cli.utils import print_preview

        class MockEmployee:
            email = "test@example.com"
            full_name = "Test User"

        print_preview([MockEmployee()], "test employees")

        captured = capsys.readouterr()
        assert "test@example.com" in captured.out
        assert "Test User" in captured.out

    def test_print_preview_with_name(self, capsys):
        """Test print_preview with name attribute."""
        from src.presentation.cli.utils import print_preview

        class MockItem:
            name = "Test Item"

        print_preview([MockItem()], "test items")

        captured = capsys.readouterr()
        assert "Test Item" in captured.out

    def test_print_preview_with_other(self, capsys):
        """Test print_preview with unknown object."""
        from src.presentation.cli.utils import print_preview

        print_preview(["item1", "item2"], "test items")

        captured = capsys.readouterr()
        assert "item1" in captured.out
        assert "item2" in captured.out

    def test_print_sync_result(self, capsys):
        """Test print_sync_result."""
        from src.presentation.cli.utils import print_sync_result

        class MockResult:
            total = 10
            created = 5
            updated = 3
            skipped = 2
            errors = 0
            success_rate = 100.0
            duration = 5.5
            correlation_id = "test-correlation"
            results = []

        print_sync_result(MockResult())

        captured = capsys.readouterr()
        assert "SYNC RESULT" in captured.out
        assert "10" in captured.out
        assert "100.0%" in captured.out

    def test_print_sync_result_with_errors(self, capsys):
        """Test print_sync_result with errors."""
        from src.presentation.cli.utils import print_sync_result

        class MockError:
            action = "error"
            entity_id = "emp-123"
            message = "Failed to sync"

        class MockResult:
            total = 10
            created = 5
            updated = 3
            skipped = 1
            errors = 1
            success_rate = 90.0
            duration = 5.5
            correlation_id = "test-correlation"
            results = [MockError()]

        print_sync_result(MockResult())

        captured = capsys.readouterr()
        assert "Errors:" in captured.out
        assert "emp-123" in captured.out
        assert "Failed to sync" in captured.out


class TestRoleMapping:
    """Tests for role mapping in sync commands."""

    def test_default_role_is_member(self):
        """Test default role is MEMBER."""
        from src.presentation.cli.batch_commands import run_sync_all
        from src.domain.models.bill_user import BillRole

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 0
            total = 1
            created = 1
            updated = 0
            skipped = 0
            success_rate = 100.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_all.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        run_sync_all(mock_container, default_role="MEMBER")

        call_kwargs = mock_sync_service.sync_all.call_args.kwargs
        assert call_kwargs.get("default_role") == BillRole.MEMBER

    def test_accepts_custom_role(self):
        """Test accepts custom role."""
        from src.presentation.cli.batch_commands import run_sync_all
        from src.domain.models.bill_user import BillRole

        mock_container = MagicMock()
        mock_sync_service = MagicMock()

        class MockResult:
            errors = 0
            total = 1
            created = 1
            updated = 0
            skipped = 0
            success_rate = 100.0
            duration = 1.0
            correlation_id = "test-123"
            results = []

        mock_sync_service.sync_all.return_value = MockResult()
        mock_container.sync_service.return_value = mock_sync_service

        run_sync_all(mock_container, default_role="ADMIN")

        call_kwargs = mock_sync_service.sync_all.call_args.kwargs
        assert call_kwargs.get("default_role") == BillRole.ADMIN
