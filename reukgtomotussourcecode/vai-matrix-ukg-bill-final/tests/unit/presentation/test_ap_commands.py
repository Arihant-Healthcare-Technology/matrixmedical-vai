"""
Unit tests for AP commands for Accounts Payable operations.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from decimal import Decimal


class TestRunVendorSync:
    """Tests for run_vendor_sync function."""

    def test_returns_one_without_vendor_file(self):
        """Test returns 1 when vendor file not provided."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        mock_container = MagicMock()

        result = run_vendor_sync(mock_container, vendor_file=None)

        assert result == 1

    def test_returns_zero_on_dry_run(self, tmp_path):
        """Test returns 0 on dry run mode."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {"name": "Test Vendor", "email": "test@vendor.com"}
        ]))

        mock_container = MagicMock()

        result = run_vendor_sync(
            mock_container,
            vendor_file=str(vendor_file),
            dry_run=True,
        )

        assert result == 0

    def test_returns_one_on_file_not_found(self):
        """Test returns 1 when file not found."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        mock_container = MagicMock()

        result = run_vendor_sync(
            mock_container,
            vendor_file="/nonexistent/file.json",
        )

        assert result == 1

    def test_returns_one_on_invalid_json(self, tmp_path):
        """Test returns 1 on invalid JSON."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text("not valid json{")

        mock_container = MagicMock()

        result = run_vendor_sync(
            mock_container,
            vendor_file=str(vendor_file),
        )

        assert result == 1

    def test_returns_zero_on_successful_sync(self, tmp_path):
        """Test returns 0 on successful sync."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {"name": "Test Vendor", "email": "test@vendor.com"}
        ]))

        mock_container = MagicMock()
        mock_vendor_service = MagicMock()

        # Use a real-like object instead of MagicMock for format string support
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

        mock_vendor_service.sync_batch.return_value = MockResult()
        mock_container.vendor_service.return_value = mock_vendor_service

        result = run_vendor_sync(
            mock_container,
            vendor_file=str(vendor_file),
        )

        assert result == 0

    def test_returns_one_on_sync_errors(self, tmp_path):
        """Test returns 1 when sync has errors."""
        from src.presentation.cli.ap_commands import run_vendor_sync

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {"name": "Test Vendor", "email": "test@vendor.com"}
        ]))

        mock_container = MagicMock()
        mock_vendor_service = MagicMock()

        class MockErrorResult:
            action = "error"
            entity_id = "v1"
            message = "Failed"

        class MockResult:
            errors = 1
            total = 1
            created = 0
            updated = 0
            skipped = 0
            success_rate = 0.0
            duration = 1.0
            correlation_id = "test-123"
            results = [MockErrorResult()]

        mock_vendor_service.sync_batch.return_value = MockResult()
        mock_container.vendor_service.return_value = mock_vendor_service

        result = run_vendor_sync(
            mock_container,
            vendor_file=str(vendor_file),
        )

        assert result == 1


class TestRunInvoiceSync:
    """Tests for run_invoice_sync function."""

    def test_returns_one_without_invoice_file(self):
        """Test returns 1 when invoice file not provided."""
        from src.presentation.cli.ap_commands import run_invoice_sync

        mock_container = MagicMock()

        result = run_invoice_sync(mock_container, invoice_file=None)

        assert result == 1

    def test_returns_zero_on_dry_run(self, tmp_path):
        """Test returns 0 on dry run mode."""
        from src.presentation.cli.ap_commands import run_invoice_sync

        invoice_file = tmp_path / "invoices.json"
        invoice_file.write_text(json.dumps([
            {
                "invoice_number": "INV-001",
                "vendor_id": "v-123",
                "total_amount": 100.00,
            }
        ]))

        mock_container = MagicMock()

        result = run_invoice_sync(
            mock_container,
            invoice_file=str(invoice_file),
            dry_run=True,
        )

        assert result == 0

    def test_returns_one_on_file_not_found(self):
        """Test returns 1 when file not found."""
        from src.presentation.cli.ap_commands import run_invoice_sync

        mock_container = MagicMock()

        result = run_invoice_sync(
            mock_container,
            invoice_file="/nonexistent/file.json",
        )

        assert result == 1

    def test_loads_vendor_mapping(self, tmp_path):
        """Test loads vendor mapping when provided."""
        from src.presentation.cli.ap_commands import run_invoice_sync

        invoice_file = tmp_path / "invoices.json"
        invoice_file.write_text(json.dumps([
            {"invoice_number": "INV-001", "vendor_id": "v-123", "total_amount": 100}
        ]))

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps({"ext-v-1": "bill-v-1"}))

        mock_container = MagicMock()
        mock_invoice_service = MagicMock()

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

        mock_invoice_service.sync_batch.return_value = MockResult()
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_invoice_sync(
            mock_container,
            invoice_file=str(invoice_file),
            vendor_mapping_file=str(mapping_file),
        )

        assert result == 0
        mock_invoice_service.sync_batch.assert_called_once()


class TestRunPaymentProcess:
    """Tests for run_payment_process function."""

    def test_returns_one_without_invoice_ids_or_all(self):
        """Test returns 1 when no invoice IDs and not pay_all_approved."""
        from src.presentation.cli.ap_commands import run_payment_process

        mock_container = MagicMock()
        mock_container.payment_service.return_value = MagicMock()
        mock_container.invoice_service.return_value = MagicMock()

        result = run_payment_process(mock_container)

        assert result == 1

    def test_returns_zero_on_no_invoices_to_pay(self):
        """Test returns 0 when no invoices to process."""
        from src.presentation.cli.ap_commands import run_payment_process

        mock_container = MagicMock()
        mock_payment_service = MagicMock()
        mock_invoice_service = MagicMock()
        mock_invoice_service.get_payable_invoices.return_value = []
        mock_container.payment_service.return_value = mock_payment_service
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_payment_process(mock_container, pay_all_approved=True)

        assert result == 0

    def test_returns_zero_on_dry_run(self):
        """Test returns 0 on dry run mode."""
        from src.presentation.cli.ap_commands import run_payment_process

        mock_container = MagicMock()
        mock_payment_service = MagicMock()
        mock_invoice_service = MagicMock()

        mock_invoice = MagicMock()
        mock_invoice.total_amount = Decimal("100.00")
        mock_invoice_service.get_payable_invoices.return_value = [mock_invoice]

        mock_container.payment_service.return_value = mock_payment_service
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_payment_process(
            mock_container,
            pay_all_approved=True,
            dry_run=True,
        )

        assert result == 0

    def test_processes_specific_invoice_ids(self):
        """Test processes specific invoice IDs."""
        from src.presentation.cli.ap_commands import run_payment_process

        mock_container = MagicMock()
        mock_payment_service = MagicMock()
        mock_invoice_service = MagicMock()

        mock_invoice = MagicMock()
        mock_invoice.total_amount = Decimal("100.00")
        mock_invoice_service.get_invoice_by_id.return_value = mock_invoice

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

        mock_payment_service.create_bulk_payments.return_value = MockResult()

        mock_container.payment_service.return_value = mock_payment_service
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_payment_process(
            mock_container,
            invoice_ids=["inv-123"],
        )

        assert result == 0
        mock_invoice_service.get_invoice_by_id.assert_called_once_with("inv-123")

    def test_handles_missing_invoice(self):
        """Test handles missing invoice gracefully."""
        from src.presentation.cli.ap_commands import run_payment_process

        mock_container = MagicMock()
        mock_payment_service = MagicMock()
        mock_invoice_service = MagicMock()
        mock_invoice_service.get_invoice_by_id.return_value = None

        mock_container.payment_service.return_value = mock_payment_service
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_payment_process(
            mock_container,
            invoice_ids=["missing-id"],
        )

        # Returns 0 since no invoices to process
        assert result == 0


class TestRunAPBatch:
    """Tests for run_ap_batch function."""

    def test_returns_one_without_any_step(self):
        """Test returns 1 when no steps selected."""
        from src.presentation.cli.ap_commands import run_ap_batch

        mock_container = MagicMock()

        result = run_ap_batch(mock_container)

        assert result == 1

    def test_runs_vendor_sync_step(self, tmp_path):
        """Test runs vendor sync step."""
        from src.presentation.cli.ap_commands import run_ap_batch

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {"name": "Test Vendor", "email": "test@vendor.com"}
        ]))

        mock_container = MagicMock()
        mock_vendor_service = MagicMock()

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

        mock_vendor_service.sync_batch.return_value = MockResult()
        mock_container.vendor_service.return_value = mock_vendor_service

        result = run_ap_batch(
            mock_container,
            include_vendors=True,
            data_dir=str(tmp_path),
        )

        assert result == 0

    def test_runs_multiple_steps(self, tmp_path):
        """Test runs multiple steps in sequence."""
        from src.presentation.cli.ap_commands import run_ap_batch

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([{"name": "Test", "email": "t@t.com"}]))

        invoice_file = tmp_path / "invoices.json"
        invoice_file.write_text(json.dumps([{"invoice_number": "INV-1", "vendor_id": "v1", "total_amount": 100}]))

        mock_container = MagicMock()

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

        # Mock vendor service
        mock_vendor_service = MagicMock()
        mock_vendor_service.sync_batch.return_value = MockResult()
        mock_container.vendor_service.return_value = mock_vendor_service

        # Mock invoice service
        mock_invoice_service = MagicMock()
        mock_invoice_service.sync_batch.return_value = MockResult()
        mock_container.invoice_service.return_value = mock_invoice_service

        result = run_ap_batch(
            mock_container,
            include_vendors=True,
            include_invoices=True,
            data_dir=str(tmp_path),
        )

        assert result == 0

    def test_returns_one_on_step_failure(self):
        """Test returns 1 when a step fails."""
        from src.presentation.cli.ap_commands import run_ap_batch

        mock_container = MagicMock()

        result = run_ap_batch(
            mock_container,
            include_vendors=True,
            data_dir="/nonexistent",
        )

        assert result == 1


class TestLoadVendorsFromFile:
    """Tests for _load_vendors_from_file function."""

    def test_loads_vendor_list(self, tmp_path):
        """Test loads vendor list."""
        from src.presentation.cli.ap_commands import _load_vendors_from_file

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {
                "name": "Acme Corp",
                "email": "billing@acme.com",
                "external_id": "EXT-001",
                "address_line1": "123 Main St",
                "address_city": "Seattle",
                "address_state": "WA",
                "address_zip": "98101",
            }
        ]))

        vendors = _load_vendors_from_file(str(vendor_file))

        assert len(vendors) == 1
        assert vendors[0].name == "Acme Corp"
        assert vendors[0].email == "billing@acme.com"

    def test_loads_vendor_dict_format(self, tmp_path):
        """Test loads vendors from dict format."""
        from src.presentation.cli.ap_commands import _load_vendors_from_file

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps({
            "vendors": [
                {"name": "Test Vendor", "email": "test@vendor.com"}
            ]
        }))

        vendors = _load_vendors_from_file(str(vendor_file))

        assert len(vendors) == 1

    def test_handles_nested_address(self, tmp_path):
        """Test handles nested address structure."""
        from src.presentation.cli.ap_commands import _load_vendors_from_file

        vendor_file = tmp_path / "vendors.json"
        vendor_file.write_text(json.dumps([
            {
                "name": "Test Vendor",
                "email": "test@vendor.com",
                "address": {
                    "line1": "456 Oak Ave",
                    "city": "Portland",
                    "state": "OR",
                    "zip": "97201",
                }
            }
        ]))

        vendors = _load_vendors_from_file(str(vendor_file))

        assert len(vendors) == 1
        assert vendors[0].address.city == "Portland"


class TestLoadInvoicesFromFile:
    """Tests for _load_invoices_from_file function."""

    def test_loads_invoice_list(self, tmp_path):
        """Test loads invoice list."""
        from src.presentation.cli.ap_commands import _load_invoices_from_file

        invoice_file = tmp_path / "invoices.json"
        invoice_file.write_text(json.dumps([
            {
                "invoice_number": "INV-001",
                "vendor_id": "v-123",
                "invoice_date": "2025-03-01",
                "due_date": "2025-03-31",
                "total_amount": 500.00,
                "line_items": [
                    {"description": "Service", "amount": 500.00, "quantity": 1}
                ]
            }
        ]))

        invoices = _load_invoices_from_file(str(invoice_file))

        assert len(invoices) == 1
        assert invoices[0].invoice_number == "INV-001"
        assert invoices[0].total_amount == Decimal("500.00")

    def test_loads_invoice_dict_format(self, tmp_path):
        """Test loads invoices from dict format."""
        from src.presentation.cli.ap_commands import _load_invoices_from_file

        invoice_file = tmp_path / "invoices.json"
        invoice_file.write_text(json.dumps({
            "invoices": [
                {"invoice_number": "INV-002", "vendor_id": "v-1", "total_amount": 100}
            ]
        }))

        invoices = _load_invoices_from_file(str(invoice_file))

        assert len(invoices) == 1


class TestLoadVendorMapping:
    """Tests for _load_vendor_mapping function."""

    def test_loads_mapping(self, tmp_path):
        """Test loads vendor mapping."""
        from src.presentation.cli.ap_commands import _load_vendor_mapping

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps({
            "ext-v-1": "bill-v-1",
            "ext-v-2": "bill-v-2",
        }))

        mapping = _load_vendor_mapping(str(mapping_file))

        assert mapping["ext-v-1"] == "bill-v-1"
        assert mapping["ext-v-2"] == "bill-v-2"


class TestPrintFunctions:
    """Tests for print helper functions (now in utils.py)."""

    def test_print_preview_with_invoices(self, capsys):
        """Test print_preview with invoice objects."""
        from src.presentation.cli.utils import print_preview

        mock_invoice = MagicMock()
        mock_invoice.invoice_number = "INV-001"
        mock_invoice.total_amount = Decimal("100.00")

        print_preview([mock_invoice], "test invoices")

        captured = capsys.readouterr()
        assert "INV-001" in captured.out
        assert "100" in captured.out

    def test_print_preview_with_vendors(self, capsys):
        """Test print_preview with vendor objects."""
        from src.presentation.cli.utils import print_preview

        class MockVendor:
            name = "Acme Corp"
            email = "billing@acme.com"

        print_preview([MockVendor()], "test vendors")

        captured = capsys.readouterr()
        assert "Acme Corp" in captured.out

    def test_print_sync_result(self, capsys):
        """Test print_sync_result."""
        from src.presentation.cli.utils import print_sync_result

        mock_result = MagicMock()
        mock_result.total = 10
        mock_result.created = 5
        mock_result.updated = 3
        mock_result.skipped = 2
        mock_result.errors = 0
        mock_result.success_rate = 100.0
        mock_result.duration = 5.5
        mock_result.correlation_id = "test-correlation"
        mock_result.results = []

        print_sync_result(mock_result, "TEST SYNC")

        captured = capsys.readouterr()
        assert "TEST SYNC" in captured.out
        assert "10" in captured.out
        assert "100.0%" in captured.out

    def test_print_sync_result_with_errors(self, capsys):
        """Test print_sync_result with errors."""
        from src.presentation.cli.utils import print_sync_result

        class MockError:
            action = "error"
            entity_id = "entity-1"
            message = "Something failed"

        class MockResult:
            total = 10
            created = 5
            updated = 3
            skipped = 1
            errors = 1
            success_rate = 90.0
            duration = 2.0
            correlation_id = "test-correlation"
            results = [MockError()]

        print_sync_result(MockResult(), "TEST SYNC")

        captured = capsys.readouterr()
        assert "Errors:" in captured.out
        assert "entity-1" in captured.out
        assert "Something failed" in captured.out
