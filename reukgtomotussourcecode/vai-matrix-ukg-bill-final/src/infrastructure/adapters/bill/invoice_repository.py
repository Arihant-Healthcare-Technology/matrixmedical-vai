"""
BILL.com Accounts Payable invoice/bill repository implementation.

This module implements the InvoiceRepository interface using the AP API client.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import InvoiceRepository
from src.domain.models.invoice import Invoice
from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient

logger = logging.getLogger(__name__)


class InvoiceRepositoryImpl(InvoiceRepository):
    """
    BILL.com Accounts Payable invoice/bill repository implementation.
    """

    def __init__(self, client: AccountsPayableClient) -> None:
        """Initialize repository."""
        self._client = client
        self._invoice_cache: Dict[str, str] = {}  # invoice_number -> bill_id
        self._external_id_cache: Dict[str, str] = {}  # external_id -> bill_id

    def get_by_id(self, entity_id: str) -> Optional[Invoice]:
        """Get invoice by BILL ID."""
        try:
            data = self._client.get_bill(entity_id)
            if data:
                return Invoice.from_bill_api(data)
        except Exception as e:
            logger.debug(f"Invoice not found by ID {entity_id}: {e}")

        return None

    def get_by_invoice_number(
        self,
        invoice_number: str,
        vendor_id: Optional[str] = None,
    ) -> Optional[Invoice]:
        """Get invoice by invoice number."""
        cache_key = f"{invoice_number}:{vendor_id or ''}"

        # Check cache
        if cache_key in self._invoice_cache:
            bill_id = self._invoice_cache[cache_key]
            return self.get_by_id(bill_id)

        # Search via API
        data = self._client.get_bill_by_invoice_number(invoice_number, vendor_id)
        if data:
            invoice = Invoice.from_bill_api(data)
            if invoice.id:
                self._invoice_cache[cache_key] = invoice.id
            return invoice

        return None

    def get_by_external_id(self, external_id: str) -> Optional[Invoice]:
        """Get invoice by external ID."""
        # Check cache
        if external_id in self._external_id_cache:
            bill_id = self._external_id_cache[external_id]
            return self.get_by_id(bill_id)

        # Search via API
        data = self._client.get_bill_by_external_id(external_id)
        if data:
            invoice = Invoice.from_bill_api(data)
            if invoice.id:
                self._external_id_cache[external_id] = invoice.id
            return invoice

        return None

    def get_invoices_for_vendor(
        self,
        vendor_id: str,
        status: Optional[str] = None,
    ) -> List[Invoice]:
        """Get all invoices for a vendor."""
        data = self._client.get_bills_for_vendor(vendor_id, status)
        return [Invoice.from_bill_api(item) for item in data]

    def get_unpaid_invoices(
        self,
        vendor_id: Optional[str] = None,
    ) -> List[Invoice]:
        """Get all unpaid invoices."""
        params: Dict[str, Any] = {}
        if vendor_id:
            params["vendorId"] = vendor_id

        # Get open and approved bills
        all_bills = self._client._paginate(
            "/bills",
            params=params,
            item_keys=["bills"],
        )

        unpaid = []
        for item in all_bills:
            invoice = Invoice.from_bill_api(item)
            if invoice.is_payable:
                unpaid.append(invoice)

        return unpaid

    def get_overdue_invoices(self) -> List[Invoice]:
        """Get all overdue invoices."""
        unpaid = self.get_unpaid_invoices()
        return [inv for inv in unpaid if inv.is_overdue]

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Invoice]:
        """List invoices with pagination."""
        filters = filters or {}
        vendor_id = filters.get("vendor_id")
        status = filters.get("status")

        data = self._client.list_bills(
            page=page,
            page_size=page_size,
            vendor_id=vendor_id,
            status=status,
        )

        return [Invoice.from_bill_api(item) for item in data]

    def create(self, entity: Invoice) -> Invoice:
        """Create new invoice in BILL."""
        payload = entity.to_api_payload()
        data = self._client.create_bill(payload)
        created = Invoice.from_bill_api(data)

        # Update caches
        if created.id:
            cache_key = f"{created.invoice_number}:{created.vendor_id}"
            self._invoice_cache[cache_key] = created.id
            if created.external_id:
                self._external_id_cache[created.external_id] = created.id

        logger.info(f"Created invoice: {created.invoice_number} ({created.id})")
        return created

    def update(self, entity: Invoice) -> Invoice:
        """Update existing invoice in BILL."""
        if not entity.id:
            raise ValueError("Cannot update invoice without ID")

        # Check if updatable
        existing = self.get_by_id(entity.id)
        if existing and not existing.is_updatable:
            logger.warning(
                f"Invoice {entity.invoice_number} has status {existing.status.value}, "
                "cannot update"
            )
            return existing

        payload = entity.to_api_payload()
        data = self._client.update_bill(entity.id, payload)

        if not data:
            data = self._client.get_bill(entity.id)

        updated = Invoice.from_bill_api(data) if data else entity
        logger.info(f"Updated invoice: {updated.invoice_number} ({updated.id})")
        return updated

    def delete(self, entity_id: str) -> bool:
        """Delete operation not supported for invoices."""
        raise NotImplementedError("Invoice deletion not supported. Use void instead.")

    def upsert(self, invoice: Invoice) -> Invoice:
        """Create or update invoice based on invoice_number lookup."""
        existing = None

        # Try external ID first
        if invoice.external_id:
            existing = self.get_by_external_id(invoice.external_id)

        # Fall back to invoice number + vendor
        if not existing:
            existing = self.get_by_invoice_number(
                invoice.invoice_number,
                invoice.vendor_id,
            )

        if existing:
            if invoice.needs_update(existing):
                invoice.id = existing.id
                return self.update(invoice)
            else:
                logger.debug(f"No changes for invoice: {invoice.invoice_number}")
                return existing
        else:
            return self.create(invoice)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._invoice_cache.clear()
        self._external_id_cache.clear()
