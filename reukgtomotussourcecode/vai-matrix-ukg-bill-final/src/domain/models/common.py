"""
Common domain model types - Shared enums and types used across domain models.

This module provides shared types that are used by multiple domain models
to avoid duplication and ensure consistency.
"""

from enum import Enum

from src.infrastructure.config.constants import VALID_PAYMENT_METHODS


class PaymentMethod(str, Enum):
    """
    Payment method types for BILL.com transactions.

    Used by both Vendor (preferred payment method) and Payment (actual payment method).
    """

    CHECK = "CHECK"
    ACH = "ACH"
    WIRE = "WIRE"
    CARD_ACCOUNT = "CARD_ACCOUNT"

    @classmethod
    def from_string(cls, method: str) -> "PaymentMethod":
        """
        Convert string to payment method enum.

        Args:
            method: String representation of payment method.

        Returns:
            PaymentMethod enum value, defaults to ACH if invalid.
        """
        method = (method or "").upper().strip()
        if method in VALID_PAYMENT_METHODS:
            return cls(method)
        return cls.ACH  # Default to ACH

    @property
    def description(self) -> str:
        """Get human-readable description."""
        descriptions = {
            PaymentMethod.CHECK: "Paper check mailed to vendor",
            PaymentMethod.ACH: "Electronic bank transfer (ACH)",
            PaymentMethod.WIRE: "Wire transfer",
            PaymentMethod.CARD_ACCOUNT: "Virtual card payment",
        }
        return descriptions.get(self, "Unknown payment method")
