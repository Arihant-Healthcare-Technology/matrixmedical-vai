"""
Vendor mapping functions.

Provides mappers for transforming between Vendor domain models and BILL API formats.
"""

from typing import Any, Dict, Optional

from src.domain.models.vendor import PaymentMethod as VendorPaymentMethod
from src.domain.models.vendor import Vendor, VendorStatus


def map_vendor_from_api(data: Dict[str, Any]) -> Vendor:
    """
    Map BILL AP API response to Vendor domain model.

    Args:
        data: API response data

    Returns:
        Vendor domain model
    """
    return Vendor.from_bill_api(data)


def map_vendor_to_api(vendor: Vendor) -> Dict[str, Any]:
    """
    Map Vendor domain model to API payload.

    Args:
        vendor: Vendor domain model

    Returns:
        API payload dict
    """
    return vendor.to_api_payload()


def map_vendor_status(status_str: Optional[str]) -> VendorStatus:
    """
    Map API status string to VendorStatus enum.

    Args:
        status_str: Status from API (active, inactive, archived)

    Returns:
        VendorStatus enum value
    """
    if not status_str:
        return VendorStatus.ACTIVE

    status_lower = status_str.lower().strip()

    if status_lower in ("inactive", "retired"):
        return VendorStatus.INACTIVE
    elif status_lower == "archived":
        return VendorStatus.ARCHIVED
    else:
        return VendorStatus.ACTIVE


def map_vendor_payment_method(method_str: Optional[str]) -> VendorPaymentMethod:
    """
    Map API payment method string to enum.

    Args:
        method_str: Payment method from API

    Returns:
        PaymentMethod enum value
    """
    if not method_str:
        return VendorPaymentMethod.CHECK

    method_upper = method_str.upper().strip()

    method_map = {
        "ACH": VendorPaymentMethod.ACH,
        "CHECK": VendorPaymentMethod.CHECK,
        "WIRE": VendorPaymentMethod.WIRE,
        "CARD_ACCOUNT": VendorPaymentMethod.CARD_ACCOUNT,
        "CARD": VendorPaymentMethod.CARD_ACCOUNT,
        "VIRTUAL_CARD": VendorPaymentMethod.CARD_ACCOUNT,
    }

    return method_map.get(method_upper, VendorPaymentMethod.CHECK)
