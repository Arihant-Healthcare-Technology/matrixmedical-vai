"""
CSV export mappers.

Provides mappers for exporting domain models to CSV format.
"""

from typing import Dict

from src.domain.models.invoice import Invoice
from src.domain.models.vendor import Vendor

from .common import format_date


def build_vendor_csv_row(vendor: Vendor) -> Dict[str, str]:
    """
    Build CSV row for vendor export.

    Args:
        vendor: Vendor to export

    Returns:
        Dict suitable for csv.DictWriter
    """
    return {
        "name": vendor.name,
        "short_name": vendor.short_name or "",
        "email": vendor.email or "",
        "phone": vendor.phone or "",
        "address_line1": vendor.address.line1 if vendor.address else "",
        "address_line2": vendor.address.line2 if vendor.address else "",
        "city": vendor.address.city if vendor.address else "",
        "state": vendor.address.state if vendor.address else "",
        "zip": vendor.address.zip_code if vendor.address else "",
        "country": vendor.address.country if vendor.address else "US",
        "payment_method": vendor.payment_method.value if vendor.payment_method else "CHECK",
        "payment_term_days": str(vendor.payment_term_days or 30),
        "external_id": vendor.external_id or "",
    }


def build_invoice_csv_row(invoice: Invoice) -> Dict[str, str]:
    """
    Build CSV row for invoice export.

    Args:
        invoice: Invoice to export

    Returns:
        Dict suitable for csv.DictWriter
    """
    # Get description from first line item if available
    description = ""
    if invoice.line_items:
        description = invoice.line_items[0].description or ""

    # Calculate total from line items if not set
    total_amount = invoice.total_amount
    if total_amount is None and invoice.line_items:
        total_amount = sum(item.amount for item in invoice.line_items)

    return {
        "invoice_number": invoice.invoice_number,
        "vendor_id": invoice.vendor_id,
        "invoice_date": format_date(invoice.invoice_date),
        "due_date": format_date(invoice.due_date),
        "amount": str(total_amount) if total_amount is not None else "0",
        "status": invoice.status.value if invoice.status else "open",
        "description": description,
        "external_id": invoice.external_id or "",
    }
