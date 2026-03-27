"""
Unit tests for BILL.com Accounts Payable repositories.
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

from src.infrastructure.adapters.bill.accounts_payable import (
    VendorRepositoryImpl,
    InvoiceRepositoryImpl,
    PaymentRepositoryImpl,
)


# ====================
# VendorRepositoryImpl Tests
# ====================

class TestVendorRepositoryInit:
    """Tests for VendorRepositoryImpl initialization."""

    def test_init_with_client(self):
        """Test initialization with client."""
        mock_client = MagicMock()
        repo = VendorRepositoryImpl(mock_client)

        assert repo._client is mock_client
        assert repo._name_cache == {}
        assert repo._external_id_cache == {}


class TestVendorGetById:
    """Tests for vendor get_by_id method."""

    def test_returns_vendor_when_found(self):
        """Test returns vendor when found by ID."""
        mock_client = MagicMock()
        mock_client.get_vendor.return_value = {
            "id": "vendor-123",
            "name": "ACME Corp",
            "email": "acme@example.com",
        }

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_id("vendor-123")

        assert result is not None
        assert result.id == "vendor-123"

    def test_returns_none_when_not_found(self):
        """Test returns None when vendor not found."""
        mock_client = MagicMock()
        mock_client.get_vendor.return_value = None

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_id("unknown-id")

        assert result is None

    def test_returns_none_on_exception(self):
        """Test returns None on exception."""
        mock_client = MagicMock()
        mock_client.get_vendor.side_effect = Exception("API error")

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_id("error-id")

        assert result is None


class TestVendorGetByName:
    """Tests for vendor get_by_name method."""

    def test_returns_vendor_when_found(self):
        """Test returns vendor when found by name."""
        mock_client = MagicMock()
        mock_client.get_vendor_by_name.return_value = {
            "id": "vendor-123",
            "name": "ACME Corp",
        }

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_name("ACME Corp")

        assert result is not None
        assert result.name == "ACME Corp"

    def test_uses_cache_on_second_call(self):
        """Test uses cache on second call."""
        mock_client = MagicMock()
        mock_client.get_vendor_by_name.return_value = {
            "id": "vendor-123",
            "name": "ACME Corp",
        }
        mock_client.get_vendor.return_value = {
            "id": "vendor-123",
            "name": "ACME Corp",
        }

        repo = VendorRepositoryImpl(mock_client)
        repo.get_by_name("ACME Corp")
        repo.get_by_name("acme corp")  # Case insensitive

        assert mock_client.get_vendor_by_name.call_count == 1


class TestVendorGetByExternalId:
    """Tests for vendor get_by_external_id method."""

    def test_returns_vendor_when_found(self):
        """Test returns vendor when found by external ID."""
        mock_client = MagicMock()
        mock_client.get_vendor_by_external_id.return_value = {
            "id": "vendor-123",
            "externalId": "EXT-001",
        }

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_external_id("EXT-001")

        assert result is not None

    def test_returns_none_when_not_found(self):
        """Test returns None when not found."""
        mock_client = MagicMock()
        mock_client.get_vendor_by_external_id.return_value = None

        repo = VendorRepositoryImpl(mock_client)
        result = repo.get_by_external_id("UNKNOWN")

        assert result is None


class TestVendorSearch:
    """Tests for vendor search method."""

    def test_searches_by_name(self):
        """Test searches vendors by name."""
        mock_client = MagicMock()
        mock_client.list_vendors.return_value = [
            {"id": "1", "name": "ACME Corp"},
            {"id": "2", "name": "Beta Inc"},
            {"id": "3", "name": "ACME Solutions"},
        ]

        repo = VendorRepositoryImpl(mock_client)
        results = repo.search("ACME")

        assert len(results) == 2


class TestVendorGetActiveVendors:
    """Tests for get_active_vendors method."""

    def test_returns_active_vendors(self):
        """Test returns active vendors."""
        mock_client = MagicMock()
        mock_client.get_all_vendors.return_value = [
            {"id": "1", "name": "Vendor 1"},
            {"id": "2", "name": "Vendor 2"},
        ]

        repo = VendorRepositoryImpl(mock_client)
        results = repo.get_active_vendors()

        assert len(results) == 2
        mock_client.get_all_vendors.assert_called_once_with(status="active")


class TestVendorList:
    """Tests for vendor list method."""

    def test_lists_vendors_with_pagination(self):
        """Test lists vendors with pagination."""
        mock_client = MagicMock()
        mock_client.list_vendors.return_value = [
            {"id": "1", "name": "Vendor 1"},
        ]

        repo = VendorRepositoryImpl(mock_client)
        results = repo.list(page=2, page_size=50)

        mock_client.list_vendors.assert_called_once_with(
            page=2, page_size=50, status=None
        )


class TestVendorCreate:
    """Tests for vendor create method."""

    def test_creates_vendor(self):
        """Test creates new vendor."""
        mock_client = MagicMock()
        mock_client.create_vendor.return_value = {
            "id": "new-vendor",
            "name": "New Vendor",
        }

        repo = VendorRepositoryImpl(mock_client)

        from src.domain.models.vendor import Vendor
        vendor = Vendor(name="New Vendor")
        result = repo.create(vendor)

        assert result.id == "new-vendor"


class TestVendorUpdate:
    """Tests for vendor update method."""

    def test_updates_vendor(self):
        """Test updates existing vendor."""
        mock_client = MagicMock()
        mock_client.update_vendor.return_value = {
            "id": "vendor-123",
            "name": "Updated Vendor",
        }

        repo = VendorRepositoryImpl(mock_client)

        from src.domain.models.vendor import Vendor
        vendor = Vendor(id="vendor-123", name="Updated Vendor")
        result = repo.update(vendor)

        assert result.id == "vendor-123"

    def test_raises_without_id(self):
        """Test raises ValueError without ID."""
        mock_client = MagicMock()
        repo = VendorRepositoryImpl(mock_client)

        from src.domain.models.vendor import Vendor
        vendor = Vendor(name="No ID Vendor")

        with pytest.raises(ValueError) as exc_info:
            repo.update(vendor)

        assert "without ID" in str(exc_info.value)


class TestVendorDelete:
    """Tests for vendor delete method."""

    def test_raises_not_implemented(self):
        """Test raises NotImplementedError."""
        mock_client = MagicMock()
        repo = VendorRepositoryImpl(mock_client)

        with pytest.raises(NotImplementedError) as exc_info:
            repo.delete("vendor-123")

        assert "Use archive instead" in str(exc_info.value)


class TestVendorUpsert:
    """Tests for vendor upsert method."""

    def test_creates_new_vendor(self):
        """Test creates new vendor when not found."""
        mock_client = MagicMock()
        mock_client.get_vendor_by_external_id.return_value = None
        mock_client.get_vendor_by_name.return_value = None
        mock_client.create_vendor.return_value = {
            "id": "new-vendor",
            "name": "New Vendor",
        }

        repo = VendorRepositoryImpl(mock_client)

        from src.domain.models.vendor import Vendor
        vendor = Vendor(name="New Vendor", external_id="EXT-001")
        result = repo.upsert(vendor)

        mock_client.create_vendor.assert_called_once()


class TestVendorClearCache:
    """Tests for vendor clear_cache method."""

    def test_clears_all_caches(self):
        """Test clears all caches."""
        mock_client = MagicMock()
        repo = VendorRepositoryImpl(mock_client)

        repo._name_cache["vendor"] = "id-1"
        repo._external_id_cache["ext-1"] = "id-1"

        repo.clear_cache()

        assert len(repo._name_cache) == 0
        assert len(repo._external_id_cache) == 0


# ====================
# InvoiceRepositoryImpl Tests
# ====================

class TestInvoiceRepositoryInit:
    """Tests for InvoiceRepositoryImpl initialization."""

    def test_init_with_client(self):
        """Test initialization with client."""
        mock_client = MagicMock()
        repo = InvoiceRepositoryImpl(mock_client)

        assert repo._client is mock_client
        assert repo._invoice_cache == {}
        assert repo._external_id_cache == {}


class TestInvoiceGetById:
    """Tests for invoice get_by_id method."""

    def test_returns_invoice_when_found(self):
        """Test returns invoice when found by ID."""
        mock_client = MagicMock()
        mock_client.get_bill.return_value = {
            "id": "bill-123",
            "invoiceNumber": "INV-001",
            "amount": "100.00",
        }

        repo = InvoiceRepositoryImpl(mock_client)
        result = repo.get_by_id("bill-123")

        assert result is not None
        assert result.id == "bill-123"

    def test_returns_none_when_not_found(self):
        """Test returns None when invoice not found."""
        mock_client = MagicMock()
        mock_client.get_bill.return_value = None

        repo = InvoiceRepositoryImpl(mock_client)
        result = repo.get_by_id("unknown-id")

        assert result is None


class TestInvoiceGetByInvoiceNumber:
    """Tests for get_by_invoice_number method."""

    def test_returns_invoice_when_found(self):
        """Test returns invoice when found by number."""
        mock_client = MagicMock()
        mock_client.get_bill_by_invoice_number.return_value = {
            "id": "bill-123",
            "invoiceNumber": "INV-001",
        }

        repo = InvoiceRepositoryImpl(mock_client)
        result = repo.get_by_invoice_number("INV-001")

        assert result is not None

    def test_uses_cache_on_second_call(self):
        """Test uses cache on second call."""
        mock_client = MagicMock()
        mock_client.get_bill_by_invoice_number.return_value = {
            "id": "bill-123",
            "invoiceNumber": "INV-001",
        }
        mock_client.get_bill.return_value = {
            "id": "bill-123",
            "invoiceNumber": "INV-001",
        }

        repo = InvoiceRepositoryImpl(mock_client)
        repo.get_by_invoice_number("INV-001", "vendor-123")
        repo.get_by_invoice_number("INV-001", "vendor-123")

        assert mock_client.get_bill_by_invoice_number.call_count == 1


class TestInvoiceGetByExternalId:
    """Tests for invoice get_by_external_id method."""

    def test_returns_invoice_when_found(self):
        """Test returns invoice when found by external ID."""
        mock_client = MagicMock()
        mock_client.get_bill_by_external_id.return_value = {
            "id": "bill-123",
            "externalId": "EXT-001",
        }

        repo = InvoiceRepositoryImpl(mock_client)
        result = repo.get_by_external_id("EXT-001")

        assert result is not None


class TestInvoiceGetInvoicesForVendor:
    """Tests for get_invoices_for_vendor method."""

    def test_returns_vendor_invoices(self):
        """Test returns invoices for vendor."""
        mock_client = MagicMock()
        mock_client.get_bills_for_vendor.return_value = [
            {"id": "1", "invoiceNumber": "INV-001"},
            {"id": "2", "invoiceNumber": "INV-002"},
        ]

        repo = InvoiceRepositoryImpl(mock_client)
        results = repo.get_invoices_for_vendor("vendor-123")

        assert len(results) == 2


class TestInvoiceList:
    """Tests for invoice list method."""

    def test_lists_invoices_with_pagination(self):
        """Test lists invoices with pagination."""
        mock_client = MagicMock()
        mock_client.list_bills.return_value = [
            {"id": "1", "invoiceNumber": "INV-001"},
        ]

        repo = InvoiceRepositoryImpl(mock_client)
        results = repo.list(page=2, page_size=50)

        mock_client.list_bills.assert_called_once()


class TestInvoiceCreate:
    """Tests for invoice create method."""

    def test_creates_invoice(self):
        """Test creates new invoice."""
        mock_client = MagicMock()
        mock_client.create_bill.return_value = {
            "id": "new-bill",
            "invoiceNumber": "INV-001",
            "vendorId": "vendor-123",
        }

        repo = InvoiceRepositoryImpl(mock_client)

        from src.domain.models.invoice import Invoice
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today(),
        )
        result = repo.create(invoice)

        assert result.id == "new-bill"


class TestInvoiceUpdate:
    """Tests for invoice update method."""

    def test_raises_without_id(self):
        """Test raises ValueError without ID."""
        mock_client = MagicMock()
        repo = InvoiceRepositoryImpl(mock_client)

        from src.domain.models.invoice import Invoice
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="vendor-123",
            invoice_date=date.today(),
            due_date=date.today(),
        )

        with pytest.raises(ValueError) as exc_info:
            repo.update(invoice)

        assert "without ID" in str(exc_info.value)


class TestInvoiceDelete:
    """Tests for invoice delete method."""

    def test_raises_not_implemented(self):
        """Test raises NotImplementedError."""
        mock_client = MagicMock()
        repo = InvoiceRepositoryImpl(mock_client)

        with pytest.raises(NotImplementedError) as exc_info:
            repo.delete("bill-123")

        assert "Use void instead" in str(exc_info.value)


class TestInvoiceClearCache:
    """Tests for invoice clear_cache method."""

    def test_clears_all_caches(self):
        """Test clears all caches."""
        mock_client = MagicMock()
        repo = InvoiceRepositoryImpl(mock_client)

        repo._invoice_cache["inv:vendor"] = "id-1"
        repo._external_id_cache["ext-1"] = "id-1"

        repo.clear_cache()

        assert len(repo._invoice_cache) == 0
        assert len(repo._external_id_cache) == 0


# ====================
# PaymentRepositoryImpl Tests
# ====================

class TestPaymentRepositoryInit:
    """Tests for PaymentRepositoryImpl initialization."""

    def test_init_with_client(self):
        """Test initialization with client."""
        mock_client = MagicMock()
        repo = PaymentRepositoryImpl(mock_client)

        assert repo._client is mock_client


class TestPaymentGetById:
    """Tests for payment get_by_id method."""

    def test_returns_payment_when_found(self):
        """Test returns payment when found by ID."""
        mock_client = MagicMock()
        mock_client.get_payment.return_value = {
            "id": "payment-123",
            "amount": "100.00",
            "billId": "bill-123",
        }

        repo = PaymentRepositoryImpl(mock_client)
        result = repo.get_by_id("payment-123")

        assert result is not None
        assert result.id == "payment-123"

    def test_returns_none_when_not_found(self):
        """Test returns None when payment not found."""
        mock_client = MagicMock()
        mock_client.get_payment.return_value = None

        repo = PaymentRepositoryImpl(mock_client)
        result = repo.get_by_id("unknown-id")

        assert result is None


class TestPaymentGetPaymentsForBill:
    """Tests for get_payments_for_bill method."""

    def test_returns_bill_payments(self):
        """Test returns payments for bill."""
        mock_client = MagicMock()
        mock_client.get_payments_for_bill.return_value = [
            {"id": "1", "amount": "50.00"},
            {"id": "2", "amount": "50.00"},
        ]

        repo = PaymentRepositoryImpl(mock_client)
        results = repo.get_payments_for_bill("bill-123")

        assert len(results) == 2


class TestPaymentGetPaymentsByStatus:
    """Tests for get_payments_by_status method."""

    def test_returns_payments_by_status(self):
        """Test returns payments by status."""
        mock_client = MagicMock()
        mock_client.list_payments.return_value = [
            {"id": "1", "status": "PENDING"},
        ]

        repo = PaymentRepositoryImpl(mock_client)
        results = repo.get_payments_by_status("PENDING")

        mock_client.list_payments.assert_called_once_with(
            status="PENDING", page=1, page_size=200
        )


class TestPaymentGetPaymentOptions:
    """Tests for get_payment_options method."""

    def test_returns_payment_options(self):
        """Test returns payment options for bill."""
        mock_client = MagicMock()
        mock_client.get_payment_options.return_value = {
            "paymentMethods": ["ACH", "CHECK"],
        }

        repo = PaymentRepositoryImpl(mock_client)
        result = repo.get_payment_options("bill-123")

        assert "paymentMethods" in result


class TestPaymentList:
    """Tests for payment list method."""

    def test_lists_payments_with_pagination(self):
        """Test lists payments with pagination."""
        mock_client = MagicMock()
        mock_client.list_payments.return_value = [
            {"id": "1", "amount": "100.00"},
        ]

        repo = PaymentRepositoryImpl(mock_client)
        results = repo.list(page=2, page_size=50)

        mock_client.list_payments.assert_called_once()


class TestPaymentCreate:
    """Tests for payment create method."""

    def test_creates_payment(self):
        """Test creates new payment."""
        mock_client = MagicMock()
        mock_client.create_payment.return_value = {
            "id": "new-payment",
            "amount": "100.00",
            "billId": "bill-123",
        }

        repo = PaymentRepositoryImpl(mock_client)

        from src.domain.models.payment import Payment
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
        )
        result = repo.create(payment)

        assert result.id == "new-payment"


class TestPaymentCreateBulk:
    """Tests for create_bulk method."""

    def test_creates_bulk_payments(self):
        """Test creates multiple payments."""
        mock_client = MagicMock()
        mock_client.create_bulk_payments.return_value = {
            "results": [
                {"id": "payment-1"},
                {"id": "payment-2"},
            ]
        }

        repo = PaymentRepositoryImpl(mock_client)

        from src.domain.models.payment import Payment
        payments = [
            Payment(bill_id="bill-1", amount=Decimal("50.00"), process_date=date.today()),
            Payment(bill_id="bill-2", amount=Decimal("50.00"), process_date=date.today()),
        ]
        results = repo.create_bulk(payments)

        assert len(results) == 2

    def test_returns_empty_for_empty_list(self):
        """Test returns empty list for empty input."""
        mock_client = MagicMock()
        repo = PaymentRepositoryImpl(mock_client)

        results = repo.create_bulk([])

        assert results == []
        mock_client.create_bulk_payments.assert_not_called()


class TestPaymentRecordExternalPayment:
    """Tests for record_external_payment method."""

    def test_records_external_payment(self):
        """Test records external payment."""
        mock_client = MagicMock()
        mock_client.record_external_payment.return_value = {
            "id": "ext-payment-123",
        }

        repo = PaymentRepositoryImpl(mock_client)

        from src.domain.models.payment import ExternalPayment
        ext_payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            payment_date=date.today(),
            reference="CHK-001",
        )
        result = repo.record_external_payment(ext_payment)

        mock_client.record_external_payment.assert_called_once()

    def test_handles_no_id_response(self):
        """Test handles response without ID."""
        mock_client = MagicMock()
        mock_client.record_external_payment.return_value = {}

        repo = PaymentRepositoryImpl(mock_client)

        from src.domain.models.payment import ExternalPayment
        ext_payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            payment_date=date.today(),
        )
        result = repo.record_external_payment(ext_payment)

        assert result.bill_id == "bill-123"


class TestPaymentCancelPayment:
    """Tests for cancel_payment method."""

    def test_returns_false_for_unknown_payment(self):
        """Test returns False for unknown payment."""
        mock_client = MagicMock()
        mock_client.get_payment.return_value = None

        repo = PaymentRepositoryImpl(mock_client)
        result = repo.cancel_payment("unknown-id")

        assert result is False


class TestPaymentUpdate:
    """Tests for payment update method."""

    def test_raises_not_implemented(self):
        """Test raises NotImplementedError."""
        mock_client = MagicMock()
        repo = PaymentRepositoryImpl(mock_client)

        with pytest.raises(NotImplementedError):
            repo.update(MagicMock())


class TestPaymentDelete:
    """Tests for payment delete method."""

    def test_raises_not_implemented(self):
        """Test raises NotImplementedError."""
        mock_client = MagicMock()
        repo = PaymentRepositoryImpl(mock_client)

        with pytest.raises(NotImplementedError):
            repo.delete("payment-123")
