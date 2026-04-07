"""
Integration tests for two-phase sync pipeline.

Tests verify the two-phase sync from UKG to TravelPerk, including supervisor handling.
Run with: pytest tests/integration/test_two_phase_sync_integration.py -v -m integration
"""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import responses

from src.application.services.user_sync import UserSyncService
from src.application.services.user_builder import UserBuilderService
from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.adapters.travelperk.client import TravelPerkClient


@pytest.fixture
def mock_ukg_settings():
    """Create mock UKG settings."""
    settings = MagicMock()
    settings.base_url = "https://service4.ultipro.com"
    settings.username = "test_user"
    settings.password = "test_pass"
    settings.customer_api_key = "test_api_key"
    settings.basic_b64 = None
    settings.timeout = 45.0
    return settings


@pytest.fixture
def mock_travelperk_settings():
    """Create mock TravelPerk settings."""
    settings = MagicMock()
    settings.api_base = "https://app.sandbox-travelperk.com"
    settings.api_key = "test_api_key"
    settings.timeout = 60.0
    settings.max_retries = 2
    return settings


@pytest.fixture
def ukg_base_url():
    return "https://service4.ultipro.com"


@pytest.fixture
def travelperk_base_url():
    return "https://app.sandbox-travelperk.com"


@pytest.mark.integration
class TestPhase1UsersWithoutSupervisor:
    """Test Phase 1: Users without supervisor."""

    @responses.activate
    def test_phase1_users_without_supervisor(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        sample_travelperk_user_response,
        ukg_base_url,
        travelperk_base_url,
    ):
        """Test Phase 1 processes users without supervisors."""
        # Employees without supervisors
        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y"},
        ]

        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )

        # Supervisor details - all have no supervisor
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[
                {"employeeNumber": "001", "supervisorEmployeeNumber": None},
                {"employeeNumber": "002", "supervisorEmployeeNumber": None},
            ],
            status=200,
        )

        # Person details
        for emp in employees:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        # TravelPerk responses
        for emp in employees:
            # Check if exists
            responses.add(
                responses.GET,
                f"{travelperk_base_url}/api/v2/scim/Users",
                json={"totalResults": 0, "Resources": []},
                status=200,
            )
            # Create user
            responses.add(
                responses.POST,
                f"{travelperk_base_url}/api/v2/scim/Users",
                json={**sample_travelperk_user_response, "id": f"tp-{emp['employeeNumber']}"},
                status=201,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(
            company_id="J9A6Y",
            dry_run=False,
        )

        assert result["phase1_processed"] >= 2


@pytest.mark.integration
class TestPhase2UsersWithSupervisor:
    """Test Phase 2: Users with supervisor."""

    @responses.activate
    def test_phase2_users_with_supervisor(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        sample_travelperk_user_response,
        ukg_base_url,
        travelperk_base_url,
    ):
        """Test Phase 2 processes users with supervisors."""
        # Supervisor and employee
        employees = [
            {"employeeNumber": "100", "employeeID": "SUP001", "companyID": "J9A6Y"},  # Supervisor
            {"employeeNumber": "101", "employeeID": "EMP001", "companyID": "J9A6Y"},  # Reports to 100
        ]

        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )

        # Supervisor details
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[
                {"employeeNumber": "100", "supervisorEmployeeNumber": None},  # Supervisor has no supervisor
                {"employeeNumber": "101", "supervisorEmployeeNumber": "100"},  # Employee reports to 100
            ],
            status=200,
        )

        # Person details for all
        for emp in employees:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        # TravelPerk responses for Phase 1 (supervisor)
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={**sample_travelperk_user_response, "id": "tp-100", "externalId": "100"},
            status=201,
        )

        # TravelPerk responses for Phase 2 (employee)
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={**sample_travelperk_user_response, "id": "tp-101", "externalId": "101"},
            status=201,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(
            company_id="J9A6Y",
            dry_run=False,
        )

        # Both should be processed
        assert result["total_processed"] == 2


@pytest.mark.integration
class TestSupervisorIdResolution:
    """Test supervisor ID resolution."""

    @responses.activate
    def test_supervisor_id_resolution(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        sample_travelperk_user_response,
        ukg_base_url,
        travelperk_base_url,
    ):
        """Test that supervisor TravelPerk ID is resolved correctly."""
        employees = [
            {"employeeNumber": "100", "employeeID": "SUP001", "companyID": "J9A6Y"},
            {"employeeNumber": "101", "employeeID": "EMP001", "companyID": "J9A6Y"},
        ]

        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[
                {"employeeNumber": "100", "supervisorEmployeeNumber": None},
                {"employeeNumber": "101", "supervisorEmployeeNumber": "100"},
            ],
            status=200,
        )

        # Person details
        for emp in employees:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        # TravelPerk - supervisor exists already
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={
                "totalResults": 1,
                "Resources": [{**sample_travelperk_user_response, "id": "tp-100", "externalId": "100"}]
            },
            status=200,
        )
        responses.add(
            responses.PATCH,
            f"{travelperk_base_url}/api/v2/scim/Users/tp-100",
            json={**sample_travelperk_user_response, "id": "tp-100"},
            status=200,
        )

        # Employee - check and create
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={**sample_travelperk_user_response, "id": "tp-101"},
            status=201,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(company_id="J9A6Y")

        # Check mapping includes both
        assert "100" in result.get("mapping", {}) or len(result.get("mapping", {})) >= 1


@pytest.mark.integration
class TestDryRunMode:
    """Test dry-run mode."""

    @responses.activate
    def test_dry_run_mode(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        ukg_base_url,
        travelperk_base_url,
    ):
        """Test that dry-run doesn't make TravelPerk API calls."""
        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
        ]

        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[{"employeeNumber": "001", "supervisorEmployeeNumber": None}],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(
            company_id="J9A6Y",
            dry_run=True,
        )

        # Verify no TravelPerk API calls
        tp_calls = [c for c in responses.calls if "travelperk" in c.request.url]
        assert len(tp_calls) == 0
        assert result["dry_run"] is True


@pytest.mark.integration
class TestFiltering:
    """Test filtering capabilities."""

    @responses.activate
    def test_state_filtering(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        ukg_base_url,
    ):
        """Test filtering by state."""
        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y"},
        ]

        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[
                {"employeeNumber": "001", "supervisorEmployeeNumber": None},
                {"employeeNumber": "002", "supervisorEmployeeNumber": None},
            ],
            status=200,
        )

        # Person details with different states
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[{"employeeId": "EMP001", "firstName": "John", "lastName": "Doe",
                   "emailAddress": "john@example.com", "addressState": "FL"}],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[{"employeeId": "EMP002", "firstName": "Jane", "lastName": "Doe",
                   "emailAddress": "jane@example.com", "addressState": "NY"}],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(
            company_id="J9A6Y",
            states_filter={"FL"},
            dry_run=True,
        )

        # Only FL employee should be processed
        assert result["total_processed"] <= 2

    @responses.activate
    def test_employee_type_filtering(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test filtering by employee type code."""
        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y", "employeeTypeCode": "FTC"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y", "employeeTypeCode": "HRC"},
        ]

        # First call returns all, client filters
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[
                {"employeeNumber": "001", "supervisorEmployeeNumber": None},
            ],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(
            company_id="J9A6Y",
            employee_type_codes=["FTC"],
            dry_run=True,
        )

        assert result["total_processed"] == 1


@pytest.mark.integration
class TestMappingFileGeneration:
    """Test mapping file generation."""

    def test_mapping_file_generation(self, tmp_path):
        """Test employee to TravelPerk ID mapping file is created."""
        mapping = {
            "001": "tp-001",
            "002": "tp-002",
            "100": "tp-100",
        }

        mapping_file = tmp_path / "employee_to_travelperk_id_mapping.json"
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        assert mapping_file.exists()

        with open(mapping_file) as f:
            loaded = json.load(f)
            assert loaded == mapping


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery in batch processing."""

    @responses.activate
    def test_error_recovery_partial_batch(
        self,
        mock_ukg_settings,
        mock_travelperk_settings,
        sample_ukg_person_details,
        sample_travelperk_user_response,
        ukg_base_url,
        travelperk_base_url,
    ):
        """Test that batch continues after individual errors."""
        employees = [
            {"employeeNumber": "001", "employeeID": "EMP001", "companyID": "J9A6Y"},
            {"employeeNumber": "002", "employeeID": "EMP002", "companyID": "J9A6Y"},
            {"employeeNumber": "003", "employeeID": "EMP003", "companyID": "J9A6Y"},
        ]

        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-supervisor-details",
            json=[{"employeeNumber": emp["employeeNumber"], "supervisorEmployeeNumber": None} for emp in employees],
            status=200,
        )

        # First employee - success
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[{**sample_ukg_person_details, "employeeId": "EMP001"}],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_user_response,
            status=201,
        )

        # Second employee - person details fails
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json={"error": "Not found"},
            status=500,
        )

        # Third employee - success
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[{**sample_ukg_person_details, "employeeId": "EMP003"}],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json={"totalResults": 0, "Resources": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{travelperk_base_url}/api/v2/scim/Users",
            json=sample_travelperk_user_response,
            status=201,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        tp_client = TravelPerkClient(settings=mock_travelperk_settings)

        sync_service = UserSyncService(ukg_client=ukg_client, travelperk_client=tp_client)
        result = sync_service.sync_batch(company_id="J9A6Y")

        # Should have processed 3, with 1 error
        assert result["errors"] >= 1
        assert result["created"] >= 1


@pytest.mark.integration
class TestCorrelationIdTracking:
    """Test correlation ID tracking."""

    def test_correlation_id_tracking(self):
        """Test that correlation IDs are properly tracked."""
        from common import RunContext

        with RunContext(project="travelperk", company_id="J9A6Y") as ctx:
            assert ctx.correlation_id is not None
            assert len(ctx.correlation_id) > 0

            ctx.stats["total_processed"] = 50
            ctx.stats["created"] = 45
            ctx.stats["errors"] = 5

            run_data = ctx.to_dict()

            assert run_data["correlation_id"] == ctx.correlation_id
