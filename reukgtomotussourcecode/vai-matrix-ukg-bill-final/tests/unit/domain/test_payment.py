"""
Unit tests for Payment domain model.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.domain.models.payment import (
    BulkPaymentRequest,
    ExternalPayment,
    FundingAccount,
    FundingAccountType,
    Payment,
    PaymentMethod,
    PaymentStatus,
)


class TestPaymentStatus:
    """Tests for PaymentStatus enum."""

    def test_from_string_valid_statuses(self):
        """Test converting valid status strings."""
        assert PaymentStatus.from_string("PENDING") == PaymentStatus.PENDING
        assert PaymentStatus.from_string("pending") == PaymentStatus.PENDING
        assert PaymentStatus.from_string("COMPLETED") == PaymentStatus.COMPLETED
        assert PaymentStatus.from_string("FAILED") == PaymentStatus.FAILED

    def test_from_string_invalid_defaults_to_pending(self):
        """Test invalid status defaults to PENDING."""
        assert PaymentStatus.from_string("INVALID") == PaymentStatus.PENDING
        assert PaymentStatus.from_string("") == PaymentStatus.PENDING

    def test_is_final(self):
        """Test is_final property."""
        assert PaymentStatus.COMPLETED.is_final is True
        assert PaymentStatus.FAILED.is_final is True
        assert PaymentStatus.CANCELLED.is_final is True
        assert PaymentStatus.VOIDED.is_final is True
        assert PaymentStatus.PENDING.is_final is False
        assert PaymentStatus.PROCESSING.is_final is False

    def test_is_success(self):
        """Test is_success property."""
        assert PaymentStatus.COMPLETED.is_success is True
        assert PaymentStatus.FAILED.is_success is False
        assert PaymentStatus.PENDING.is_success is False

    def test_is_pending(self):
        """Test is_pending property."""
        assert PaymentStatus.PENDING.is_pending is True
        assert PaymentStatus.APPROVED.is_pending is True
        assert PaymentStatus.SCHEDULED.is_pending is True
        assert PaymentStatus.PROCESSING.is_pending is True
        assert PaymentStatus.COMPLETED.is_pending is False
        assert PaymentStatus.FAILED.is_pending is False

    def test_description(self):
        """Test description property."""
        assert "completed" in PaymentStatus.COMPLETED.description.lower()
        assert "failed" in PaymentStatus.FAILED.description.lower()


class TestPaymentMethod:
    """Tests for PaymentMethod enum."""

    def test_from_string_valid_methods(self):
        """Test converting valid method strings."""
        assert PaymentMethod.from_string("CHECK") == PaymentMethod.CHECK
        assert PaymentMethod.from_string("ACH") == PaymentMethod.ACH
        assert PaymentMethod.from_string("ach") == PaymentMethod.ACH
        assert PaymentMethod.from_string("WIRE") == PaymentMethod.WIRE

    def test_from_string_invalid_defaults_to_ach(self):
        """Test invalid method defaults to ACH."""
        assert PaymentMethod.from_string("INVALID") == PaymentMethod.ACH
        assert PaymentMethod.from_string("") == PaymentMethod.ACH


class TestFundingAccount:
    """Tests for FundingAccount dataclass."""

    def test_basic_creation(self):
        """Test basic funding account creation."""
        account = FundingAccount(
            id="account-123",
            account_type=FundingAccountType.BANK_ACCOUNT,
            name="Business Checking",
            last_four="1234",
        )
        assert account.id == "account-123"
        assert account.account_type == FundingAccountType.BANK_ACCOUNT
        assert account.name == "Business Checking"

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        account = FundingAccount(
            id="account-123",
            account_type=FundingAccountType.BANK_ACCOUNT,
        )
        payload = account.to_api_payload()
        assert payload == {
            "type": "BANK_ACCOUNT",
            "id": "account-123",
        }

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "account-456",
            "type": "BANK_ACCOUNT",
            "name": "Savings",
            "lastFour": "5678",
        }
        account = FundingAccount.from_dict(data)
        assert account.id == "account-456"
        assert account.account_type == FundingAccountType.BANK_ACCOUNT
        assert account.name == "Savings"
        assert account.last_four == "5678"


class TestPayment:
    """Tests for Payment domain model."""

    def test_basic_creation(self):
        """Test basic payment creation."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("1000.00"),
            process_date=date.today(),
            funding_account=FundingAccount(id="account-123"),
        )
        assert payment.bill_id == "bill-123"
        assert payment.amount == Decimal("1000.00")
        assert payment.status == PaymentStatus.PENDING

    def test_amount_conversion_from_float(self):
        """Test amount is converted from float to Decimal."""
        payment = Payment(
            bill_id="bill-123",
            amount=500.50,  # type: ignore
            process_date=date.today(),
        )
        assert payment.amount == Decimal("500.5")

    def test_date_string_conversion(self):
        """Test date string is converted to date object."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date="2026-03-15",  # type: ignore
        )
        assert payment.process_date == date(2026, 3, 15)

    def test_is_completed(self):
        """Test is_completed property."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            status=PaymentStatus.COMPLETED,
        )
        assert payment.is_completed is True

    def test_is_pending(self):
        """Test is_pending property."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            status=PaymentStatus.PENDING,
        )
        assert payment.is_pending is True

    def test_is_failed(self):
        """Test is_failed property."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            status=PaymentStatus.FAILED,
        )
        assert payment.is_failed is True

    def test_is_cancellable(self):
        """Test is_cancellable property."""
        pending = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            status=PaymentStatus.PENDING,
        )
        completed = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            status=PaymentStatus.COMPLETED,
        )
        assert pending.is_cancellable is True
        assert completed.is_cancellable is False

    def test_validate_valid_payment(self):
        """Test validation of valid payment."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            funding_account=FundingAccount(id="account-123"),
        )
        errors = payment.validate()
        assert len(errors) == 0
        assert payment.is_valid() is True

    def test_validate_missing_bill_id(self):
        """Test validation catches missing bill_id."""
        payment = Payment(
            bill_id="",
            amount=Decimal("100.00"),
            process_date=date.today(),
            funding_account=FundingAccount(id="account-123"),
        )
        errors = payment.validate()
        assert "bill_id is required" in errors

    def test_validate_invalid_amount(self):
        """Test validation catches invalid amount."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("-100.00"),
            process_date=date.today(),
            funding_account=FundingAccount(id="account-123"),
        )
        errors = payment.validate()
        assert any("must be positive" in e for e in errors)

    def test_validate_past_process_date(self):
        """Test validation catches past process date."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today() - timedelta(days=10),
            funding_account=FundingAccount(id="account-123"),
        )
        errors = payment.validate()
        assert any("cannot be in the past" in e for e in errors)

    def test_validate_missing_funding_account(self):
        """Test validation catches missing funding account."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            process_date=date.today(),
            funding_account=None,
        )
        errors = payment.validate()
        assert "funding_account is required" in errors

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("500.00"),
            process_date=date(2026, 3, 15),
            funding_account=FundingAccount(id="account-123"),
            payment_method=PaymentMethod.ACH,
        )
        payload = payment.to_api_payload()
        assert payload["billId"] == "bill-123"
        assert payload["amount"] == 500.0
        assert payload["processDate"] == "2026-03-15"
        assert payload["fundingAccount"]["id"] == "account-123"
        assert payload["paymentMethod"] == "ACH"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        payment = Payment(
            bill_id="bill-123",
            amount=Decimal("500.00"),
            process_date=date.today(),
            id="payment-456",
            status=PaymentStatus.COMPLETED,
            vendor_name="Acme Corp",
        )
        result = payment.to_dict()
        assert result["id"] == "payment-456"
        assert result["bill_id"] == "bill-123"
        assert result["amount"] == 500.0
        assert result["is_completed"] is True
        assert result["vendor_name"] == "Acme Corp"

    def test_from_bill_api(self):
        """Test creation from BILL API response."""
        data = {
            "id": "payment-uuid-123",
            "billId": "bill-456",
            "amount": 1000.0,
            "processDate": "2026-03-15",
            "status": "COMPLETED",
            "paymentMethod": "ACH",
            "vendorId": "vendor-789",
            "vendorName": "Test Vendor",
            "checkNumber": "1234",
            "fundingAccount": {
                "id": "account-111",
                "type": "BANK_ACCOUNT",
            },
        }
        payment = Payment.from_bill_api(data)
        assert payment.id == "payment-uuid-123"
        assert payment.bill_id == "bill-456"
        assert payment.amount == Decimal("1000")
        assert payment.status == PaymentStatus.COMPLETED
        assert payment.payment_method == PaymentMethod.ACH
        assert payment.vendor_name == "Test Vendor"
        assert payment.funding_account.id == "account-111"


class TestExternalPayment:
    """Tests for ExternalPayment dataclass."""

    def test_basic_creation(self):
        """Test basic external payment creation."""
        payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("500.00"),
            payment_date=date(2026, 3, 15),
            reference="CHECK-1234",
        )
        assert payment.bill_id == "bill-123"
        assert payment.amount == Decimal("500.00")
        assert payment.reference == "CHECK-1234"

    def test_amount_conversion(self):
        """Test amount conversion from float."""
        payment = ExternalPayment(
            bill_id="bill-123",
            amount=250.75,  # type: ignore
            payment_date=date.today(),
        )
        assert payment.amount == Decimal("250.75")

    def test_date_string_conversion(self):
        """Test date string conversion."""
        payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            payment_date="2026-03-15",  # type: ignore
        )
        assert payment.payment_date == date(2026, 3, 15)

    def test_validate_valid(self):
        """Test validation of valid external payment."""
        payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("100.00"),
            payment_date=date.today(),
        )
        errors = payment.validate()
        assert len(errors) == 0

    def test_validate_missing_bill_id(self):
        """Test validation catches missing bill_id."""
        payment = ExternalPayment(
            bill_id="",
            amount=Decimal("100.00"),
            payment_date=date.today(),
        )
        errors = payment.validate()
        assert "bill_id is required" in errors

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        payment = ExternalPayment(
            bill_id="bill-123",
            amount=Decimal("500.00"),
            payment_date=date(2026, 3, 15),
            reference="CHECK-1234",
        )
        payload = payment.to_api_payload()
        assert payload["billId"] == "bill-123"
        assert payload["amount"] == 500.0
        assert payload["paymentDate"] == "2026-03-15"
        assert payload["reference"] == "CHECK-1234"


class TestBulkPaymentRequest:
    """Tests for BulkPaymentRequest dataclass."""

    def test_basic_creation(self):
        """Test basic bulk payment request creation."""
        payments = [
            Payment(
                bill_id="bill-1",
                amount=Decimal("100.00"),
                process_date=date.today(),
                funding_account=FundingAccount(id="account-1"),
            ),
            Payment(
                bill_id="bill-2",
                amount=Decimal("200.00"),
                process_date=date.today(),
                funding_account=FundingAccount(id="account-1"),
            ),
        ]
        bulk = BulkPaymentRequest(payments=payments)
        assert bulk.payment_count == 2
        assert bulk.total_amount == Decimal("300.00")

    def test_validate_empty_payments(self):
        """Test validation catches empty payments."""
        bulk = BulkPaymentRequest(payments=[])
        errors = bulk.validate()
        assert "At least one payment is required" in errors

    def test_validate_with_invalid_payment(self):
        """Test validation catches invalid payments."""
        payments = [
            Payment(
                bill_id="bill-1",
                amount=Decimal("100.00"),
                process_date=date.today(),
                funding_account=FundingAccount(id="account-1"),
            ),
            Payment(
                bill_id="",  # Invalid - missing bill_id
                amount=Decimal("200.00"),
                process_date=date.today(),
                funding_account=FundingAccount(id="account-1"),
            ),
        ]
        bulk = BulkPaymentRequest(payments=payments)
        errors = bulk.validate()
        assert any("Payment 1: bill_id is required" in e for e in errors)

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        payments = [
            Payment(
                bill_id="bill-1",
                amount=Decimal("100.00"),
                process_date=date(2026, 3, 15),
                funding_account=FundingAccount(id="account-1"),
            ),
        ]
        bulk = BulkPaymentRequest(payments=payments)
        payload = bulk.to_api_payload()
        assert "payments" in payload
        assert len(payload["payments"]) == 1
        assert payload["payments"][0]["billId"] == "bill-1"
