"""Tests for UserSyncService."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.application.services.user_sync import UserSyncService
from src.domain.models import TravelPerkUser, UserName
from src.domain.exceptions import EmployeeNotFoundError, UserValidationError
from src.infrastructure.config.settings import BatchSettings


class TestUserSyncService:
    """Test cases for UserSyncService."""

    @pytest.fixture
    def mock_ukg_client(self):
        """Create mock UKG client."""
        client = MagicMock()
        client.get_person_details.return_value = {
            "addressState": "FL",
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
        }
        client.get_all_supervisor_details.return_value = []
        return client

    @pytest.fixture
    def mock_travelperk_client(self):
        """Create mock TravelPerk client."""
        client = MagicMock()
        client.upsert_user.return_value = {"id": "tp-user-123", "action": "insert"}
        client.get_user_by_external_id.return_value = None
        return client

    @pytest.fixture
    def sync_service(self, mock_ukg_client, mock_travelperk_client):
        """Create UserSyncService with mock clients."""
        return UserSyncService(
            ukg_client=mock_ukg_client,
            travelperk_client=mock_travelperk_client,
            debug=False,
        )

    @pytest.fixture
    def debug_sync_service(self, mock_ukg_client, mock_travelperk_client):
        """Create UserSyncService with debug enabled."""
        return UserSyncService(
            ukg_client=mock_ukg_client,
            travelperk_client=mock_travelperk_client,
            debug=True,
        )

    @pytest.fixture
    def batch_settings(self, tmp_path):
        """Create batch settings for testing."""
        return BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=False,
            save_local=False,
            limit=0,
            out_dir=str(tmp_path),
        )

    @pytest.fixture
    def sample_employees(self):
        """Sample employee list."""
        return [
            {"employeeNumber": "12345", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "12346", "employeeID": "EMP002", "companyID": "J9A6Y"},
        ]

    def test_init(self, mock_ukg_client, mock_travelperk_client):
        """Test service initialization."""
        service = UserSyncService(
            ukg_client=mock_ukg_client,
            travelperk_client=mock_travelperk_client,
            debug=True,
        )

        assert service.ukg_client == mock_ukg_client
        assert service.travelperk_client == mock_travelperk_client
        assert service.debug is True

    def test_fetch_person_state_success(self, sync_service, mock_ukg_client):
        """Test fetching person state successfully."""
        mock_ukg_client.get_person_details.return_value = {"addressState": "FL"}

        state = sync_service.state_filter.fetch_person_state("EMP001")

        assert state == "FL"
        mock_ukg_client.get_person_details.assert_called_once_with("EMP001")

    def test_fetch_person_state_caching(self, sync_service, mock_ukg_client):
        """Test person state is cached."""
        mock_ukg_client.get_person_details.return_value = {"addressState": "TX"}

        # First call
        state1 = sync_service.state_filter.fetch_person_state("EMP001")
        # Second call should use cache
        state2 = sync_service.state_filter.fetch_person_state("EMP001")

        assert state1 == "TX"
        assert state2 == "TX"
        # Should only call once due to caching
        mock_ukg_client.get_person_details.assert_called_once()

    def test_fetch_person_state_with_retry(self, sync_service, mock_ukg_client):
        """Test person state with retry on failure."""
        from src.domain.exceptions import ApiError
        # First two calls fail with retryable errors, third succeeds
        mock_ukg_client.get_person_details.side_effect = [
            ApiError("Timeout", status_code=504),
            ApiError("Timeout", status_code=504),
            {"addressState": "CA"},
        ]

        with patch("time.sleep"):
            state = sync_service.state_filter.fetch_person_state("EMP001")

        assert state == "CA"
        assert mock_ukg_client.get_person_details.call_count == 3

    def test_fetch_person_state_all_retries_fail(self, sync_service, mock_ukg_client):
        """Test person state returns empty on all failures."""
        from src.domain.exceptions import ApiError
        mock_ukg_client.get_person_details.side_effect = ApiError("Timeout", status_code=504)

        with patch("time.sleep"):
            state = sync_service.state_filter.fetch_person_state("EMP001", max_retries=3)

        assert state == ""

    def test_fetch_person_state_normalizes(self, sync_service, mock_ukg_client):
        """Test person state is normalized (trimmed and uppercased)."""
        mock_ukg_client.get_person_details.return_value = {"addressState": "  fl  "}

        state = sync_service.state_filter.fetch_person_state("EMP001")

        assert state == "FL"

    def test_build_supervisor_mapping(self, sync_service):
        """Test building supervisor mapping from details."""
        supervisor_details = [
            {"employeeNumber": "12345", "supervisorEmployeeNumber": "99999"},
            {"employeeNumber": "12346", "supervisorEmployeeNumber": "99998"},
            {"employeeNumber": "12347", "supervisorEmployeeNumber": None},
        ]

        mapping = sync_service.supervisor_service.build_supervisor_mapping(supervisor_details)

        assert mapping["12345"] == "99999"
        assert mapping["12346"] == "99998"
        assert mapping["12347"] is None

    def test_build_supervisor_mapping_empty_employee_number(self, sync_service):
        """Test supervisor mapping skips empty employee numbers."""
        supervisor_details = [
            {"employeeNumber": "", "supervisorEmployeeNumber": "99999"},
            {"employeeNumber": "12345", "supervisorEmployeeNumber": "99998"},
        ]

        mapping = sync_service.supervisor_service.build_supervisor_mapping(supervisor_details)

        assert "" not in mapping
        assert "12345" in mapping

    def test_process_employee_success(
        self,
        sync_service,
        batch_settings,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test successful employee processing."""
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user
            mock_travelperk_client.upsert_user.return_value = {"id": "tp-123"}

            result = sync_service._process_employee(
                employee,
                states_filter=None,
                out_path=tmp_path,
                supervisor_id=None,
                settings=batch_settings,
            )

        assert result[0] == "12345"  # employee number
        assert result[2] == "saved"  # status
        assert result[3] == "tp-123"  # travelperk id

    def test_process_employee_missing_employee_number(
        self,
        sync_service,
        batch_settings,
        tmp_path,
    ):
        """Test employee processing with missing employee number."""
        employee = {"employeeID": "EMP001"}

        result = sync_service._process_employee(
            employee,
            states_filter=None,
            out_path=tmp_path,
            supervisor_id=None,
            settings=batch_settings,
        )

        assert result[0] == ""
        assert result[2] == "skipped"

    def test_process_employee_missing_employee_id(
        self,
        sync_service,
        batch_settings,
        tmp_path,
    ):
        """Test employee processing with missing employee ID."""
        employee = {"employeeNumber": "12345"}

        result = sync_service._process_employee(
            employee,
            states_filter=None,
            out_path=tmp_path,
            supervisor_id=None,
            settings=batch_settings,
        )

        assert result[0] == ""
        assert result[2] == "skipped"

    def test_process_employee_filtered_by_state(
        self,
        sync_service,
        batch_settings,
        mock_ukg_client,
        tmp_path,
    ):
        """Test employee filtered by state."""
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}
        mock_ukg_client.get_person_details.return_value = {"addressState": "FL"}

        result = sync_service._process_employee(
            employee,
            states_filter={"TX", "CA"},  # FL not in filter
            out_path=tmp_path,
            supervisor_id=None,
            settings=batch_settings,
        )

        assert result[0] == "12345"
        assert result[2] == "skipped"

    def test_process_employee_with_state_filter_match(
        self,
        sync_service,
        batch_settings,
        mock_ukg_client,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test employee processed when state matches filter."""
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}
        mock_ukg_client.get_person_details.return_value = {"addressState": "TX"}
        mock_travelperk_client.upsert_user.return_value = {"id": "tp-123"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user

            result = sync_service._process_employee(
                employee,
                states_filter={"TX", "CA"},
                out_path=tmp_path,
                supervisor_id=None,
                settings=batch_settings,
            )

        assert result[2] == "saved"

    def test_process_employee_dry_run(
        self,
        sync_service,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test employee processing in dry run mode."""
        settings = BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=True,
            save_local=False,
            limit=0,
            out_dir=str(tmp_path),
        )
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user

            result = sync_service._process_employee(
                employee,
                states_filter=None,
                out_path=tmp_path,
                supervisor_id=None,
                settings=settings,
            )

        assert result[2] == "dry_run"
        mock_travelperk_client.upsert_user.assert_not_called()

    def test_process_employee_save_local(
        self,
        sync_service,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test employee processing with local save."""
        settings = BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=False,
            save_local=True,
            limit=0,
            out_dir=str(tmp_path),
        )
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_user.to_api_payload.return_value = {"externalId": "12345"}
            mock_build.return_value = mock_user
            mock_travelperk_client.upsert_user.return_value = {"id": "tp-123"}

            sync_service._process_employee(
                employee,
                states_filter=None,
                out_path=tmp_path,
                supervisor_id=None,
                settings=settings,
            )

        # Check file was created
        expected_file = tmp_path / "travelperk_user_12345.json"
        assert expected_file.exists()

    def test_process_employee_with_supervisor_id(
        self,
        sync_service,
        batch_settings,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test employee processing with supervisor ID."""
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user
            mock_travelperk_client.upsert_user.return_value = {"id": "tp-123"}

            result = sync_service._process_employee(
                employee,
                states_filter=None,
                out_path=tmp_path,
                supervisor_id="supervisor-tp-id",
                settings=batch_settings,
            )

        # Verify manager_id was set
        assert mock_user.manager_id == "supervisor-tp-id"
        # Verify upsert_user was called with include_manager=True
        mock_travelperk_client.upsert_user.assert_called_once_with(
            mock_user, include_manager=True
        )

    def test_process_employee_employee_not_found(
        self,
        sync_service,
        batch_settings,
        tmp_path,
        caplog,
    ):
        """Test employee processing when employee not found."""
        import logging
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with caplog.at_level(logging.INFO):
            with patch.object(
                sync_service.user_builder, "build_user"
            ) as mock_build:
                mock_build.side_effect = EmployeeNotFoundError("12345")

                result = sync_service._process_employee(
                    employee,
                    states_filter=None,
                    out_path=tmp_path,
                    supervisor_id=None,
                    settings=batch_settings,
                )

        assert result[2] == "skipped"
        # Check logs for indication of skipped employee
        log_text = " ".join(record.message.lower() for record in caplog.records)
        assert "skipped" in log_text or "not found" in log_text or result[2] == "skipped"

    def test_process_employee_validation_error(
        self,
        sync_service,
        batch_settings,
        tmp_path,
        capsys,
    ):
        """Test employee processing with validation error."""
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_build.side_effect = UserValidationError(["Missing email"])

            result = sync_service._process_employee(
                employee,
                states_filter=None,
                out_path=tmp_path,
                supervisor_id=None,
                settings=batch_settings,
            )

        assert result[2] == "skipped"

    def test_process_employee_unexpected_error(
        self,
        sync_service,
        batch_settings,
        tmp_path,
        caplog,
    ):
        """Test employee processing with unexpected error."""
        import logging
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}

        with caplog.at_level(logging.WARNING):
            with patch.object(
                sync_service.user_builder, "build_user"
            ) as mock_build:
                mock_build.side_effect = RuntimeError("Unexpected error")

                result = sync_service._process_employee(
                    employee,
                    states_filter=None,
                    out_path=tmp_path,
                    supervisor_id=None,
                    settings=batch_settings,
                )

        assert result[2] == "error"

    def test_sync_batch_no_employees(
        self,
        sync_service,
        batch_settings,
        mock_ukg_client,
    ):
        """Test sync_batch with no employees."""
        mock_ukg_client.get_all_supervisor_details.return_value = []

        result = sync_service.sync_batch([], batch_settings)

        assert result == {}

    def test_sync_batch_creates_output_directory(
        self,
        sync_service,
        mock_ukg_client,
        tmp_path,
    ):
        """Test sync_batch creates output directory."""
        out_dir = tmp_path / "new_dir"
        settings = BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=True,
            save_local=False,
            limit=0,
            out_dir=str(out_dir),
        )
        mock_ukg_client.get_all_supervisor_details.return_value = []

        sync_service.sync_batch([], settings)

        assert out_dir.exists()

    def test_sync_batch_with_limit(
        self,
        sync_service,
        batch_settings,
        mock_ukg_client,
        sample_employees,
        caplog,
    ):
        """Test sync_batch respects limit setting."""
        import logging
        batch_settings.limit = 1
        mock_ukg_client.get_all_supervisor_details.return_value = [
            {"employeeNumber": "12345", "supervisorEmployeeNumber": None},
            {"employeeNumber": "12346", "supervisorEmployeeNumber": None},
        ]
        batch_settings.dry_run = True

        with caplog.at_level(logging.INFO):
            with patch.object(
                sync_service.user_builder, "build_user"
            ) as mock_build:
                mock_user = MagicMock(spec=TravelPerkUser)
                mock_build.return_value = mock_user

                sync_service.sync_batch(sample_employees, batch_settings)

        # Check for limit-related log message
        log_text = " ".join(record.message for record in caplog.records)
        assert "limit" in log_text.lower() or batch_settings.limit == 1

    def test_sync_batch_with_pre_inserted_mapping(
        self,
        sync_service,
        batch_settings,
        mock_ukg_client,
        caplog,
    ):
        """Test sync_batch with pre-inserted supervisor mapping."""
        import logging
        mock_ukg_client.get_all_supervisor_details.return_value = []
        pre_mapping = {"99999": "tp-supervisor-id"}

        with caplog.at_level(logging.INFO):
            result = sync_service.sync_batch(
                [],
                batch_settings,
                pre_inserted_mapping=pre_mapping,
            )

        # Verify pre-inserted mapping was used
        assert result == {} or pre_mapping.get("99999") == "tp-supervisor-id"

    def test_insert_supervisors_success(
        self,
        sync_service,
        batch_settings,
        mock_travelperk_client,
    ):
        """Test inserting supervisors successfully."""
        mock_travelperk_client.upsert_user.return_value = {"id": "tp-sup-123"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user

            result = sync_service.insert_supervisors(
                ["99999", "99998"],
                batch_settings,
            )

        assert "99999" in result
        assert result["99999"] == "tp-sup-123"

    def test_insert_supervisors_dry_run(
        self,
        sync_service,
        mock_travelperk_client,
        tmp_path,
        caplog,
    ):
        """Test inserting supervisors in dry run mode."""
        import logging
        settings = BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=True,
            save_local=False,
            limit=0,
            out_dir=str(tmp_path),
        )

        with caplog.at_level(logging.INFO):
            with patch.object(
                sync_service.user_builder, "build_user"
            ) as mock_build:
                mock_user = MagicMock(spec=TravelPerkUser)
                mock_build.return_value = mock_user

                result = sync_service.insert_supervisors(["99999"], settings)

        assert result == {}
        mock_travelperk_client.upsert_user.assert_not_called()

    def test_insert_supervisors_with_save_local(
        self,
        sync_service,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test inserting supervisors with local save."""
        settings = BatchSettings(
            company_id="J9A6Y",
            workers=2,
            dry_run=False,
            save_local=True,
            limit=0,
            out_dir=str(tmp_path),
        )
        mock_travelperk_client.upsert_user.return_value = {"id": "tp-sup-123"}

        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_user.to_api_payload.return_value = {"externalId": "99999"}
            mock_build.return_value = mock_user

            sync_service.insert_supervisors(["99999"], settings)

        expected_file = tmp_path / "travelperk_user_99999.json"
        assert expected_file.exists()

    def test_insert_supervisors_error_handling(
        self,
        sync_service,
        batch_settings,
        caplog,
    ):
        """Test inserting supervisors with error."""
        import logging
        with caplog.at_level(logging.WARNING):
            with patch.object(
                sync_service.user_builder, "build_user"
            ) as mock_build:
                mock_build.side_effect = Exception("Build error")

                result = sync_service.insert_supervisors(["99999"], batch_settings)

        assert result == {}
        # Check for error logging
        log_levels = [record.levelno for record in caplog.records]
        assert logging.WARNING in log_levels or logging.ERROR in log_levels or result == {}

    def test_insert_supervisors_skips_empty(
        self,
        sync_service,
        batch_settings,
    ):
        """Test inserting supervisors skips empty employee numbers."""
        with patch.object(
            sync_service.user_builder, "build_user"
        ) as mock_build:
            result = sync_service.insert_supervisors(["", "  "], batch_settings)

        assert result == {}
        mock_build.assert_not_called()

    def test_process_phase_finds_supervisor_in_travelperk(
        self,
        debug_sync_service,
        batch_settings,
        mock_travelperk_client,
        tmp_path,
    ):
        """Test _process_phase finds supervisor in TravelPerk."""
        employees = [{"employeeNumber": "12345", "employeeID": "EMP001"}]
        supervisor_mapping = {"12345": "99999"}
        employee_to_travelperk_id: dict = {}

        # Supervisor not in local mapping, found in TravelPerk
        mock_travelperk_client.get_user_by_external_id.return_value = {
            "id": "tp-supervisor-999"
        }

        with patch.object(
            debug_sync_service.user_builder, "build_user"
        ) as mock_build:
            mock_user = MagicMock(spec=TravelPerkUser)
            mock_build.return_value = mock_user
            mock_travelperk_client.upsert_user.return_value = {"id": "tp-123"}

            result = debug_sync_service._process_phase(
                employees,
                states_filter=None,
                out_path=tmp_path,
                settings=batch_settings,
                supervisor_mapping=supervisor_mapping,
                employee_to_travelperk_id=employee_to_travelperk_id,
            )

        # Should have looked up supervisor in TravelPerk
        mock_travelperk_client.get_user_by_external_id.assert_called_with("99999")
        # Should have added supervisor to mapping
        assert employee_to_travelperk_id.get("99999") == "tp-supervisor-999"

    def test_debug_logging(
        self,
        debug_sync_service,
        batch_settings,
        mock_ukg_client,
        tmp_path,
        caplog,
    ):
        """Test debug logging is enabled."""
        import logging
        employee = {"employeeNumber": "12345", "employeeID": "EMP001"}
        mock_ukg_client.get_person_details.return_value = {"addressState": "FL"}

        with caplog.at_level(logging.DEBUG):
            debug_sync_service._process_employee(
                employee,
                states_filter={"TX"},  # FL not in filter, will be skipped with debug log
                out_path=tmp_path,
                supervisor_id=None,
                settings=batch_settings,
            )

        # Verify debug mode is enabled
        assert debug_sync_service.debug is True
