"""
Payment mapping functions.

Provides mappers for transforming between Payment domain models and BILL API formats.
"""

from typing import Any, Dict, Optional

from src.domain.models.payment import (
    FundingAccount,
    FundingAccountType,
    Payment,
    PaymentMethod,
    PaymentStatus,
)


def map_payment_from_api(data: Dict[str, Any]) -> Payment:
    """
    Map BILL AP API response to Payment domain model.

    Args:
        data: API response data

    Returns:
        Payment domain model
    """
    return Payment.from_bill_api(data)


def map_payment_to_api(payment: Payment) -> Dict[str, Any]:
    """
    Map Payment domain model to API payload.

    Args:
        payment: Payment domain model

    Returns:
        API payload dict
    """
    return payment.to_api_payload()


def map_payment_status(status_str: Optional[str]) -> PaymentStatus:
    """
    Map API status string to PaymentStatus enum.

    Args:
        status_str: Status from API

    Returns:
        PaymentStatus enum value
    """
    if not status_str:
        return PaymentStatus.PENDING

    status_upper = status_str.upper().strip()

    status_map = {
        "PENDING": PaymentStatus.PENDING,
        "SCHEDULED": PaymentStatus.SCHEDULED,
        "PROCESSING": PaymentStatus.PROCESSING,
        "IN_PROGRESS": PaymentStatus.PROCESSING,
        "COMPLETED": PaymentStatus.COMPLETED,
        "PAID": PaymentStatus.COMPLETED,
        "FAILED": PaymentStatus.FAILED,
        "ERROR": PaymentStatus.FAILED,
        "CANCELLED": PaymentStatus.CANCELLED,
        "CANCELED": PaymentStatus.CANCELLED,
        "VOIDED": PaymentStatus.VOIDED,
        "VOID": PaymentStatus.VOIDED,
    }

    return status_map.get(status_upper, PaymentStatus.PENDING)


def map_payment_method(method_str: Optional[str]) -> PaymentMethod:
    """
    Map API payment method string to enum.

    Args:
        method_str: Payment method from API

    Returns:
        PaymentMethod enum value
    """
    if not method_str:
        return PaymentMethod.CHECK

    method_upper = method_str.upper().strip()

    method_map = {
        "ACH": PaymentMethod.ACH,
        "CHECK": PaymentMethod.CHECK,
        "WIRE": PaymentMethod.WIRE,
        "CARD_ACCOUNT": PaymentMethod.CARD_ACCOUNT,
        "CARD": PaymentMethod.CARD_ACCOUNT,
        "VIRTUAL_CARD": PaymentMethod.CARD_ACCOUNT,
    }

    return method_map.get(method_upper, PaymentMethod.CHECK)


def map_funding_account_from_api(data: Dict[str, Any]) -> Optional[FundingAccount]:
    """
    Map API funding account data to domain model.

    Args:
        data: Funding account data from API

    Returns:
        FundingAccount or None
    """
    if not data:
        return None

    account_id = data.get("id") or data.get("accountId")
    if not account_id:
        return None

    account_type_str = data.get("type", "BANK_ACCOUNT")
    try:
        account_type = FundingAccountType(account_type_str)
    except ValueError:
        account_type = FundingAccountType.BANK_ACCOUNT

    return FundingAccount(
        id=account_id,
        account_type=account_type,
    )
