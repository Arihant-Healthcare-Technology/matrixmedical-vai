"""
Vendor domain model - Represents BILL.com Accounts Payable vendor.

This model represents a vendor/supplier in the BILL.com AP system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.config.constants import (
    DEFAULT_PAYMENT_METHOD,
    DEFAULT_PAYMENT_TERM_DAYS,
    VALID_PAYMENT_METHODS,
)


class PaymentMethod(str, Enum):
    """Vendor payment methods."""

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
        return cls.ACH  # Default


class VendorStatus(str, Enum):
    """Vendor status in BILL.com."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass
class VendorAddress:
    """Vendor address."""

    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"

    def is_us_address(self) -> bool:
        """Check if this is a US address."""
        return self.country.upper() in ("US", "USA", "UNITED STATES")

    def is_complete(self) -> bool:
        """Check if address has minimum required fields."""
        return bool(self.line1 and self.city and self.state and self.zip_code)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for API payload."""
        return {
            "line1": self.line1,
            "line2": self.line2,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VendorAddress":
        """Create from dictionary."""
        return cls(
            line1=data.get("line1", "") or "",
            line2=data.get("line2", "") or "",
            city=data.get("city", "") or "",
            state=data.get("state", "") or "",
            zip_code=data.get("zip", "") or data.get("zip_code", "") or "",
            country=data.get("country", "US") or "US",
        )


@dataclass
class Vendor:
    """
    BILL.com Accounts Payable vendor.

    Represents a vendor/supplier that can receive payments through BILL.com.

    Attributes:
        id: BILL.com vendor ID (assigned after creation)
        name: Vendor name (required, used for lookup)
        short_name: Short name/alias
        email: Vendor contact email
        phone: Vendor contact phone
        address: Vendor address
        payment_method: Preferred payment method
        payment_term_days: Payment terms (days until due)
        external_id: External identifier for upsert
        status: Vendor status
        metadata: Additional vendor data
    """

    # Required
    name: str

    # BILL-assigned ID
    id: Optional[str] = None

    # Identifiers
    short_name: str = ""
    external_id: str = ""

    # Contact
    email: str = ""
    phone: str = ""

    # Address
    address: VendorAddress = field(default_factory=VendorAddress)

    # Payment settings
    payment_method: PaymentMethod = PaymentMethod.ACH
    payment_term_days: int = DEFAULT_PAYMENT_TERM_DAYS

    # Status
    status: VendorStatus = VendorStatus.ACTIVE

    # Banking info (stored but not exposed)
    has_bank_info: bool = False

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
        self.name = (self.name or "").strip()
        self.short_name = (self.short_name or "").strip()
        self.email = (self.email or "").strip().lower()
        self.phone = self._normalize_phone(self.phone)

        if isinstance(self.payment_method, str):
            self.payment_method = PaymentMethod.from_string(self.payment_method)

        if isinstance(self.status, str):
            try:
                self.status = VendorStatus(self.status.lower())
            except ValueError:
                self.status = VendorStatus.ACTIVE

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone to digits only."""
        if not phone:
            return ""
        return "".join(c for c in phone if c.isdigit())[-10:]

    @property
    def is_active(self) -> bool:
        """Check if vendor is active."""
        return self.status == VendorStatus.ACTIVE

    @property
    def is_international(self) -> bool:
        """Check if vendor is international (non-US)."""
        return not self.address.is_us_address()

    @property
    def exists_in_bill(self) -> bool:
        """Check if vendor exists in BILL (has ID)."""
        return self.id is not None

    def validate(self) -> List[str]:
        """
        Validate vendor data for BILL.com API.

        Returns:
            List of validation error messages
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if self.email and "@" not in self.email:
            errors.append(f"Invalid email format: {self.email}")

        if self.payment_term_days < 0:
            errors.append(f"payment_term_days must be >= 0: {self.payment_term_days}")

        return errors

    def is_valid(self) -> bool:
        """Check if vendor data is valid."""
        return len(self.validate()) == 0

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert to BILL.com API payload for create/update.

        Returns:
            Dictionary suitable for POST/PATCH to BILL API
        """
        payload: Dict[str, Any] = {
            "name": self.name,
        }

        if self.short_name:
            payload["shortName"] = self.short_name

        if self.email:
            payload["email"] = self.email

        if self.phone:
            payload["phone"] = self.phone

        if self.address.is_complete():
            payload["address"] = self.address.to_dict()

        payload["paymentMethod"] = self.payment_method.value
        payload["paymentTermDays"] = self.payment_term_days

        if self.external_id:
            payload["externalId"] = self.external_id

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "external_id": self.external_id,
            "email": self.email,
            "phone": self.phone,
            "address": self.address.to_dict(),
            "payment_method": self.payment_method.value,
            "payment_term_days": self.payment_term_days,
            "status": self.status.value,
            "is_active": self.is_active,
            "is_international": self.is_international,
        }

    def diff(self, other: "Vendor") -> Dict[str, tuple]:
        """Compare with another Vendor and return differences."""
        diffs = {}
        compare_fields = ["name", "short_name", "email", "phone", "payment_method", "payment_term_days"]

        for field_name in compare_fields:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)

            if isinstance(self_val, Enum):
                self_val = self_val.value
            if isinstance(other_val, Enum):
                other_val = other_val.value

            if self_val != other_val:
                diffs[field_name] = (self_val, other_val)

        # Compare address
        for addr_field in ["line1", "line2", "city", "state", "zip_code", "country"]:
            self_val = getattr(self.address, addr_field)
            other_val = getattr(other.address, addr_field)
            if self_val != other_val:
                diffs[f"address.{addr_field}"] = (self_val, other_val)

        return diffs

    def needs_update(self, existing: "Vendor") -> bool:
        """Check if vendor needs to be updated in BILL."""
        return len(self.diff(existing)) > 0

    @classmethod
    def from_bill_api(cls, data: Dict[str, Any]) -> "Vendor":
        """Create Vendor from BILL.com API response."""
        address_data = data.get("address", {}) or {}

        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            short_name=data.get("shortName", ""),
            external_id=data.get("externalId", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            address=VendorAddress.from_dict(address_data),
            payment_method=PaymentMethod.from_string(data.get("paymentMethod", "")),
            payment_term_days=data.get("paymentTermDays", DEFAULT_PAYMENT_TERM_DAYS),
            status=VendorStatus(data.get("status", "active").lower()) if data.get("status") else VendorStatus.ACTIVE,
            has_bank_info=data.get("hasBankInfo", False),
            metadata={"bill_data": data},
        )

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Vendor":
        """Create Vendor from CSV row."""
        return cls(
            name=row.get("name", "") or row.get("vendor_name", ""),
            short_name=row.get("short_name", "") or row.get("shortName", ""),
            external_id=row.get("external_id", "") or row.get("vendor_id", ""),
            email=row.get("email", "") or row.get("vendor_email", ""),
            phone=row.get("phone", "") or row.get("vendor_phone", ""),
            address=VendorAddress(
                line1=row.get("address1", "") or row.get("line1", ""),
                line2=row.get("address2", "") or row.get("line2", ""),
                city=row.get("city", ""),
                state=row.get("state", ""),
                zip_code=row.get("zip", "") or row.get("postal_code", ""),
                country=row.get("country", "US"),
            ),
            payment_method=PaymentMethod.from_string(row.get("payment_method", "")),
            payment_term_days=int(row.get("payment_term_days", str(DEFAULT_PAYMENT_TERM_DAYS)) or DEFAULT_PAYMENT_TERM_DAYS),
        )
