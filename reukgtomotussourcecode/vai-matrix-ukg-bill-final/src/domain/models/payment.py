"""
Payment domain model - Represents BILL.com Accounts Payable payment.

This model represents a payment made to a vendor through BILL.com.
Payments can be made via ACH, check, wire, or virtual card.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.config.constants import (
    BILL_DATE_FORMAT,
    DEFAULT_PAYMENT_METHOD,
    VALID_PAYMENT_METHODS,
)


class PaymentStatus(str, Enum):
    """Payment status in BILL.com."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    VOIDED = "VOIDED"

    @classmethod
    def from_string(cls, status: str) -> "PaymentStatus":
        """Convert string to status enum."""
        status = (status or "").upper().strip()
        for s in cls:
            if s.value == status:
                return s
        return cls.PENDING

    @property
    def is_final(self) -> bool:
        """Check if status is final (cannot change)."""
        return self in (
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.VOIDED,
        )

    @property
    def is_success(self) -> bool:
        """Check if payment succeeded."""
        return self == PaymentStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if payment is still pending."""
        return self in (
            PaymentStatus.PENDING,
            PaymentStatus.APPROVED,
            PaymentStatus.SCHEDULED,
            PaymentStatus.PROCESSING,
        )

    @property
    def description(self) -> str:
        """Get human-readable description."""
        descriptions = {
            PaymentStatus.PENDING: "Payment is pending approval",
            PaymentStatus.APPROVED: "Payment approved, awaiting processing",
            PaymentStatus.SCHEDULED: "Payment scheduled for future date",
            PaymentStatus.PROCESSING: "Payment is being processed",
            PaymentStatus.COMPLETED: "Payment completed successfully",
            PaymentStatus.FAILED: "Payment failed",
            PaymentStatus.CANCELLED: "Payment was cancelled",
            PaymentStatus.VOIDED: "Payment was voided",
        }
        return descriptions.get(self, "Unknown status")


class PaymentMethod(str, Enum):
    """Payment method types."""

    CHECK = "CHECK"
    ACH = "ACH"
    WIRE = "WIRE"
    CARD_ACCOUNT = "CARD_ACCOUNT"

    @classmethod
    def from_string(cls, method: str) -> "PaymentMethod":
        """Convert string to payment method enum."""
        method = (method or "").upper().strip()
        if method in VALID_PAYMENT_METHODS:
            return cls(method)
        return cls.ACH


class FundingAccountType(str, Enum):
    """Funding account types."""

    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    LINE_OF_CREDIT = "LINE_OF_CREDIT"


@dataclass
class FundingAccount:
    """Funding account for payments."""

    id: str
    account_type: FundingAccountType = FundingAccountType.BANK_ACCOUNT
    name: str = ""
    last_four: str = ""

    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to BILL.com API payload."""
        return {
            "type": self.account_type.value,
            "id": self.id,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.account_type.value,
            "name": self.name,
            "last_four": self.last_four,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FundingAccount":
        """Create from dictionary."""
        account_type_str = data.get("type", "BANK_ACCOUNT")
        try:
            account_type = FundingAccountType(account_type_str)
        except ValueError:
            account_type = FundingAccountType.BANK_ACCOUNT

        return cls(
            id=data.get("id", ""),
            account_type=account_type,
            name=data.get("name", "") or "",
            last_four=data.get("lastFour", "") or data.get("last_four", "") or "",
        )


@dataclass
class Payment:
    """
    BILL.com Accounts Payable payment.

    Represents a payment made to a vendor.

    Attributes:
        id: BILL.com payment ID (assigned after creation)
        bill_id: BILL.com bill ID being paid
        amount: Payment amount
        process_date: Date payment will be processed
        funding_account: Funding account for payment
        payment_method: Payment method (CHECK, ACH, WIRE, etc.)
        status: Payment status
        vendor_id: Vendor receiving payment
        vendor_name: Vendor name (for display)
        invoice_number: Related invoice number
        reference: External reference number
        check_number: Check number (if paid by check)
        confirmation_number: Payment confirmation number
        metadata: Additional payment data
    """

    # Required
    bill_id: str
    amount: Decimal

    # Payment details
    process_date: date
    funding_account: Optional[FundingAccount] = None
    payment_method: PaymentMethod = PaymentMethod.ACH

    # BILL-assigned ID
    id: Optional[str] = None

    # Status
    status: PaymentStatus = PaymentStatus.PENDING

    # Related entities
    vendor_id: str = ""
    vendor_name: str = ""
    invoice_number: str = ""

    # Tracking
    reference: str = ""
    check_number: str = ""
    confirmation_number: str = ""

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize after initialization."""
        self._normalize()

    def _normalize(self) -> None:
        """Normalize field values."""
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))

        if isinstance(self.process_date, str):
            self.process_date = datetime.strptime(self.process_date, BILL_DATE_FORMAT).date()

        if isinstance(self.status, str):
            self.status = PaymentStatus.from_string(self.status)

        if isinstance(self.payment_method, str):
            self.payment_method = PaymentMethod.from_string(self.payment_method)

    @property
    def is_completed(self) -> bool:
        """Check if payment is completed."""
        return self.status == PaymentStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if payment is still pending."""
        return self.status.is_pending

    @property
    def is_failed(self) -> bool:
        """Check if payment failed."""
        return self.status == PaymentStatus.FAILED

    @property
    def is_cancellable(self) -> bool:
        """Check if payment can be cancelled."""
        return self.status in (
            PaymentStatus.PENDING,
            PaymentStatus.APPROVED,
            PaymentStatus.SCHEDULED,
        )

    @property
    def exists_in_bill(self) -> bool:
        """Check if payment exists in BILL (has ID)."""
        return self.id is not None

    def validate(self) -> List[str]:
        """
        Validate payment data for BILL.com API.

        Returns:
            List of validation error messages
        """
        errors = []

        if not self.bill_id:
            errors.append("bill_id is required")

        if not self.amount or self.amount <= 0:
            errors.append(f"amount must be positive: {self.amount}")

        if not self.process_date:
            errors.append("process_date is required")
        elif self.process_date < date.today():
            errors.append(f"process_date cannot be in the past: {self.process_date}")

        if not self.funding_account:
            errors.append("funding_account is required")
        elif not self.funding_account.id:
            errors.append("funding_account.id is required")

        return errors

    def is_valid(self) -> bool:
        """Check if payment data is valid."""
        return len(self.validate()) == 0

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert to BILL.com API payload for create.

        Returns:
            Dictionary suitable for POST to BILL API
        """
        payload: Dict[str, Any] = {
            "billId": self.bill_id,
            "amount": float(self.amount),
            "processDate": self.process_date.strftime(BILL_DATE_FORMAT),
        }

        if self.funding_account:
            payload["fundingAccount"] = self.funding_account.to_api_payload()

        if self.payment_method:
            payload["paymentMethod"] = self.payment_method.value

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "bill_id": self.bill_id,
            "amount": float(self.amount),
            "process_date": self.process_date.isoformat() if self.process_date else None,
            "payment_method": self.payment_method.value,
            "status": self.status.value,
            "status_description": self.status.description,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "reference": self.reference,
            "check_number": self.check_number,
            "confirmation_number": self.confirmation_number,
            "funding_account": self.funding_account.to_dict() if self.funding_account else None,
            "is_completed": self.is_completed,
            "is_pending": self.is_pending,
            "is_failed": self.is_failed,
        }

    @classmethod
    def from_bill_api(cls, data: Dict[str, Any]) -> "Payment":
        """Create Payment from BILL.com API response."""
        # Parse process date
        process_date_str = data.get("processDate", "")
        process_date = None
        if process_date_str:
            try:
                process_date = datetime.strptime(process_date_str[:10], BILL_DATE_FORMAT).date()
            except ValueError:
                process_date = date.today()

        # Parse funding account
        funding_account_data = data.get("fundingAccount", {}) or {}
        funding_account = FundingAccount.from_dict(funding_account_data) if funding_account_data else None

        # Parse completed timestamp
        completed_at = None
        if data.get("completedDate"):
            try:
                completed_at = datetime.strptime(data["completedDate"][:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

        return cls(
            id=data.get("id"),
            bill_id=data.get("billId", ""),
            amount=Decimal(str(data.get("amount", 0))),
            process_date=process_date or date.today(),
            funding_account=funding_account,
            payment_method=PaymentMethod.from_string(data.get("paymentMethod", "")),
            status=PaymentStatus.from_string(data.get("status", "")),
            vendor_id=data.get("vendorId", "") or "",
            vendor_name=data.get("vendorName", "") or "",
            invoice_number=data.get("invoiceNumber", "") or "",
            reference=data.get("reference", "") or "",
            check_number=data.get("checkNumber", "") or "",
            confirmation_number=data.get("confirmationNumber", "") or "",
            completed_at=completed_at,
            metadata={"bill_data": data},
        )


@dataclass
class ExternalPayment:
    """
    External payment record.

    Represents a payment made outside of BILL.com that needs to be recorded
    to mark a bill as paid.
    """

    bill_id: str
    amount: Decimal
    payment_date: date
    reference: str = ""
    payment_method: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        """Normalize after initialization."""
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))

        if isinstance(self.payment_date, str):
            self.payment_date = datetime.strptime(self.payment_date, BILL_DATE_FORMAT).date()

    def validate(self) -> List[str]:
        """Validate external payment data."""
        errors = []

        if not self.bill_id:
            errors.append("bill_id is required")

        if not self.amount or self.amount <= 0:
            errors.append(f"amount must be positive: {self.amount}")

        if not self.payment_date:
            errors.append("payment_date is required")

        return errors

    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to BILL.com API payload."""
        payload: Dict[str, Any] = {
            "billId": self.bill_id,
            "amount": float(self.amount),
            "paymentDate": self.payment_date.strftime(BILL_DATE_FORMAT),
        }

        if self.reference:
            payload["reference"] = self.reference

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "bill_id": self.bill_id,
            "amount": float(self.amount),
            "payment_date": self.payment_date.isoformat(),
            "reference": self.reference,
            "payment_method": self.payment_method,
            "notes": self.notes,
        }


@dataclass
class BulkPaymentRequest:
    """
    Bulk payment request.

    Contains multiple payments to be processed together.
    """

    payments: List[Payment] = field(default_factory=list)

    @property
    def total_amount(self) -> Decimal:
        """Get total amount of all payments."""
        return sum((p.amount for p in self.payments), Decimal("0"))

    @property
    def payment_count(self) -> int:
        """Get number of payments."""
        return len(self.payments)

    def validate(self) -> List[str]:
        """Validate all payments."""
        errors = []

        if not self.payments:
            errors.append("At least one payment is required")
            return errors

        for i, payment in enumerate(self.payments):
            payment_errors = payment.validate()
            for error in payment_errors:
                errors.append(f"Payment {i}: {error}")

        return errors

    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to BILL.com bulk payment API payload."""
        return {
            "payments": [p.to_api_payload() for p in self.payments],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "payments": [p.to_dict() for p in self.payments],
            "total_amount": float(self.total_amount),
            "payment_count": self.payment_count,
        }
