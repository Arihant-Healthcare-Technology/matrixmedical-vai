"""
Invoice service - Orchestrates invoice/bill management in BILL.com AP.

This service coordinates:
- Invoice creation and updates
- Vendor mapping resolution
- Batch invoice operations
- Invoice status tracking
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from src.domain.interfaces.services import (
    InvoiceSyncService,
    SyncResult,
    BatchSyncResult,
)
from src.domain.interfaces.repositories import InvoiceRepository, VendorRepository
from src.domain.models.invoice import Invoice, BillStatus


logger = logging.getLogger(__name__)


class InvoiceService(InvoiceSyncService):
    """
    Implementation of invoice sync service.

    Manages invoice/bill operations in BILL.com Accounts Payable.
    """

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        vendor_repository: Optional[VendorRepository] = None,
        rate_limiter: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize invoice service.

        Args:
            invoice_repository: Repository for invoice data.
            vendor_repository: Optional repository for vendor lookups.
            rate_limiter: Optional rate limiter callable.
        """
        self.invoice_repo = invoice_repository
        self.vendor_repo = vendor_repository
        self.rate_limiter = rate_limiter
        self._invoice_cache: Dict[str, Invoice] = {}

    def sync_invoice(
        self,
        invoice: Invoice,
        vendor_mapping: Optional[Dict[str, str]] = None,
    ) -> SyncResult:
        """
        Sync an invoice to BILL.com.

        Args:
            invoice: Invoice to sync.
            vendor_mapping: Optional external vendor ID to BILL vendor ID mapping.

        Returns:
            SyncResult with operation details.
        """
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate invoice
            validation_errors = self._validate_invoice(invoice)
            if validation_errors:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice.id,
                    message=f"Validation failed: {', '.join(validation_errors)}",
                    details={"invoice_number": invoice.invoice_number},
                )

            # Resolve vendor ID if mapping provided
            if vendor_mapping and invoice.vendor_id in vendor_mapping:
                invoice.vendor_id = vendor_mapping[invoice.vendor_id]

            # Check if invoice already exists
            existing = self._find_existing_invoice(invoice)

            if existing:
                return self._update_invoice(existing, invoice)
            else:
                return self._create_invoice(invoice)

        except Exception as e:
            logger.error(f"Error syncing invoice {invoice.invoice_number}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=invoice.id,
                message=str(e),
                details={"invoice_number": invoice.invoice_number},
            )

    def _validate_invoice(self, invoice: Invoice) -> List[str]:
        """Validate invoice has required fields."""
        errors = []

        if not invoice.invoice_number:
            errors.append("Missing invoice number")

        if not invoice.vendor_id:
            errors.append("Missing vendor ID")

        if not invoice.line_items or len(invoice.line_items) == 0:
            errors.append("Invoice must have at least one line item")

        # Calculate total if not set
        total = invoice.total_amount
        if total is None and invoice.line_items:
            total = sum(item.amount for item in invoice.line_items)

        if total is None or total <= 0:
            errors.append("Invoice total must be positive")

        return errors

    def _find_existing_invoice(self, invoice: Invoice) -> Optional[Invoice]:
        """Find existing invoice by ID, external ID, or invoice number."""
        # Try by BILL invoice ID first
        if invoice.id:
            cached = self._invoice_cache.get(invoice.id)
            if cached:
                return cached

            existing = self.invoice_repo.get_by_id(invoice.id)
            if existing:
                self._invoice_cache[invoice.id] = existing
                return existing

        # Try by external ID
        if invoice.external_id:
            existing = self.invoice_repo.get_by_external_id(invoice.external_id)
            if existing:
                self._invoice_cache[existing.id] = existing
                return existing

        # Try by invoice number and vendor
        existing = self.invoice_repo.get_by_invoice_number(
            invoice.invoice_number,
            invoice.vendor_id,
        )
        if existing:
            self._invoice_cache[existing.id] = existing
            return existing

        return None

    def _create_invoice(self, invoice: Invoice) -> SyncResult:
        """Create a new invoice in BILL.com."""
        try:
            created = self.invoice_repo.create(invoice)
            self._invoice_cache[created.id] = created

            logger.info(
                f"Created invoice: {created.invoice_number} "
                f"(ID: {created.id})"
            )
            return SyncResult(
                success=True,
                action="create",
                entity_id=created.id,
                message=f"Created invoice {created.invoice_number}",
                details={
                    "invoice_number": created.invoice_number,
                    "vendor_id": created.vendor_id,
                    "amount": float(created.total_amount) if created.total_amount else 0,
                },
            )
        except Exception as e:
            logger.error(f"Failed to create invoice {invoice.invoice_number}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=invoice.id,
                message=f"Failed to create invoice: {e}",
                details={"invoice_number": invoice.invoice_number},
            )

    def _update_invoice(
        self,
        existing: Invoice,
        updated: Invoice,
    ) -> SyncResult:
        """Update an existing invoice."""
        try:
            # Check if update is needed
            if self._invoices_match(existing, updated):
                logger.debug(f"Invoice {existing.invoice_number} unchanged, skipping")
                return SyncResult(
                    success=True,
                    action="skip",
                    entity_id=existing.id,
                    message="No changes detected",
                    details={"invoice_number": existing.invoice_number},
                )

            # Check if invoice can be updated (not paid/voided)
            if existing.status in [BillStatus.PAID, BillStatus.VOIDED]:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=existing.id,
                    message=f"Cannot update invoice with status {existing.status.value}",
                    details={"invoice_number": existing.invoice_number},
                )

            # Preserve existing ID
            updated.id = existing.id

            result = self.invoice_repo.update(updated)
            self._invoice_cache[result.id] = result

            logger.info(f"Updated invoice: {result.invoice_number}")
            return SyncResult(
                success=True,
                action="update",
                entity_id=result.id,
                message=f"Updated invoice {result.invoice_number}",
                details={
                    "invoice_number": result.invoice_number,
                    "changes": self._get_changes(existing, updated),
                },
            )
        except Exception as e:
            logger.error(f"Failed to update invoice {existing.invoice_number}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=existing.id,
                message=f"Failed to update invoice: {e}",
                details={"invoice_number": existing.invoice_number},
            )

    def _invoices_match(self, existing: Invoice, updated: Invoice) -> bool:
        """Check if two invoices have matching data."""
        existing_total = existing.total_amount or 0
        updated_total = updated.total_amount or 0

        return (
            existing.invoice_number == updated.invoice_number
            and existing.vendor_id == updated.vendor_id
            and float(existing_total) == float(updated_total)
            and existing.due_date == updated.due_date
        )

    def _get_changes(
        self,
        existing: Invoice,
        updated: Invoice,
    ) -> Dict[str, Any]:
        """Get dictionary of changed fields."""
        changes = {}

        if existing.invoice_number != updated.invoice_number:
            changes["invoice_number"] = {
                "old": existing.invoice_number,
                "new": updated.invoice_number,
            }

        existing_total = existing.total_amount or 0
        updated_total = updated.total_amount or 0
        if float(existing_total) != float(updated_total):
            changes["total_amount"] = {
                "old": float(existing_total),
                "new": float(updated_total),
            }

        if existing.due_date != updated.due_date:
            changes["due_date"] = {
                "old": existing.due_date.isoformat() if existing.due_date else None,
                "new": updated.due_date.isoformat() if updated.due_date else None,
            }

        return changes

    def sync_batch(
        self,
        invoices: List[Invoice],
        vendor_mapping: Optional[Dict[str, str]] = None,
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync multiple invoices to BILL.com.

        Args:
            invoices: List of invoices to sync.
            vendor_mapping: Optional vendor ID mapping.
            workers: Number of concurrent workers.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"Starting batch invoice sync of {len(invoices)} invoices "
            f"[correlation_id={correlation_id}]"
        )

        result = BatchSyncResult(
            total=len(invoices),
            correlation_id=correlation_id,
            start_time=datetime.now(),
        )

        if not invoices:
            result.end_time = datetime.now()
            return result

        # Process in parallel
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.sync_invoice, inv, vendor_mapping): inv
                for inv in invoices
            }

            for future in as_completed(futures):
                invoice = futures[future]
                try:
                    sync_result = future.result()
                    result.results.append(sync_result)

                    if sync_result.action == "create":
                        result.created += 1
                    elif sync_result.action == "update":
                        result.updated += 1
                    elif sync_result.action == "skip":
                        result.skipped += 1
                    elif sync_result.action == "error":
                        result.errors += 1

                except Exception as e:
                    logger.error(
                        f"Unexpected error syncing invoice "
                        f"{invoice.invoice_number}: {e}"
                    )
                    result.errors += 1
                    result.results.append(
                        SyncResult(
                            success=False,
                            action="error",
                            entity_id=invoice.id,
                            message=str(e),
                        )
                    )

        result.end_time = datetime.now()

        logger.info(
            f"Invoice batch sync complete: {result.created} created, "
            f"{result.updated} updated, {result.skipped} skipped, "
            f"{result.errors} errors [correlation_id={correlation_id}]"
        )

        return result

    def get_payable_invoices(
        self,
        vendor_id: Optional[str] = None,
    ) -> List[Invoice]:
        """
        Get all invoices ready for payment.

        Returns invoices with status APPROVED or SCHEDULED.

        Args:
            vendor_id: Optional vendor filter.

        Returns:
            List of payable invoices.
        """
        payable_statuses = [BillStatus.APPROVED, BillStatus.SCHEDULED]
        invoices = []
        page = 1

        while True:
            filters = {}
            if vendor_id:
                filters["vendor_id"] = vendor_id

            batch = self.invoice_repo.list(page=page, page_size=200, filters=filters)
            if not batch:
                break

            # Filter for payable statuses
            payable = [inv for inv in batch if inv.status in payable_statuses]
            invoices.extend(payable)

            if len(batch) < 200:
                break
            page += 1

        return invoices

    def get_overdue_invoices(self) -> List[Invoice]:
        """
        Get all overdue invoices.

        Returns:
            List of invoices past due date.
        """
        today = datetime.now().date()
        invoices = []
        page = 1

        while True:
            batch = self.invoice_repo.list(page=page, page_size=200)
            if not batch:
                break

            # Filter for overdue (due date < today and not paid)
            overdue = [
                inv for inv in batch
                if inv.due_date
                and inv.due_date < today
                and inv.status not in [BillStatus.PAID, BillStatus.VOIDED]
            ]
            invoices.extend(overdue)

            if len(batch) < 200:
                break
            page += 1

        return invoices

    def void_invoice(self, invoice_id: str, reason: str = "") -> SyncResult:
        """
        Void an invoice.

        Args:
            invoice_id: Invoice ID to void.
            reason: Optional reason for voiding.

        Returns:
            SyncResult with operation details.
        """
        try:
            invoice = self.invoice_repo.get_by_id(invoice_id)
            if not invoice:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice_id,
                    message="Invoice not found",
                )

            # Check if invoice can be voided
            if invoice.status in [BillStatus.PAID, BillStatus.VOIDED]:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice_id,
                    message=f"Cannot void invoice with status {invoice.status.value}",
                )

            invoice.status = BillStatus.VOIDED
            updated = self.invoice_repo.update(invoice)

            # Update cache
            if invoice_id in self._invoice_cache:
                del self._invoice_cache[invoice_id]

            logger.info(f"Voided invoice: {updated.invoice_number}")
            return SyncResult(
                success=True,
                action="update",
                entity_id=invoice_id,
                message=f"Voided invoice {updated.invoice_number}",
                details={"reason": reason},
            )
        except Exception as e:
            logger.error(f"Failed to void invoice {invoice_id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=invoice_id,
                message=str(e),
            )

    def approve_invoice(self, invoice_id: str) -> SyncResult:
        """
        Approve an invoice for payment.

        Args:
            invoice_id: Invoice ID to approve.

        Returns:
            SyncResult with operation details.
        """
        try:
            invoice = self.invoice_repo.get_by_id(invoice_id)
            if not invoice:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice_id,
                    message="Invoice not found",
                )

            # Check if invoice can be approved
            if invoice.status != BillStatus.OPEN:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice_id,
                    message=f"Cannot approve invoice with status {invoice.status.value}",
                )

            invoice.status = BillStatus.APPROVED
            updated = self.invoice_repo.update(invoice)
            self._invoice_cache[invoice_id] = updated

            logger.info(f"Approved invoice: {updated.invoice_number}")
            return SyncResult(
                success=True,
                action="update",
                entity_id=invoice_id,
                message=f"Approved invoice {updated.invoice_number}",
            )
        except Exception as e:
            logger.error(f"Failed to approve invoice {invoice_id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=invoice_id,
                message=str(e),
            )
