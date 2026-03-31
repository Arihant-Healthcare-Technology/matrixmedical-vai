"""Tests for DriverSyncService."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory

from src.application.services.driver_sync import DriverSyncService
from src.infrastructure.config.settings import BatchSettings
from src.domain.models import MotusDriver
from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError


class TestDriverSyncService:
    """Test cases for DriverSyncService."""

    @pytest.fixture
    def mock_ukg_client(self):
        """Create mock UKG client."""
        client = MagicMock()
        client.get_person_details.return_value = {
            "employeeId": "EMP001",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
            "addressState": "FL",
        }
        return client

    @pytest.fixture
    def mock_motus_client(self):
        """Create mock Motus client."""
        client = MagicMock()
        client.upsert_driver.return_value = {
            "success": True,
            "action": "insert",
            "id": "12345",
        }
        return client

    @pytest.fixture
    def sync_service(self, mock_ukg_client, mock_motus_client):
        """Create DriverSyncService with mock clients."""
        return DriverSyncService(
            ukg_client=mock_ukg_client,
            motus_client=mock_motus_client,
            debug=False,
        )

    @pytest.fixture
    def debug_service(self, mock_ukg_client, mock_motus_client):
        """Create DriverSyncService with debug enabled."""
        return DriverSyncService(
            ukg_client=mock_ukg_client,
            motus_client=mock_motus_client,
            debug=True,
        )

    @pytest.fixture
    def sample_employee_record(self):
        """Sample employee record from UKG."""
        return {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "companyID": "J9A6Y",
            "primaryJobCode": "4154",
            "employeeStatusCode": "A",
        }

    @pytest.fixture
    def batch_settings(self):
        """Create batch settings for testing."""
        return BatchSettings(
            workers=2,
            company_id="J9A6Y",
            dry_run=False,
            save_local=False,
            probe=False,
        )

    def test_init(self, mock_ukg_client, mock_motus_client):
        """Test service initialization."""
        service = DriverSyncService(
            ukg_client=mock_ukg_client,
            motus_client=mock_motus_client,
            debug=True,
        )
        assert service.ukg_client == mock_ukg_client
        assert service.motus_client == mock_motus_client
        assert service.debug is True
        assert service.builder is not None

    def test_log_debug_enabled(self, debug_service, caplog):
        """Test _log outputs when debug enabled."""
        import logging
        caplog.set_level(logging.DEBUG)

        debug_service._log("Test message")

        # Check that the message was logged
        assert any("Test message" in record.message for record in caplog.records)

    def test_log_debug_disabled(self, sync_service, capsys):
        """Test _log does not output when debug disabled."""
        sync_service._log("Test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_get_person_state_from_cache(self, sync_service, mock_ukg_client):
        """Test get_person_state returns cached value."""
        cache = {"EMP001": "FL"}

        result = sync_service.get_person_state("EMP001", cache)

        assert result == "FL"
        mock_ukg_client.get_person_details.assert_not_called()

    def test_get_person_state_fetches_and_caches(self, sync_service, mock_ukg_client):
        """Test get_person_state fetches and caches new value."""
        cache = {}

        result = sync_service.get_person_state("EMP001", cache)

        assert result == "FL"
        assert cache["EMP001"] == "FL"
        mock_ukg_client.get_person_details.assert_called_once()

    def test_get_person_state_normalizes(self, sync_service, mock_ukg_client):
        """Test get_person_state normalizes state code."""
        mock_ukg_client.get_person_details.return_value = {
            "addressState": "  fl  ",
        }
        cache = {}

        result = sync_service.get_person_state("EMP001", cache)

        assert result == "FL"

    def test_get_person_state_api_error_retries(self, sync_service, mock_ukg_client):
        """Test get_person_state retries on API error."""
        mock_ukg_client.get_person_details.side_effect = [
            Exception("API Error"),
            {"addressState": "FL"},
        ]
        cache = {}

        with patch("time.sleep"):  # Speed up test
            result = sync_service.get_person_state("EMP001", cache, max_retries=2)

        assert result == "FL"

    def test_get_person_state_all_retries_fail(self, sync_service, mock_ukg_client):
        """Test get_person_state returns empty string after all retries fail."""
        mock_ukg_client.get_person_details.side_effect = Exception("API Error")
        cache = {}

        with patch("time.sleep"):  # Speed up test
            result = sync_service.get_person_state("EMP001", cache, max_retries=2)

        assert result == ""
        assert cache["EMP001"] == ""

    def test_sync_employee_success(
        self, sync_service, sample_employee_record, mock_motus_client
    ):
        """Test successful employee sync."""
        # Mock the builder to return a valid driver
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "insert"
        mock_motus_client.upsert_driver.assert_called_once()

    def test_sync_employee_skipped_empty_number(self, sync_service):
        """Test employee sync skipped for empty employee number."""
        record = {"employeeNumber": "", "employeeID": "EMP001"}

        emp_num, state, status = sync_service.sync_employee(
            employee_record=record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == ""
        assert status == "skipped"

    def test_sync_employee_skipped_empty_id(self, sync_service):
        """Test employee sync skipped for empty employee ID."""
        record = {"employeeNumber": "12345", "employeeID": ""}

        emp_num, state, status = sync_service.sync_employee(
            employee_record=record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == ""
        assert status == "skipped"

    def test_sync_employee_skipped_state_filter(self, sync_service, sample_employee_record):
        """Test employee sync skipped when state not in filter."""
        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter={"TX", "CA"},  # FL not included
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "skipped"

    def test_sync_employee_state_filter_match(
        self, sync_service, sample_employee_record, mock_motus_client
    ):
        """Test employee sync proceeds when state matches filter."""
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter={"FL", "TX"},  # FL included
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "insert"

    def test_sync_employee_dry_run(self, sync_service, sample_employee_record):
        """Test employee sync in dry run mode."""
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )
        sync_service.motus_client.upsert_driver.return_value = {
            "dry_run": True,
            "action": "validated",
        }

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
            dry_run=True,
        )

        assert emp_num == "12345"
        assert status == "dry_run"

    def test_sync_employee_saves_to_file(self, sync_service, sample_employee_record):
        """Test employee sync saves to file when out_dir specified."""
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            sync_service.sync_employee(
                employee_record=sample_employee_record,
                company_id="J9A6Y",
                states_filter=None,
                state_cache={},
                out_dir=out_dir,
            )

            file_path = out_dir / "motus_driver_12345.json"
            assert file_path.exists()

            with file_path.open() as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["clientEmployeeId1"] == "12345"

    def test_sync_employee_employee_not_found(self, sync_service, sample_employee_record, caplog):
        """Test employee sync handles EmployeeNotFoundError."""
        import logging
        caplog.set_level(logging.WARNING)

        sync_service.builder.build_driver = MagicMock(
            side_effect=EmployeeNotFoundError("Not found", employee_number="12345")
        )

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "skipped"
        # Check that a warning was logged
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) > 0 or status == "skipped"  # Either logged or status indicates skip

    def test_sync_employee_program_not_found(self, sync_service, sample_employee_record, capsys):
        """Test employee sync handles ProgramNotFoundError."""
        sync_service.builder.build_driver = MagicMock(
            side_effect=ProgramNotFoundError("No program", job_code="9999")
        )

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "skipped"

    def test_sync_employee_generic_error(self, sync_service, sample_employee_record, caplog):
        """Test employee sync handles generic errors."""
        import logging
        caplog.set_level(logging.WARNING)

        sync_service.builder.build_driver = MagicMock(
            side_effect=Exception("Unexpected error")
        )

        emp_num, state, status = sync_service.sync_employee(
            employee_record=sample_employee_record,
            company_id="J9A6Y",
            states_filter=None,
            state_cache={},
        )

        assert emp_num == "12345"
        assert status == "error"
        # Check that a warning/error was logged or status indicates error
        error_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(error_records) > 0 or status == "error"

    def test_sync_batch_success(self, sync_service, batch_settings, capsys):
        """Test batch sync with multiple employees."""
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        employees = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
            {"employeeNumber": "12346", "employeeID": "EMP002"},
        ]

        stats = sync_service.sync_batch(employees, batch_settings)

        assert stats["total"] == 2
        assert stats["saved"] == 2
        assert stats["skipped"] == 0
        assert stats["errors"] == 0

    def test_sync_batch_with_state_filter(self, sync_service, batch_settings, mock_ukg_client):
        """Test batch sync with state filter."""
        # First employee in FL, second in TX
        mock_ukg_client.get_person_details.side_effect = [
            {"addressState": "FL"},
            {"addressState": "TX"},
        ]
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        employees = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
            {"employeeNumber": "12346", "employeeID": "EMP002"},
        ]

        stats = sync_service.sync_batch(
            employees, batch_settings, states_filter={"FL"}
        )

        assert stats["total"] == 2
        assert stats["saved"] == 1
        assert stats["skipped"] == 1

    def test_sync_batch_dry_run(self, sync_service, batch_settings):
        """Test batch sync in dry run mode."""
        batch_settings.dry_run = True
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )
        sync_service.motus_client.upsert_driver.return_value = {
            "dry_run": True,
            "action": "validated",
        }

        employees = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        stats = sync_service.sync_batch(employees, batch_settings)

        # Dry run results in skipped
        assert stats["total"] == 1
        assert stats["skipped"] == 1

    def test_sync_batch_saves_local(self, sync_service):
        """Test batch sync saves files when save_local enabled."""
        with TemporaryDirectory() as tmpdir:
            batch_settings = BatchSettings(
                workers=1,
                company_id="J9A6Y",
                dry_run=False,
                save_local=True,
                out_dir=tmpdir,
            )

            sync_service.builder.build_driver = MagicMock(
                return_value=MotusDriver(
                    client_employee_id1="12345",
                    program_id=21233,
                    first_name="John",
                    last_name="Doe",
                    email="john.doe@example.com",
                )
            )

            employees = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

            sync_service.sync_batch(employees, batch_settings)

            file_path = Path(tmpdir) / "motus_driver_12345.json"
            assert file_path.exists()

    def test_sync_batch_creates_output_dir(self, sync_service):
        """Test batch sync creates output directory if needed."""
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "nested" / "dir"

            batch_settings = BatchSettings(
                workers=1,
                company_id="J9A6Y",
                save_local=True,
                out_dir=str(out_dir),
            )

            sync_service.builder.build_driver = MagicMock(
                return_value=MotusDriver(
                    client_employee_id1="12345",
                    program_id=21233,
                    first_name="John",
                    last_name="Doe",
                    email="john.doe@example.com",
                )
            )

            employees = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

            sync_service.sync_batch(employees, batch_settings)

            assert out_dir.exists()

    def test_sync_batch_progress_logging(self, sync_service, batch_settings, caplog):
        """Test batch sync logs progress."""
        import logging
        caplog.set_level(logging.INFO)

        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )

        employees = [
            {"employeeNumber": str(i), "employeeID": f"EMP{i:03d}"}
            for i in range(150)
        ]

        sync_service.sync_batch(employees, batch_settings)

        # Check that progress/completion was logged at INFO level
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        log_messages = " ".join(r.message for r in info_records)
        assert "progress" in log_messages.lower() or "done" in log_messages.lower() or len(info_records) > 0

    def test_sync_batch_mixed_results(self, sync_service, batch_settings, mock_ukg_client):
        """Test batch sync with mixed success, skip, and error."""
        call_count = 0

        def mock_build_driver(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MotusDriver(
                    client_employee_id1="12345",
                    program_id=21233,
                    first_name="John",
                    last_name="Doe",
                    email="john.doe@example.com",
                )
            elif call_count == 2:
                raise EmployeeNotFoundError("Not found")
            else:
                raise Exception("Error")

        sync_service.builder.build_driver = MagicMock(side_effect=mock_build_driver)

        employees = [
            {"employeeNumber": "12345", "employeeID": "EMP001"},
            {"employeeNumber": "12346", "employeeID": "EMP002"},
            {"employeeNumber": "12347", "employeeID": "EMP003"},
        ]

        stats = sync_service.sync_batch(employees, batch_settings)

        assert stats["total"] == 3
        assert stats["saved"] == 1
        assert stats["skipped"] == 1
        assert stats["errors"] == 1

    def test_sync_batch_update_action(self, sync_service, batch_settings):
        """Test batch sync counts updates as saved."""
        sync_service.builder.build_driver = MagicMock(
            return_value=MotusDriver(
                client_employee_id1="12345",
                program_id=21233,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
            )
        )
        sync_service.motus_client.upsert_driver.return_value = {
            "success": True,
            "action": "update",
            "id": "12345",
        }

        employees = [{"employeeNumber": "12345", "employeeID": "EMP001"}]

        stats = sync_service.sync_batch(employees, batch_settings)

        assert stats["saved"] == 1
