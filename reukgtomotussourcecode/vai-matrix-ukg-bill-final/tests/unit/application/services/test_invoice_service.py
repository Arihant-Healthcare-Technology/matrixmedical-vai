"""
Unit tests for InvoiceService.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

import pytest

from src.application.services.invoice_service import InvoiceService
from src.domain.models.invoice import Invoice, BillStatus, InvoiceLineItem


@pytest.fixture
def mock_invoice_repo():
    """Create mock invoice repository."""
    return MagicMock()


@pytest.fixture
def mock_vendor_repo():
    """Create mock vendor repository."""
    return MagicMock()


@pytest.fixture
def invoice_service(mock_invoice_repo, mock_vendor_repo):
    """Create invoice service with mocked dependencies."""
    return InvoiceService(
        invoice_repository=mock_invoice_repo,
        vendor_repository=mock_vendor_repo,
    )


@pytest.fixture
def sample_invoice():
    """Create sample invoice."""
    return Invoice(
        id="INV001",
        invoice_number="INV-2024-001",
        vendor_id="VND001",
        invoice_date=date(2024, 3, 1),
        due_date=date(2024, 4, 1),
        status=BillStatus.OPEN,
        line_items=[
            InvoiceLineItem(description="Service", amount=Decimal("1000.00")),
        ],
        total_amount=Decimal("1000.00"),
    )


class TestSyncInvoice:
    """Tests for sync_invoice method."""

    def test_creates_new_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should create invoice when not found."""
        mock_invoice_repo.get_by_id.return_value = None
        mock_invoice_repo.get_by_external_id.return_value = None
        mock_invoice_repo.get_by_invoice_number.return_value = None
        mock_invoice_repo.create.return_value = sample_invoice

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is True
        assert result.action == "create"
        mock_invoice_repo.create.assert_called_once()

    def test_updates_existing_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should update invoice when found with changes."""
        existing = Invoice(
            id="INV001",
            invoice_number="INV-2024-001",
            vendor_id="VND001",
            invoice_date=date(2024, 3, 1),
            due_date=date(2024, 3, 15),  # Different due date
            status=BillStatus.OPEN,
            line_items=[InvoiceLineItem(description="Old", amount=Decimal("500.00"))],
            total_amount=Decimal("500.00"),  # Different amount
        )
        mock_invoice_repo.get_by_invoice_number.return_value = existing
        mock_invoice_repo.update.return_value = sample_invoice

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is True
        assert result.action == "update"
        mock_invoice_repo.update.assert_called_once()

    def test_skips_unchanged_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should skip when no changes detected."""
        # Mock get_by_id to return the same invoice (since sample_invoice has an id)
        mock_invoice_repo.get_by_id.return_value = sample_invoice

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is True
        assert result.action == "skip"

    def test_error_missing_invoice_number(self, invoice_service, sample_invoice):
        """Should return error for invoice without number."""
        sample_invoice.invoice_number = None

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is False
        assert result.action == "error"

    def test_error_missing_vendor_id(self, invoice_service, sample_invoice):
        """Should return error for invoice without vendor."""
        sample_invoice.vendor_id = None

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is False
        assert result.action == "error"

    def test_error_no_line_items(self, invoice_service, sample_invoice):
        """Should return error for invoice without line items."""
        sample_invoice.line_items = []
        sample_invoice.total_amount = None

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is False
        assert result.action == "error"

    def test_cannot_update_paid_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should not update invoice with PAID status."""
        existing = Invoice(
            id="INV001",
            invoice_number="INV-2024-001",
            vendor_id="VND001",
            invoice_date=date(2024, 3, 1),
            due_date=date(2024, 4, 1),
            status=BillStatus.PAID,
            line_items=[InvoiceLineItem(description="Svc", amount=Decimal("500.00"))],
            total_amount=Decimal("500.00"),
        )
        # Mock get_by_id since sample_invoice has an id
        mock_invoice_repo.get_by_id.return_value = existing

        result = invoice_service.sync_invoice(sample_invoice)

        assert result.success is False
        assert "status" in result.message.lower()

    def test_applies_vendor_mapping(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should apply vendor ID mapping."""
        sample_invoice.vendor_id = "EXT001"
        sample_invoice.id = None  # Remove ID so it creates new
        vendor_mapping = {"EXT001": "BILL001"}

        mock_invoice_repo.get_by_id.return_value = None
        mock_invoice_repo.get_by_external_id.return_value = None
        mock_invoice_repo.get_by_invoice_number.return_value = None
        mock_invoice_repo.create.return_value = sample_invoice

        invoice_service.sync_invoice(sample_invoice, vendor_mapping)

        # Check the vendor_id was mapped
        created = mock_invoice_repo.create.call_args[0][0]
        assert created.vendor_id == "BILL001"


class TestSyncBatch:
    """Tests for sync_batch method."""

    def test_empty_batch(self, invoice_service):
        """Should handle empty invoice list."""
        result = invoice_service.sync_batch([])

        assert result.total == 0
        assert result.created == 0

    def test_batch_processes_all_invoices(
        self,
        invoice_service,
        mock_invoice_repo,
    ):
        """Should process all invoices in batch."""
        invoices = [
            Invoice(
                invoice_number=f"INV-{i}",
                vendor_id="VND001",
                invoice_date=date(2024, 3, 1),
                due_date=date(2024, 4, 1),
                status=BillStatus.OPEN,
                line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
                total_amount=Decimal("100.00"),
            )
            for i in range(3)
        ]

        # Mock all lookup methods to return None (new invoice)
        mock_invoice_repo.get_by_id.return_value = None
        mock_invoice_repo.get_by_external_id.return_value = None
        mock_invoice_repo.get_by_invoice_number.return_value = None
        mock_invoice_repo.create.side_effect = [
            Invoice(
                id=f"INV{i}",
                invoice_number=f"INV-{i}",
                vendor_id="VND001",
                invoice_date=date(2024, 3, 1),
                due_date=date(2024, 4, 1),
                status=BillStatus.OPEN,
                line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
                total_amount=Decimal("100.00"),
            )
            for i in range(3)
        ]

        result = invoice_service.sync_batch(invoices, workers=1)

        assert result.total == 3
        assert result.created == 3


class TestGetPayableInvoices:
    """Tests for get_payable_invoices method."""

    def test_returns_approved_invoices(
        self,
        invoice_service,
        mock_invoice_repo,
    ):
        """Should return approved and scheduled invoices."""
        approved = Invoice(
            id="INV001",
            invoice_number="INV-1",
            vendor_id="VND001",
            invoice_date=date(2024, 3, 1),
            due_date=date(2024, 4, 1),
            status=BillStatus.APPROVED,
            line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
        )
        scheduled = Invoice(
            id="INV002",
            invoice_number="INV-2",
            vendor_id="VND001",
            invoice_date=date(2024, 3, 1),
            due_date=date(2024, 4, 1),
            status=BillStatus.SCHEDULED,
            line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
        )
        open_inv = Invoice(
            id="INV003",
            invoice_number="INV-3",
            vendor_id="VND001",
            invoice_date=date(2024, 3, 1),
            due_date=date(2024, 4, 1),
            status=BillStatus.OPEN,
            line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
        )
        mock_invoice_repo.list.return_value = [approved, scheduled, open_inv]

        result = invoice_service.get_payable_invoices()

        assert len(result) == 2
        assert approved in result
        assert scheduled in result
        assert open_inv not in result


class TestVoidInvoice:
    """Tests for void_invoice method."""

    def test_voids_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should void open invoice."""
        mock_invoice_repo.get_by_id.return_value = sample_invoice
        mock_invoice_repo.update.return_value = sample_invoice

        result = invoice_service.void_invoice("INV001", "Cancelled by customer")

        assert result.success is True
        assert result.action == "update"
        updated = mock_invoice_repo.update.call_args[0][0]
        assert updated.status == BillStatus.VOIDED

    def test_cannot_void_paid_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should not void paid invoice."""
        sample_invoice.status = BillStatus.PAID
        mock_invoice_repo.get_by_id.return_value = sample_invoice

        result = invoice_service.void_invoice("INV001")

        assert result.success is False
        assert "status" in result.message.lower()


class TestApproveInvoice:
    """Tests for approve_invoice method."""

    def test_approves_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should approve open invoice."""
        mock_invoice_repo.get_by_id.return_value = sample_invoice
        mock_invoice_repo.update.return_value = sample_invoice

        result = invoice_service.approve_invoice("INV001")

        assert result.success is True
        updated = mock_invoice_repo.update.call_args[0][0]
        assert updated.status == BillStatus.APPROVED

    def test_cannot_approve_non_open_invoice(
        self,
        invoice_service,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should not approve invoice that's not OPEN."""
        sample_invoice.status = BillStatus.APPROVED
        mock_invoice_repo.get_by_id.return_value = sample_invoice

        result = invoice_service.approve_invoice("INV001")

        assert result.success is False
