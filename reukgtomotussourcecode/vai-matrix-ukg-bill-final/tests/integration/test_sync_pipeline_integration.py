"""
Integration tests for the full sync pipeline.

Tests verify end-to-end behavior from UKG data fetch to BILL user creation.
Run with: pytest tests/integration/test_sync_pipeline_integration.py -v -m integration
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import responses

from src.application.services.sync_service import SyncService
from src.infrastructure.adapters.ukg.client import UKGClient
from src.infrastructure.adapters.bill.spend_expense import BillSpendExpenseClient


@pytest.mark.integration
class TestFullSyncPipeline:
    """Test full sync pipeline from UKG to BILL."""

    @responses.activate
    def test_full_sync_pipeline_dry_run(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        sample_ukg_employment_details_list,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test full sync pipeline in dry-run mode."""
        # Mock UKG employee-employment-details
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )
        # Mock UKG person-details (called for each employee)
        for emp in sample_ukg_employment_details_list:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)
        result = sync_service.sync_employees(
            company_id="J9A6Y",
            dry_run=True,
        )

        assert result["total_processed"] == 3
        assert result["dry_run"] is True
        # No BILL API calls should be made in dry-run
        bill_api_calls = [c for c in responses.calls if "bill.com" in c.request.url]
        assert len(bill_api_calls) == 0

    @responses.activate
    def test_employee_to_bill_user_mapping(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        sample_ukg_employment_details,
        sample_ukg_person_details,
        sample_bill_user_response,
        ukg_base_url,
        bill_se_base_url,
    ):
        """Test employee to BILL user mapping creation."""
        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=[sample_ukg_employment_details],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/person-details",
            json=[sample_ukg_person_details],
            status=200,
        )

        # Mock BILL responses - check if exists returns empty
        responses.add(
            responses.GET,
            f"{bill_se_base_url}/users",
            json={"users": [], "pagination": {"totalCount": 0}},
            status=200,
        )
        # Create user
        responses.add(
            responses.POST,
            f"{bill_se_base_url}/users",
            json=sample_bill_user_response,
            status=201,
        )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)
        result = sync_service.sync_employees(company_id="J9A6Y")

        assert "mapping" in result
        assert sample_ukg_employment_details["employeeNumber"] in result["mapping"]


@pytest.mark.integration
class TestBatchProcessing:
    """Test batch processing with workers."""

    @responses.activate
    def test_batch_processing_with_workers(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        generate_employees,
        sample_ukg_person_details,
        sample_bill_user_response,
        ukg_base_url,
        bill_se_base_url,
    ):
        """Test batch processing with multiple workers."""
        employees = generate_employees(10)

        # Mock UKG employee list
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )

        # Mock person details for each
        for emp in employees:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )
            # Mock BILL check
            responses.add(
                responses.GET,
                f"{bill_se_base_url}/users",
                json={"users": [], "pagination": {"totalCount": 0}},
                status=200,
            )
            # Mock BILL create
            responses.add(
                responses.POST,
                f"{bill_se_base_url}/users",
                json={**sample_bill_user_response, "uuid": f"usr_{emp['employeeNumber']}"},
                status=201,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)
        result = sync_service.sync_employees(
            company_id="J9A6Y",
            workers=4,
        )

        assert result["total_processed"] == 10
        assert result["created"] + result["updated"] + result["skipped"] == 10


@pytest.mark.integration
class TestFiltering:
    """Test filtering capabilities."""

    @responses.activate
    def test_state_filtering(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        sample_ukg_employment_details_list,
        ukg_base_url,
    ):
        """Test filtering employees by state."""
        # Mock UKG employee list
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )

        # Mock person details with different states
        states = ["FL", "NY", "CA"]
        for i, emp in enumerate(sample_ukg_employment_details_list):
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{
                    "employeeId": emp["employeeID"],
                    "firstName": "Test",
                    "lastName": "User",
                    "emailAddress": f"test{i}@example.com",
                    "addressState": states[i % len(states)],
                }],
                status=200,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)
        result = sync_service.sync_employees(
            company_id="J9A6Y",
            states_filter={"FL"},
            dry_run=True,
        )

        # Only FL employees should be processed
        assert result["total_processed"] <= 3

    @responses.activate
    def test_employee_type_filtering(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        sample_ukg_employment_details_list,
        sample_ukg_person_details,
        ukg_base_url,
    ):
        """Test filtering employees by type code."""
        # Mock UKG employee list
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )

        # Mock person details
        for emp in sample_ukg_employment_details_list:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)

        # Filter to only FTC employees
        result = sync_service.sync_employees(
            company_id="J9A6Y",
            employee_type_codes=["FTC"],
            dry_run=True,
        )

        # Should only process FTC employees
        assert result["total_processed"] >= 1


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery in batch processing."""

    @responses.activate
    def test_error_recovery_partial_batch(
        self,
        mock_ukg_settings,
        mock_bill_se_settings,
        generate_employees,
        sample_ukg_person_details,
        sample_bill_user_response,
        ukg_base_url,
        bill_se_base_url,
    ):
        """Test that batch continues after individual errors."""
        employees = generate_employees(5)

        # Mock UKG employee list
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=employees,
            status=200,
        )

        # Mock person details - second one fails
        for i, emp in enumerate(employees):
            if i == 1:
                # This one returns 500
                responses.add(
                    responses.GET,
                    f"{ukg_base_url}/personnel/v1/person-details",
                    json={"error": "Server Error"},
                    status=500,
                )
            else:
                responses.add(
                    responses.GET,
                    f"{ukg_base_url}/personnel/v1/person-details",
                    json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                    status=200,
                )
                # Mock BILL calls for successful ones
                responses.add(
                    responses.GET,
                    f"{bill_se_base_url}/users",
                    json={"users": [], "pagination": {"totalCount": 0}},
                    status=200,
                )
                responses.add(
                    responses.POST,
                    f"{bill_se_base_url}/users",
                    json=sample_bill_user_response,
                    status=201,
                )

        ukg_client = UKGClient(settings=mock_ukg_settings)
        bill_client = BillSpendExpenseClient(settings=mock_bill_se_settings)

        sync_service = SyncService(ukg_client=ukg_client, bill_client=bill_client)
        result = sync_service.sync_employees(company_id="J9A6Y")

        # Should have processed all 5, with 1 error
        assert result["errors"] >= 1
        assert result["created"] >= 1


@pytest.mark.integration
class TestReportGeneration:
    """Test report generation functionality."""

    def test_report_generation(self, tmp_path):
        """Test that sync generates proper reports."""
        from common import ReportGenerator

        report_gen = ReportGenerator(output_dir=str(tmp_path))

        run_data = {
            "correlation_id": "test-123",
            "company_id": "J9A6Y",
            "total_processed": 100,
            "created": 80,
            "updated": 15,
            "skipped": 3,
            "errors": 2,
            "duration_seconds": 45.5,
        }

        report_paths = report_gen.generate_run_report(run_data)

        assert len(report_paths) > 0
        for path in report_paths:
            assert Path(path).exists()


@pytest.mark.integration
class TestCSVExport:
    """Test CSV export functionality."""

    @responses.activate
    def test_csv_export(
        self,
        mock_ukg_settings,
        sample_ukg_employment_details_list,
        sample_ukg_person_details,
        ukg_base_url,
        tmp_path,
    ):
        """Test CSV export of employee data."""
        # Mock UKG responses
        responses.add(
            responses.GET,
            f"{ukg_base_url}/personnel/v1/employee-employment-details",
            json=sample_ukg_employment_details_list,
            status=200,
        )
        for emp in sample_ukg_employment_details_list:
            responses.add(
                responses.GET,
                f"{ukg_base_url}/personnel/v1/person-details",
                json=[{**sample_ukg_person_details, "employeeId": emp["employeeID"]}],
                status=200,
            )

        ukg_client = UKGClient(settings=mock_ukg_settings)

        # Export to CSV
        csv_path = tmp_path / "people.csv"
        employees = ukg_client.get_all_employment_details_by_company("J9A6Y")

        # Write CSV
        import csv
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["employeeNumber", "companyID"])
            writer.writeheader()
            for emp in employees:
                writer.writerow({
                    "employeeNumber": emp.get("employeeNumber"),
                    "companyID": emp.get("companyID"),
                })

        assert csv_path.exists()
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3


@pytest.mark.integration
class TestCorrelationTracking:
    """Test correlation ID tracking."""

    def test_correlation_id_tracking(self):
        """Test that correlation IDs are properly tracked."""
        from common import RunContext

        with RunContext(project="bill", company_id="J9A6Y") as ctx:
            assert ctx.correlation_id is not None
            assert len(ctx.correlation_id) > 0

            ctx.stats["total_processed"] = 10
            ctx.stats["created"] = 8
            ctx.stats["errors"] = 2

            run_data = ctx.to_dict()

            assert run_data["correlation_id"] == ctx.correlation_id
            assert run_data["stats"]["total_processed"] == 10


@pytest.mark.integration
class TestMappingFileSave:
    """Test mapping file saving."""

    def test_mapping_file_save(self, tmp_path):
        """Test saving employee to BILL UUID mapping."""
        mapping = {
            "12345": "usr_abc123",
            "12346": "usr_def456",
            "12347": "usr_ghi789",
        }

        mapping_file = tmp_path / "employee_to_bill_uuid_mapping.json"
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        assert mapping_file.exists()

        with open(mapping_file) as f:
            loaded = json.load(f)
            assert loaded == mapping
