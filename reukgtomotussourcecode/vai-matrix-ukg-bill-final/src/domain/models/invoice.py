"""
Invoice domain model - Represents BILL.com Accounts Payable bill/invoice.

This model represents a bill/invoice in the BILL.com AP system. In BILL.com,
"bills" are what you owe to vendors (accounts payable). The term "invoice"
refers to the vendor's invoice number that identifies the bill.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.config.constants import (
    BILL_DATE_FORMAT,
    BILL_STATUS_APPROVED,
    BILL_STATUS_OPEN,
    BILL_STATUS_PAID,
    BILL_STATUS_PARTIAL,
    BILL_STATUS_VOIDED,
    DEFAULT_PAYMENT_TERM_DAYS,
    NON_UPDATABLE_BILL_STATUSES,
)


class BillStatus(str, Enum):
    """BILL.com bill/invoice status."""

    OPEN = "open"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    PAID = "paid"
    PARTIAL = "partial"
    VOIDED = "voided"

    @classmethod
    def from_string(cls, status: str) -> "BillStatus":
        """Convert string to status enum."""
        status = (status or "").lower().strip()
        for s in cls:
            if s.value == status:
                return s
        return cls.OPEN

    @property
    def is_payable(self) -> bool:
        """Check if bill can be paid."""
        return self in (BillStatus.OPEN, BillStatus.APPROVED)

    @property
    def is_updatable(self) -> bool:
        """Check if bill can be updated."""
        return self.value not in NON_UPDATABLE_BILL_STATUSES


@dataclass
class InvoiceLineItem:
    """A line item on a bill/invoice."""

    amount: Decimal
    description: str = ""
    gl_account_id: str = ""
    department_id: str = ""
    location_id: str = ""
    class_id: str = ""
    quantity: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        """Normalize after initialization."""
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))
        if isinstance(self.quantity, (int, float)):
            self.quantity = Decimal(str(self.quantity))

    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to BILL.com API payload."""
        payload: Dict[str, Any] = {
            "amount": float(self.amount),
        }

        if self.description:
            payload["description"] = self.description
        if self.gl_account_id:
            payload["glAccountId"] = self.gl_account_id
        if self.department_id:
            payload["departmentId"] = self.department_id
        if self.location_id:
            payload["locationId"] = self.location_id
        if self.class_id:
            payload["classId"] = self.class_id

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "amount": float(self.amount),
            "description": self.description,
            "gl_account_id": self.gl_account_id,
            "department_id": self.department_id,
            "location_id": self.location_id,
            "class_id": self.class_id,
            "quantity": float(self.quantity),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvoiceLineItem":
        """Create from dictionary."""
        return cls(
            amount=Decimal(str(data.get("amount", 0))),
            description=data.get("description", "") or "",
            gl_account_id=data.get("glAccountId", "") or data.get("gl_account_id", "") or "",
            department_id=data.get("departmentId", "") or data.get("department_id", "") or "",
            location_id=data.get("locationId", "") or data.get("location_id", "") or "",
            class_id=data.get("classId", "") or data.get("class_id", "") or "",
            quantity=Decimal(str(data.get("quantity", 1))),
        )


@dataclass
class Invoice:
    """
    BILL.com Accounts Payable bill/invoice.

    Represents a bill that the organization owes to a vendor.

    Attributes:
        id: BILL.com bill ID (assigned after creation)
        invoice_number: Vendor's invoice number (unique identifier)
        vendor_id: BILL.com vendor ID
        invoice_date: Date on the invoice
        due_date: Payment due date
        line_items: List of line items
        status: Bill status
        po_number: Purchase order number
        external_id: External identifier for upsert
        amount_due: Remaining amount due
        total_amount: Total invoice amount
        metadata: Additional bill data
    """

    # Required
    invoice_number: str
    vendor_id: str

    # Dates
    invoice_date: date
    due_date: date

    # BILL-assigned ID
    id: Optional[str] = None

    # Line items
    line_items: List[InvoiceLineItem] = field(default_factory=list)

    # Status
    status: BillStatus = BillStatus.OPEN

    # Optional identifiers
    po_number: str = ""
    external_id: str = ""
    vendor_name: str = ""

    # Amounts (calculated from line items or set by BILL)
    amount_due: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize after initialization."""
        self._normalize()

    def _normalize(self) -> None:
        """Normalize field values."""
        self.invoice_number = (self.invoice_number or "").strip()
        self.vendor_id = (self.vendor_id or "").strip()
        self.po_number = (self.po_number or "").strip()
        self.external_id = (self.external_id or "").strip()

        if isinstance(self.invoice_date, str):
            self.invoice_date = datetime.strptime(self.invoice_date, BILL_DATE_FORMAT).date()

        if isinstance(self.due_date, str):
            self.due_date = datetime.strptime(self.due_date, BILL_DATE_FORMAT).date()

        if isinstance(self.status, str):
            self.status = BillStatus.from_string(self.status)

        if isinstance(self.amount_due, (int, float)):
            self.amount_due = Decimal(str(self.amount_due))

        if isinstance(self.total_amount, (int, float)):
            self.total_amount = Decimal(str(self.total_amount))

        # Set external_id to invoice_number if not provided
        if not self.external_id:
            self.external_id = self.invoice_number

    @property
    def calculated_total(self) -> Decimal:
        """Calculate total from line items."""
        return sum((item.amount for item in self.line_items), Decimal("0"))

    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.status == BillStatus.PAID

    @property
    def is_payable(self) -> bool:
        """Check if invoice can be paid."""
        return self.status.is_payable

    @property
    def is_updatable(self) -> bool:
        """Check if invoice can be updated."""
        return self.status.is_updatable

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is past due date."""
        if self.is_paid:
            return False
        return date.today() > self.due_date

    @property
    def days_until_due(self) -> int:
        """Get days until due (negative if overdue)."""
        return (self.due_date - date.today()).days

    @property
    def exists_in_bill(self) -> bool:
        """Check if invoice exists in BILL (has ID)."""
        return self.id is not None

    def validate(self) -> List[str]:
        """
        Validate invoice data for BILL.com API.

        Returns:
            List of validation error messages
        """
        errors = []

        if not self.invoice_number:
            errors.append("invoice_number is required")

        if not self.vendor_id:
            errors.append("vendor_id is required")

        if not self.invoice_date:
            errors.append("invoice_date is required")

        if not self.due_date:
            errors.append("due_date is required")

        if not self.line_items:
            errors.append("At least one line item is required")
        else:
            for i, item in enumerate(self.line_items):
                if item.amount <= 0:
                    errors.append(f"Line item {i} has invalid amount: {item.amount}")

        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            errors.append(f"due_date ({self.due_date}) cannot be before invoice_date ({self.invoice_date})")

        return errors

    def is_valid(self) -> bool:
        """Check if invoice data is valid."""
        return len(self.validate()) == 0

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert to BILL.com API payload for create/update.

        Returns:
            Dictionary suitable for POST/PATCH to BILL API
        """
        payload: Dict[str, Any] = {
            "vendorId": self.vendor_id,
            "invoice": {
                "number": self.invoice_number,
                "date": self.invoice_date.strftime(BILL_DATE_FORMAT),
            },
            "dueDate": self.due_date.strftime(BILL_DATE_FORMAT),
            "billLineItems": [item.to_api_payload() for item in self.line_items],
        }

        if self.po_number:
            payload["poNumber"] = self.po_number

        if self.external_id:
            payload["externalId"] = self.external_id

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status.value,
            "po_number": self.po_number,
            "external_id": self.external_id,
            "line_items": [item.to_dict() for item in self.line_items],
            "calculated_total": float(self.calculated_total),
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "amount_due": float(self.amount_due) if self.amount_due else None,
            "is_paid": self.is_paid,
            "is_payable": self.is_payable,
            "is_overdue": self.is_overdue,
            "days_until_due": self.days_until_due,
        }

    def diff(self, other: "Invoice") -> Dict[str, tuple]:
        """Compare with another Invoice and return differences."""
        diffs = {}

        if self.due_date != other.due_date:
            diffs["due_date"] = (self.due_date, other.due_date)

        if self.po_number != other.po_number:
            diffs["po_number"] = (self.po_number, other.po_number)

        # Compare totals
        self_total = self.calculated_total
        other_total = other.calculated_total
        if abs(self_total - other_total) > Decimal("0.01"):
            diffs["total_amount"] = (float(self_total), float(other_total))

        return diffs

    def needs_update(self, existing: "Invoice") -> bool:
        """Check if invoice needs to be updated in BILL."""
        if not existing.is_updatable:
            return False
        return len(self.diff(existing)) > 0

    @classmethod
    def from_bill_api(cls, data: Dict[str, Any]) -> "Invoice":
        """Create Invoice from BILL.com API response."""
        # Extract invoice info
        invoice_info = data.get("invoice", {}) or {}
        invoice_number = invoice_info.get("number", "")
        invoice_date_str = invoice_info.get("date", "")

        # Parse dates
        invoice_date = None
        if invoice_date_str:
            try:
                invoice_date = datetime.strptime(invoice_date_str[:10], BILL_DATE_FORMAT).date()
            except ValueError:
                invoice_date = date.today()

        due_date_str = data.get("dueDate", "")
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str[:10], BILL_DATE_FORMAT).date()
            except ValueError:
                due_date = date.today() + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS)

        # Parse line items
        line_items_data = data.get("billLineItems", []) or []
        line_items = [InvoiceLineItem.from_dict(item) for item in line_items_data]

        # Calculate amounts
        total_amount = Decimal(str(data.get("totalAmount", 0) or 0))
        amount_due = Decimal(str(data.get("amountDue", 0) or 0))

        return cls(
            id=data.get("id"),
            invoice_number=invoice_number,
            vendor_id=data.get("vendorId", ""),
            invoice_date=invoice_date or date.today(),
            due_date=due_date or date.today() + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS),
            line_items=line_items,
            status=BillStatus.from_string(data.get("status", "")),
            po_number=data.get("poNumber", "") or "",
            external_id=data.get("externalId", "") or "",
            total_amount=total_amount if total_amount else None,
            amount_due=amount_due if amount_due else None,
            metadata={"bill_data": data},
        )

    @classmethod
    def from_csv_row(cls, row: Dict[str, str], vendor_mapping: Optional[Dict[str, str]] = None) -> "Invoice":
        """
        Create Invoice from CSV row.

        Args:
            row: CSV row dict
            vendor_mapping: Optional mapping from external vendor ID to BILL vendor ID
        """
        vendor_mapping = vendor_mapping or {}

        # Parse invoice date
        invoice_date_str = row.get("invoice_date", "").strip()
        invoice_date = None
        if invoice_date_str:
            try:
                invoice_date = datetime.strptime(invoice_date_str, BILL_DATE_FORMAT).date()
            except ValueError:
                invoice_date = date.today()

        # Parse or calculate due date
        due_date_str = row.get("due_date", "").strip()
        payment_term_days = int(row.get("payment_term_days", str(DEFAULT_PAYMENT_TERM_DAYS)) or DEFAULT_PAYMENT_TERM_DAYS)

        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, BILL_DATE_FORMAT).date()
            except ValueError:
                due_date = (invoice_date or date.today()) + timedelta(days=payment_term_days)
        else:
            due_date = (invoice_date or date.today()) + timedelta(days=payment_term_days)

        # Resolve vendor ID
        vendor_identifier = row.get("vendor_id", "").strip()
        vendor_id = vendor_mapping.get(vendor_identifier, vendor_identifier)

        # Build line items
        amount = Decimal(str(row.get("amount", "0") or "0"))
        description = row.get("description", "").strip() or "Invoice payment"

        line_items = [
            InvoiceLineItem(
                amount=amount,
                description=description,
                gl_account_id=row.get("gl_account", "").strip(),
            )
        ]

        return cls(
            invoice_number=row.get("invoice_number", "").strip(),
            vendor_id=vendor_id,
            invoice_date=invoice_date or date.today(),
            due_date=due_date,
            line_items=line_items,
            po_number=row.get("po_number", "").strip(),
            vendor_name=row.get("vendor_name", "").strip(),
        )
