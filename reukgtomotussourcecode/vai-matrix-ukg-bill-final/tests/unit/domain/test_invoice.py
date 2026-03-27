"""
Unit tests for Invoice domain model.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.domain.models.invoice import (
    BillStatus,
    Invoice,
    InvoiceLineItem,
)


class TestBillStatus:
    """Tests for BillStatus enum."""

    def test_from_string_valid_statuses(self):
        """Test converting valid status strings."""
        assert BillStatus.from_string("open") == BillStatus.OPEN
        assert BillStatus.from_string("OPEN") == BillStatus.OPEN
        assert BillStatus.from_string("paid") == BillStatus.PAID
        assert BillStatus.from_string("voided") == BillStatus.VOIDED

    def test_from_string_invalid_defaults_to_open(self):
        """Test invalid status defaults to OPEN."""
        assert BillStatus.from_string("INVALID") == BillStatus.OPEN
        assert BillStatus.from_string("") == BillStatus.OPEN

    def test_is_payable(self):
        """Test is_payable property."""
        assert BillStatus.OPEN.is_payable is True
        assert BillStatus.APPROVED.is_payable is True
        assert BillStatus.PAID.is_payable is False
        assert BillStatus.VOIDED.is_payable is False

    def test_is_updatable(self):
        """Test is_updatable property."""
        assert BillStatus.OPEN.is_updatable is True
        assert BillStatus.APPROVED.is_updatable is True
        assert BillStatus.PAID.is_updatable is False
        assert BillStatus.VOIDED.is_updatable is False
        assert BillStatus.PARTIAL.is_updatable is False


class TestInvoiceLineItem:
    """Tests for InvoiceLineItem dataclass."""

    def test_basic_creation(self):
        """Test basic line item creation."""
        item = InvoiceLineItem(
            amount=Decimal("100.00"),
            description="Service fee",
        )
        assert item.amount == Decimal("100.00")
        assert item.description == "Service fee"

    def test_amount_conversion_from_float(self):
        """Test amount is converted from float to Decimal."""
        item = InvoiceLineItem(amount=100.50)  # type: ignore
        assert item.amount == Decimal("100.5")

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        item = InvoiceLineItem(
            amount=Decimal("500.00"),
            description="Consulting",
            gl_account_id="GL001",
            department_id="DEPT001",
        )
        payload = item.to_api_payload()
        assert payload["amount"] == 500.0
        assert payload["description"] == "Consulting"
        assert payload["glAccountId"] == "GL001"
        assert payload["departmentId"] == "DEPT001"

    def test_to_api_payload_minimal(self):
        """Test API payload with minimal fields."""
        item = InvoiceLineItem(amount=Decimal("100.00"))
        payload = item.to_api_payload()
        assert payload == {"amount": 100.0}

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "amount": 250.50,
            "description": "Parts",
            "glAccountId": "GL002",
        }
        item = InvoiceLineItem.from_dict(data)
        assert item.amount == Decimal("250.5")
        assert item.description == "Parts"
        assert item.gl_account_id == "GL002"


class TestInvoice:
    """Tests for Invoice domain model."""

    def test_basic_creation(self):
        """Test basic invoice creation."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            line_items=[
                InvoiceLineItem(amount=Decimal("1000.00"), description="Services"),
            ],
        )
        assert invoice.invoice_number == "INV-001"
        assert invoice.vendor_id == "vendor-123"
        assert invoice.status == BillStatus.OPEN

    def test_string_normalization(self):
        """Test string fields are stripped."""
        invoice = Invoice(
            invoice_number="  INV-001  ",
            vendor_id="  vendor-123  ",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        assert invoice.invoice_number == "INV-001"
        assert invoice.vendor_id == "vendor-123"

    def test_external_id_defaults_to_invoice_number(self):
        """Test external_id defaults to invoice_number."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        assert invoice.external_id == "INV-001"

    def test_date_string_conversion(self):
        """Test date strings are converted to date objects."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date="2026-03-01",  # type: ignore
            due_date="2026-04-01",  # type: ignore
        )
        assert invoice.invoice_date == date(2026, 3, 1)
        assert invoice.due_date == date(2026, 4, 1)

    def test_calculated_total(self):
        """Test calculated_total sums line items."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                InvoiceLineItem(amount=Decimal("100.00")),
                InvoiceLineItem(amount=Decimal("250.50")),
                InvoiceLineItem(amount=Decimal("49.50")),
            ],
        )
        assert invoice.calculated_total == Decimal("400.00")

    def test_is_paid(self):
        """Test is_paid property."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=BillStatus.PAID,
        )
        assert invoice.is_paid is True

    def test_is_overdue(self):
        """Test is_overdue property."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            status=BillStatus.OPEN,
        )
        assert invoice.is_overdue is True

    def test_is_overdue_when_paid(self):
        """Test is_overdue is False when paid."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            status=BillStatus.PAID,
        )
        assert invoice.is_overdue is False

    def test_days_until_due(self):
        """Test days_until_due calculation."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15),
        )
        assert invoice.days_until_due == 15

    def test_days_until_due_overdue(self):
        """Test days_until_due is negative when overdue."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=10),
        )
        assert invoice.days_until_due == -10

    def test_validate_valid_invoice(self):
        """Test validation of valid invoice."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                InvoiceLineItem(amount=Decimal("100.00")),
            ],
        )
        errors = invoice.validate()
        assert len(errors) == 0
        assert invoice.is_valid() is True

    def test_validate_missing_invoice_number(self):
        """Test validation catches missing invoice_number."""
        invoice = Invoice(
            invoice_number="",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = invoice.validate()
        assert "invoice_number is required" in errors

    def test_validate_missing_vendor_id(self):
        """Test validation catches missing vendor_id."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = invoice.validate()
        assert "vendor_id is required" in errors

    def test_validate_no_line_items(self):
        """Test validation catches missing line items."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[],
        )
        errors = invoice.validate()
        assert "At least one line item is required" in errors

    def test_validate_invalid_line_item_amount(self):
        """Test validation catches invalid line item amount."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                InvoiceLineItem(amount=Decimal("-100.00")),
            ],
        )
        errors = invoice.validate()
        assert any("invalid amount" in e for e in errors)

    def test_validate_due_date_before_invoice_date(self):
        """Test validation catches due date before invoice date."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() - timedelta(days=10),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = invoice.validate()
        assert any("cannot be before invoice_date" in e for e in errors)

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 4, 1),
            line_items=[
                InvoiceLineItem(amount=Decimal("500.00"), description="Services"),
            ],
            po_number="PO-123",
        )
        payload = invoice.to_api_payload()
        assert payload["vendorId"] == "vendor-123"
        assert payload["invoice"]["number"] == "INV-001"
        assert payload["invoice"]["date"] == "2026-03-01"
        assert payload["dueDate"] == "2026-04-01"
        assert payload["poNumber"] == "PO-123"
        assert len(payload["billLineItems"]) == 1

    def test_diff_same_invoices(self):
        """Test diff returns empty for identical invoices."""
        inv1 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        inv2 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        diffs = inv1.diff(inv2)
        assert len(diffs) == 0

    def test_diff_different_due_date(self):
        """Test diff detects different due dates."""
        inv1 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        inv2 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=60),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        diffs = inv1.diff(inv2)
        assert "due_date" in diffs

    def test_diff_different_amount(self):
        """Test diff detects different amounts."""
        inv1 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        inv2 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("200.00"))],
        )
        diffs = inv1.diff(inv2)
        assert "total_amount" in diffs

    def test_needs_update_when_updatable(self):
        """Test needs_update with updatable invoice."""
        inv1 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        inv2 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=60),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
            status=BillStatus.OPEN,
        )
        assert inv1.needs_update(inv2) is True

    def test_needs_update_when_paid(self):
        """Test needs_update returns False when existing is paid."""
        inv1 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        inv2 = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=60),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
            status=BillStatus.PAID,
        )
        assert inv1.needs_update(inv2) is False

    def test_from_bill_api(self):
        """Test creation from BILL API response."""
        data = {
            "id": "bill-uuid-123",
            "vendorId": "vendor-456",
            "invoice": {
                "number": "INV-001",
                "date": "2026-03-01",
            },
            "dueDate": "2026-04-01",
            "status": "open",
            "billLineItems": [
                {"amount": 500.0, "description": "Services"},
            ],
            "poNumber": "PO-123",
            "externalId": "EXT-001",
        }
        invoice = Invoice.from_bill_api(data)
        assert invoice.id == "bill-uuid-123"
        assert invoice.invoice_number == "INV-001"
        assert invoice.vendor_id == "vendor-456"
        assert invoice.invoice_date == date(2026, 3, 1)
        assert invoice.due_date == date(2026, 4, 1)
        assert len(invoice.line_items) == 1
        assert invoice.po_number == "PO-123"

    def test_from_csv_row(self):
        """Test creation from CSV row."""
        row = {
            "invoice_number": "INV-001",
            "vendor_id": "vendor-123",
            "invoice_date": "2026-03-01",
            "due_date": "2026-04-01",
            "amount": "1000.00",
            "description": "Consulting services",
            "po_number": "PO-456",
        }
        invoice = Invoice.from_csv_row(row)
        assert invoice.invoice_number == "INV-001"
        assert invoice.vendor_id == "vendor-123"
        assert len(invoice.line_items) == 1
        assert invoice.line_items[0].amount == Decimal("1000.00")

    def test_from_csv_row_with_vendor_mapping(self):
        """Test CSV row with vendor mapping."""
        row = {
            "invoice_number": "INV-001",
            "vendor_id": "external-vendor-1",
            "invoice_date": "2026-03-01",
            "amount": "500.00",
        }
        vendor_mapping = {
            "external-vendor-1": "bill-vendor-uuid",
        }
        invoice = Invoice.from_csv_row(row, vendor_mapping)
        assert invoice.vendor_id == "bill-vendor-uuid"

    def test_from_csv_row_calculated_due_date(self):
        """Test CSV row calculates due date from payment terms."""
        row = {
            "invoice_number": "INV-001",
            "vendor_id": "vendor-123",
            "invoice_date": "2026-03-01",
            "payment_term_days": "45",
            "amount": "500.00",
        }
        invoice = Invoice.from_csv_row(row)
        assert invoice.due_date == date(2026, 4, 15)  # 45 days from March 1
