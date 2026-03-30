"""
Invoice/Bill mapping functions.

Provides mappers for transforming between Invoice domain models and BILL API formats.
"""

from typing import Any, Dict, List, Optional

from src.domain.models.invoice import BillStatus, Invoice, InvoiceLineItem


def map_invoice_from_api(data: Dict[str, Any]) -> Invoice:
    """
    Map BILL AP API response to Invoice domain model.

    Args:
        data: API response data

    Returns:
        Invoice domain model
    """
    return Invoice.from_bill_api(data)


def map_invoice_to_api(invoice: Invoice) -> Dict[str, Any]:
    """
    Map Invoice domain model to API payload.

    Args:
        invoice: Invoice domain model

    Returns:
        API payload dict
    """
    return invoice.to_api_payload()


def map_bill_status(status_str: Optional[str]) -> BillStatus:
    """
    Map API status string to BillStatus enum.

    Args:
        status_str: Status from API

    Returns:
        BillStatus enum value
    """
    if not status_str:
        return BillStatus.OPEN

    status_lower = status_str.lower().strip()

    status_map = {
        "open": BillStatus.OPEN,
        "approved": BillStatus.APPROVED,
        "scheduled": BillStatus.SCHEDULED,
        "processing": BillStatus.PROCESSING,
        "paid": BillStatus.PAID,
        "partial": BillStatus.PARTIAL,
        "voided": BillStatus.VOIDED,
        "void": BillStatus.VOIDED,
    }

    return status_map.get(status_lower, BillStatus.OPEN)


def map_line_items_from_api(items_data: List[Dict[str, Any]]) -> List[InvoiceLineItem]:
    """
    Map API line items to domain models.

    Args:
        items_data: List of line item dicts from API

    Returns:
        List of InvoiceLineItem domain models
    """
    result = []
    for item in items_data:
        line = InvoiceLineItem.from_dict(item)
        result.append(line)
    return result


def map_line_items_to_api(items: List[InvoiceLineItem]) -> List[Dict[str, Any]]:
    """
    Map domain line items to API format.

    Args:
        items: List of InvoiceLineItem domain models

    Returns:
        List of dicts for API payload
    """
    return [item.to_api_payload() for item in items]
