"""
Unit tests for PaymentService.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock, MagicMock

import pytest

from src.application.services.payment_service import PaymentService
from src.domain.models.payment import Payment, PaymentStatus, PaymentMethod, FundingAccount
from src.domain.models.invoice import Invoice, BillStatus, InvoiceLineItem


@pytest.fixture
def mock_payment_repo():
    """Create mock payment repository."""
    return MagicMock()


@pytest.fixture
def mock_invoice_repo():
    """Create mock invoice repository."""
    return MagicMock()


@pytest.fixture
def payment_service(mock_payment_repo, mock_invoice_repo):
    """Create payment service with mocked dependencies."""
    return PaymentService(
        payment_repository=mock_payment_repo,
        invoice_repository=mock_invoice_repo,
        default_funding_account_id="DEFAULT_ACCOUNT",
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
        status=BillStatus.APPROVED,
        line_items=[
            InvoiceLineItem(description="Service", amount=Decimal("1000.00")),
        ],
        total_amount=Decimal("1000.00"),
    )


@pytest.fixture
def sample_payment():
    """Create sample payment."""
    return Payment(
        id="PAY001",
        bill_id="INV001",
        vendor_id="VND001",
        amount=Decimal("1000.00"),
        status=PaymentStatus.PENDING,
        process_date=date.today(),
    )


class TestCreatePayment:
    """Tests for create_payment method."""

    def test_creates_payment(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should create payment for valid invoice."""
        mock_payment_repo.create.return_value = Payment(
            id="PAY001",
            bill_id="INV001",
            vendor_id="VND001",
            amount=Decimal("1000.00"),
            status=PaymentStatus.PENDING,
            process_date=date.today(),
        )

        result = payment_service.create_payment(sample_invoice)

        assert result.success is True
        assert result.action == "create"
        mock_payment_repo.create.assert_called_once()

    def test_creates_partial_payment(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should create partial payment."""
        mock_payment_repo.create.return_value = Payment(
            id="PAY001",
            bill_id="INV001",
            amount=Decimal("500.00"),
            status=PaymentStatus.PENDING,
            process_date=date.today(),
        )

        result = payment_service.create_payment(sample_invoice, amount=500.00)

        assert result.success is True
        created = mock_payment_repo.create.call_args[0][0]
        assert created.amount == Decimal("500.00")

    def test_error_no_funding_account(
        self,
        mock_payment_repo,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should return error when no funding account available."""
        service = PaymentService(
            payment_repository=mock_payment_repo,
            invoice_repository=mock_invoice_repo,
            default_funding_account_id=None,
        )

        result = service.create_payment(sample_invoice)

        assert result.success is False
        assert "funding account" in result.message.lower()

    def test_error_already_paid(
        self,
        payment_service,
        sample_invoice,
    ):
        """Should return error for already paid invoice."""
        sample_invoice.status = BillStatus.PAID

        result = payment_service.create_payment(sample_invoice)

        assert result.success is False
        assert "paid" in result.message.lower()

    def test_error_voided_invoice(
        self,
        payment_service,
        sample_invoice,
    ):
        """Should return error for voided invoice."""
        sample_invoice.status = BillStatus.VOIDED

        result = payment_service.create_payment(sample_invoice)

        assert result.success is False

    def test_error_negative_amount(
        self,
        payment_service,
        sample_invoice,
    ):
        """Should return error for negative amount."""
        result = payment_service.create_payment(sample_invoice, amount=-100.00)

        assert result.success is False
        assert "positive" in result.message.lower()

    def test_error_amount_exceeds_total(
        self,
        payment_service,
        sample_invoice,
    ):
        """Should return error when amount exceeds invoice total."""
        result = payment_service.create_payment(sample_invoice, amount=5000.00)

        assert result.success is False
        assert "exceed" in result.message.lower()

    def test_updates_invoice_status(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
        sample_invoice,
    ):
        """Should update invoice status after payment."""
        mock_payment_repo.create.return_value = Payment(
            id="PAY001",
            bill_id="INV001",
            amount=Decimal("1000.00"),
            status=PaymentStatus.PENDING,
            process_date=date.today(),
        )
        mock_invoice_repo.get_by_id.return_value = sample_invoice

        payment_service.create_payment(sample_invoice)

        mock_invoice_repo.update.assert_called()


class TestCreateBulkPayments:
    """Tests for create_bulk_payments method."""

    def test_empty_list(self, payment_service):
        """Should handle empty invoice list."""
        result = payment_service.create_bulk_payments([])

        assert result.total == 0
        assert result.created == 0

    def test_creates_multiple_payments(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
    ):
        """Should create payments for multiple invoices."""
        invoices = [
            Invoice(
                id=f"INV{i}",
                invoice_number=f"INV-{i}",
                vendor_id="VND001",
                invoice_date=date(2024, 3, 1),
                due_date=date(2024, 4, 1),
                status=BillStatus.APPROVED,
                line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
                total_amount=Decimal("100.00"),
            )
            for i in range(3)
        ]

        mock_payment_repo.create_bulk.return_value = [
            Payment(
                id=f"PAY{i}",
                bill_id=f"INV{i}",
                amount=Decimal("100.00"),
                status=PaymentStatus.PENDING,
                process_date=date.today(),
            )
            for i in range(3)
        ]

        result = payment_service.create_bulk_payments(invoices)

        assert result.total == 3
        assert result.created == 3

    def test_falls_back_to_individual(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
    ):
        """Should fall back to individual payments if bulk not supported."""
        invoices = [
            Invoice(
                id="INV0",
                invoice_number="INV-0",
                vendor_id="VND001",
                invoice_date=date(2024, 3, 1),
                due_date=date(2024, 4, 1),
                status=BillStatus.APPROVED,
                line_items=[InvoiceLineItem(description="Svc", amount=Decimal("100.00"))],
                total_amount=Decimal("100.00"),
            )
        ]

        mock_payment_repo.create_bulk.side_effect = NotImplementedError()
        mock_payment_repo.create.return_value = Payment(
            id="PAY0",
            bill_id="INV0",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
            process_date=date.today(),
        )

        result = payment_service.create_bulk_payments(invoices)

        assert result.created == 1
        mock_payment_repo.create.assert_called()


class TestRecordExternalPayment:
    """Tests for record_external_payment method."""

    def test_records_payment(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
    ):
        """Should record external payment."""
        mock_payment_repo.record_external.return_value = Payment(
            id="EXT001",
            bill_id="INV001",
            amount=Decimal("1000.00"),
            status=PaymentStatus.COMPLETED,
            process_date=date(2024, 3, 15),
        )

        result = payment_service.record_external_payment(
            bill_id="INV001",
            amount=1000.00,
            payment_date="2024-03-15",
            reference="CHECK-123",
        )

        assert result.success is True
        assert result.action == "create"
        mock_payment_repo.record_external.assert_called_once()

    def test_error_negative_amount(self, payment_service):
        """Should return error for negative amount."""
        result = payment_service.record_external_payment(
            bill_id="INV001",
            amount=-100.00,
            payment_date="2024-03-15",
        )

        assert result.success is False
        assert "positive" in result.message.lower()

    def test_error_invalid_date_format(self, payment_service):
        """Should return error for invalid date format."""
        result = payment_service.record_external_payment(
            bill_id="INV001",
            amount=1000.00,
            payment_date="03/15/2024",  # Wrong format
        )

        assert result.success is False
        assert "date" in result.message.lower()


class TestGetPaymentStatus:
    """Tests for get_payment_status method."""

    def test_returns_payment(
        self,
        payment_service,
        mock_payment_repo,
        sample_payment,
    ):
        """Should return payment by ID."""
        mock_payment_repo.get_by_id.return_value = sample_payment

        result = payment_service.get_payment_status("PAY001")

        assert result == sample_payment
        mock_payment_repo.get_by_id.assert_called_with("PAY001")

    def test_error_not_found(self, payment_service, mock_payment_repo):
        """Should raise error when payment not found."""
        mock_payment_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            payment_service.get_payment_status("NOTFOUND")


class TestCancelPayment:
    """Tests for cancel_payment method."""

    def test_cancels_pending_payment(
        self,
        payment_service,
        mock_payment_repo,
        mock_invoice_repo,
        sample_payment,
    ):
        """Should cancel pending payment."""
        sample_payment.bill_id = "INV001"
        mock_payment_repo.get_by_id.return_value = sample_payment
        mock_payment_repo.update.return_value = sample_payment

        result = payment_service.cancel_payment("PAY001", "Customer request")

        assert result.success is True
        updated = mock_payment_repo.update.call_args[0][0]
        assert updated.status == PaymentStatus.CANCELLED

    def test_cannot_cancel_completed(
        self,
        payment_service,
        mock_payment_repo,
        sample_payment,
    ):
        """Should not cancel completed payment."""
        sample_payment.status = PaymentStatus.COMPLETED
        mock_payment_repo.get_by_id.return_value = sample_payment

        result = payment_service.cancel_payment("PAY001")

        assert result.success is False
        assert "status" in result.message.lower()

    def test_error_not_found(self, payment_service, mock_payment_repo):
        """Should return error when payment not found."""
        mock_payment_repo.get_by_id.return_value = None

        result = payment_service.cancel_payment("NOTFOUND")

        assert result.success is False
        assert "not found" in result.message.lower()


class TestGetPendingPayments:
    """Tests for get_pending_payments method."""

    def test_returns_pending_payments(
        self,
        payment_service,
        mock_payment_repo,
        sample_payment,
    ):
        """Should return pending payments."""
        mock_payment_repo.list.return_value = [sample_payment]

        result = payment_service.get_pending_payments()

        assert len(result) == 1
        assert result[0].status == PaymentStatus.PENDING
