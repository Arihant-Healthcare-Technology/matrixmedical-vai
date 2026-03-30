"""
Bulk/Batch operation mappers.

Provides mappers for bulk payment operations.
"""

from typing import Any, Dict, List

from src.domain.models.payment import Payment


def build_bulk_payment_payload(payments: List[Payment]) -> Dict[str, Any]:
    """
    Build bulk payment API payload.

    Args:
        payments: List of Payment domain models

    Returns:
        Bulk payment API payload
    """
    return {
        "payments": [p.to_api_payload() for p in payments],
    }


def parse_bulk_payment_results(
    data: Dict[str, Any],
) -> List[Payment]:
    """
    Parse bulk payment API response.

    Args:
        data: API response data

    Returns:
        List of created Payment domain models
    """
    results = data.get("results", [])
    payments = []

    for result in results:
        if result.get("id"):
            payment = Payment.from_bill_api(result)
            payments.append(payment)

    return payments
