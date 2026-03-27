"""
BILL.com Accounts Payable repository implementations.

This module implements the VendorRepository, InvoiceRepository, and
PaymentRepository interfaces using the AP API client.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import (
    InvoiceRepository,
    PaymentRepository,
    VendorRepository,
)
from src.domain.models.invoice import Invoice
from src.domain.models.payment import ExternalPayment, Payment
from src.domain.models.vendor import Vendor
from src.infrastructure.adapters.bill.client import AccountsPayableClient

logger = logging.getLogger(__name__)


class VendorRepositoryImpl(VendorRepository):
    """
    BILL.com Accounts Payable vendor repository implementation.

    Implements the VendorRepository interface using the AP API client.
    """

    def __init__(self, client: AccountsPayableClient) -> None:
        """
        Initialize repository.

        Args:
            client: AP API client
        """
        self._client = client
        self._name_cache: Dict[str, str] = {}  # name -> vendor_id
        self._external_id_cache: Dict[str, str] = {}  # external_id -> vendor_id

    def get_by_id(self, entity_id: str) -> Optional[Vendor]:
        """Get vendor by BILL ID."""
        try:
            data = self._client.get_vendor(entity_id)
            if data:
                return Vendor.from_bill_api(data)
        except Exception as e:
            logger.debug(f"Vendor not found by ID {entity_id}: {e}")

        return None

    def get_by_name(self, name: str) -> Optional[Vendor]:
        """Get vendor by name (exact match)."""
        name_lower = name.lower().strip()

        # Check cache
        if name_lower in self._name_cache:
            vendor_id = self._name_cache[name_lower]
            return self.get_by_id(vendor_id)

        # Search via API
        data = self._client.get_vendor_by_name(name)
        if data:
            vendor = Vendor.from_bill_api(data)
            if vendor.id:
                self._name_cache[name_lower] = vendor.id
            return vendor

        return None

    def get_by_external_id(self, external_id: str) -> Optional[Vendor]:
        """Get vendor by external ID."""
        # Check cache
        if external_id in self._external_id_cache:
            vendor_id = self._external_id_cache[external_id]
            return self.get_by_id(vendor_id)

        # Search via API
        data = self._client.get_vendor_by_external_id(external_id)
        if data:
            vendor = Vendor.from_bill_api(data)
            if vendor.id:
                self._external_id_cache[external_id] = vendor.id
            return vendor

        return None

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Vendor]:
        """Search vendors by name."""
        query_lower = query.lower().strip()
        all_vendors = self._client.list_vendors(page=page, page_size=page_size)

        results = []
        for data in all_vendors:
            name = data.get("name", "").lower()
            if query_lower in name:
                results.append(Vendor.from_bill_api(data))

        return results

    def get_active_vendors(self) -> List[Vendor]:
        """Get all active vendors."""
        data = self._client.get_all_vendors(status="active")
        vendors = []

        for item in data:
            vendor = Vendor.from_bill_api(item)
            vendors.append(vendor)
            # Update caches
            if vendor.id:
                if vendor.name:
                    self._name_cache[vendor.name.lower()] = vendor.id
                if vendor.external_id:
                    self._external_id_cache[vendor.external_id] = vendor.id

        return vendors

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Vendor]:
        """List vendors with pagination."""
        filters = filters or {}
        status = filters.get("status")

        data = self._client.list_vendors(
            page=page,
            page_size=page_size,
            status=status,
        )

        return [Vendor.from_bill_api(item) for item in data]

    def create(self, entity: Vendor) -> Vendor:
        """Create new vendor in BILL."""
        payload = entity.to_api_payload()
        data = self._client.create_vendor(payload)
        created = Vendor.from_bill_api(data)

        # Update caches
        if created.id:
            if created.name:
                self._name_cache[created.name.lower()] = created.id
            if created.external_id:
                self._external_id_cache[created.external_id] = created.id

        logger.info(f"Created vendor: {created.name} ({created.id})")
        return created

    def update(self, entity: Vendor) -> Vendor:
        """Update existing vendor in BILL."""
        if not entity.id:
            raise ValueError("Cannot update vendor without ID")

        payload = entity.to_api_payload()
        data = self._client.update_vendor(entity.id, payload)

        if not data:
            data = self._client.get_vendor(entity.id)

        updated = Vendor.from_bill_api(data) if data else entity
        logger.info(f"Updated vendor: {updated.name} ({updated.id})")
        return updated

    def delete(self, entity_id: str) -> bool:
        """Delete operation not typically supported for vendors."""
        raise NotImplementedError("Vendor deletion not supported. Use archive instead.")

    def upsert(self, vendor: Vendor) -> Vendor:
        """Create or update vendor based on name/external_id lookup."""
        existing = None

        # Try external ID first
        if vendor.external_id:
            existing = self.get_by_external_id(vendor.external_id)

        # Fall back to name
        if not existing and vendor.name:
            existing = self.get_by_name(vendor.name)

        if existing:
            if vendor.needs_update(existing):
                vendor.id = existing.id
                return self.update(vendor)
            else:
                logger.debug(f"No changes for vendor: {vendor.name}")
                return existing
        else:
            return self.create(vendor)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._name_cache.clear()
        self._external_id_cache.clear()


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


class PaymentRepositoryImpl(PaymentRepository):
    """
    BILL.com Accounts Payable payment repository implementation.
    """

    def __init__(self, client: AccountsPayableClient) -> None:
        """Initialize repository."""
        self._client = client

    def get_by_id(self, entity_id: str) -> Optional[Payment]:
        """Get payment by BILL ID."""
        try:
            data = self._client.get_payment(entity_id)
            if data:
                return Payment.from_bill_api(data)
        except Exception as e:
            logger.debug(f"Payment not found by ID {entity_id}: {e}")

        return None

    def get_payments_for_bill(self, bill_id: str) -> List[Payment]:
        """Get all payments for a specific bill."""
        data = self._client.get_payments_for_bill(bill_id)
        return [Payment.from_bill_api(item) for item in data]

    def get_payments_by_status(
        self,
        status: str,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Payment]:
        """Get payments by status."""
        data = self._client.list_payments(
            status=status,
            page=page,
            page_size=page_size,
        )
        return [Payment.from_bill_api(item) for item in data]

    def get_payment_options(self, bill_id: str) -> Dict[str, Any]:
        """Get available payment options for a bill."""
        return self._client.get_payment_options(bill_id)

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Payment]:
        """List payments with pagination."""
        filters = filters or {}
        bill_id = filters.get("bill_id")
        status = filters.get("status")

        data = self._client.list_payments(
            bill_id=bill_id,
            status=status,
            page=page,
            page_size=page_size,
        )

        return [Payment.from_bill_api(item) for item in data]

    def create(self, entity: Payment) -> Payment:
        """Create new payment in BILL."""
        payload = entity.to_api_payload()
        data = self._client.create_payment(payload)
        created = Payment.from_bill_api(data)

        logger.info(
            f"Created payment: {created.id} for bill {created.bill_id} "
            f"amount ${created.amount}"
        )
        return created

    def create_bulk(self, payments: List[Payment]) -> List[Payment]:
        """Create multiple payments in bulk."""
        if not payments:
            return []

        payloads = [p.to_api_payload() for p in payments]
        data = self._client.create_bulk_payments(payloads)

        # Parse results
        results = data.get("results", [])
        created_payments = []

        for result in results:
            if result.get("id"):
                created_payments.append(Payment.from_bill_api(result))

        logger.info(f"Created {len(created_payments)} bulk payments")
        return created_payments

    def record_external_payment(self, payment: ExternalPayment) -> Payment:
        """Record an external payment made outside BILL."""
        payload = payment.to_api_payload()
        data = self._client.record_external_payment(
            bill_id=payment.bill_id,
            amount=float(payment.amount),
            payment_date=payment.payment_date.strftime("%Y-%m-%d"),
            reference=payment.reference or None,
        )

        # External payments may not return full payment object
        if data and data.get("id"):
            recorded = Payment.from_bill_api(data)
        else:
            from datetime import date
            from decimal import Decimal

            from src.domain.models.payment import PaymentStatus

            recorded = Payment(
                bill_id=payment.bill_id,
                amount=payment.amount,
                process_date=payment.payment_date,
                status=PaymentStatus.COMPLETED,
                reference=payment.reference,
            )

        logger.info(
            f"Recorded external payment for bill {payment.bill_id} "
            f"amount ${payment.amount}"
        )
        return recorded

    def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancel a pending payment.

        Note: This may not be supported by all BILL API versions.
        """
        payment = self.get_by_id(payment_id)
        if not payment:
            return False

        if not payment.is_cancellable:
            logger.warning(
                f"Payment {payment_id} has status {payment.status.value}, "
                "cannot cancel"
            )
            return False

        # BILL API may not have a direct cancel endpoint
        # This would need to be implemented based on actual API capabilities
        raise NotImplementedError(
            "Payment cancellation not implemented. "
            "Check BILL API documentation for supported operations."
        )

    def update(self, entity: Payment) -> Payment:
        """Update operation not typically supported for payments."""
        raise NotImplementedError("Payment updates not supported")

    def delete(self, entity_id: str) -> bool:
        """Delete operation not supported for payments."""
        raise NotImplementedError("Payment deletion not supported")
