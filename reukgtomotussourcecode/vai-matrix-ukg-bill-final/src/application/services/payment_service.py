"""
Payment service - Orchestrates payment processing in BILL.com AP.

This service coordinates:
- Single and bulk payment creation
- External payment recording
- Payment status tracking
- MFA handling considerations
"""

import logging
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Callable
from decimal import Decimal

from src.domain.interfaces.services import (
    PaymentService as PaymentServiceInterface,
    SyncResult,
    BatchSyncResult,
)
from src.domain.interfaces.repositories import PaymentRepository, InvoiceRepository
from src.domain.models.common import PaymentMethod
from src.domain.models.payment import Payment, PaymentStatus, FundingAccount
from src.domain.models.invoice import Invoice, BillStatus


logger = logging.getLogger(__name__)


class PaymentService(PaymentServiceInterface):
    """
    Implementation of payment service.

    Manages payment operations in BILL.com Accounts Payable.
    """

    def __init__(
        self,
        payment_repository: PaymentRepository,
        invoice_repository: Optional[InvoiceRepository] = None,
        rate_limiter: Optional[Callable[[], None]] = None,
        default_funding_account_id: Optional[str] = None,
    ):
        """
        Initialize payment service.

        Args:
            payment_repository: Repository for payment data.
            invoice_repository: Optional repository for invoice updates.
            rate_limiter: Optional rate limiter callable.
            default_funding_account_id: Default funding account for payments.
        """
        self.payment_repo = payment_repository
        self.invoice_repo = invoice_repository
        self.rate_limiter = rate_limiter
        self.default_funding_account_id = default_funding_account_id

    def create_payment(
        self,
        invoice: Invoice,
        amount: Optional[float] = None,
        funding_account_id: Optional[str] = None,
    ) -> SyncResult:
        """
        Create a payment for an invoice.

        Args:
            invoice: Invoice to pay.
            amount: Payment amount (defaults to full invoice amount).
            funding_account_id: Funding account to use.

        Returns:
            SyncResult with payment details.
        """
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate invoice
            validation_errors = self._validate_payment_request(invoice, amount)
            if validation_errors:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice.id,
                    message=f"Validation failed: {', '.join(validation_errors)}",
                    details={"invoice_number": invoice.invoice_number},
                )

            # Determine payment amount
            payment_amount = amount
            if payment_amount is None:
                payment_amount = float(invoice.total_amount or 0)

            # Get funding account
            account_id = funding_account_id or self.default_funding_account_id
            if not account_id:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=invoice.id,
                    message="No funding account specified",
                )

            # Create payment
            payment = Payment(
                bill_id=invoice.id,
                vendor_id=invoice.vendor_id,
                amount=Decimal(str(payment_amount)),
                status=PaymentStatus.PENDING,
                process_date=date.today(),
                funding_account=FundingAccount(id=account_id),
            )

            created = self.payment_repo.create(payment)

            # Update invoice status if we have the repo
            if self.invoice_repo:
                self._update_invoice_status(invoice.id, BillStatus.SCHEDULED)

            logger.info(
                f"Created payment {created.id} for invoice "
                f"{invoice.invoice_number} (${payment_amount})"
            )

            return SyncResult(
                success=True,
                action="create",
                entity_id=created.id,
                message=f"Created payment for {invoice.invoice_number}",
                details={
                    "payment_id": created.id,
                    "invoice_number": invoice.invoice_number,
                    "amount": payment_amount,
                    "status": created.status.value,
                },
            )

        except Exception as e:
            logger.error(f"Failed to create payment for invoice {invoice.id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=invoice.id,
                message=str(e),
                details={"invoice_number": invoice.invoice_number},
            )

    def _validate_payment_request(
        self,
        invoice: Invoice,
        amount: Optional[float],
    ) -> List[str]:
        """Validate payment request."""
        errors = []

        if not invoice.id:
            errors.append("Invoice ID is required")

        if not invoice.vendor_id:
            errors.append("Vendor ID is required")

        # Check invoice status
        if invoice.status == BillStatus.PAID:
            errors.append("Invoice is already paid")
        elif invoice.status == BillStatus.VOIDED:
            errors.append("Cannot pay voided invoice")

        # Validate amount
        if amount is not None and amount <= 0:
            errors.append("Payment amount must be positive")

        invoice_total = invoice.total_amount or 0
        if amount is not None and amount > float(invoice_total):
            errors.append("Payment amount cannot exceed invoice total")

        return errors

    def _update_invoice_status(self, invoice_id: str, status: BillStatus) -> None:
        """Update invoice status after payment."""
        try:
            invoice = self.invoice_repo.get_by_id(invoice_id)
            if invoice:
                invoice.status = status
                self.invoice_repo.update(invoice)
        except Exception as e:
            logger.warning(f"Failed to update invoice status: {e}")

    def create_bulk_payments(
        self,
        invoices: List[Invoice],
        funding_account_id: Optional[str] = None,
    ) -> BatchSyncResult:
        """
        Create payments for multiple invoices.

        Args:
            invoices: Invoices to pay.
            funding_account_id: Funding account to use.

        Returns:
            BatchSyncResult with payment results.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"Starting bulk payment for {len(invoices)} invoices "
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

        account_id = funding_account_id or self.default_funding_account_id

        # Build bulk payment request
        payments_to_create = []
        skipped_invoices = []

        for invoice in invoices:
            validation_errors = self._validate_payment_request(invoice, None)
            if validation_errors:
                result.errors += 1
                result.results.append(
                    SyncResult(
                        success=False,
                        action="error",
                        entity_id=invoice.id,
                        message=", ".join(validation_errors),
                    )
                )
                continue

            payment = Payment(
                bill_id=invoice.id,
                vendor_id=invoice.vendor_id,
                amount=Decimal(str(invoice.total_amount or 0)),
                status=PaymentStatus.PENDING,
                process_date=date.today(),
                funding_account=FundingAccount(id=account_id) if account_id else None,
            )
            payments_to_create.append((payment, invoice))

        if not payments_to_create:
            result.end_time = datetime.now()
            return result

        # Try bulk API first, fall back to individual if not supported
        try:
            bulk_result = self.payment_repo.create_bulk(
                [p[0] for p in payments_to_create]
            )

            # Process bulk results
            for i, (payment, invoice) in enumerate(payments_to_create):
                if i < len(bulk_result):
                    created = bulk_result[i]
                    if created.id:
                        result.created += 1
                        result.results.append(
                            SyncResult(
                                success=True,
                                action="create",
                                entity_id=created.id,
                                message=f"Created payment for {invoice.invoice_number}",
                                details={
                                    "amount": float(created.amount),
                                    "status": created.status.value,
                                },
                            )
                        )

                        # Update invoice status
                        if self.invoice_repo:
                            self._update_invoice_status(
                                invoice.id,
                                BillStatus.SCHEDULED,
                            )
                    else:
                        result.errors += 1
                        result.results.append(
                            SyncResult(
                                success=False,
                                action="error",
                                entity_id=invoice.id,
                                message="Bulk payment failed for invoice",
                            )
                        )

        except NotImplementedError:
            # Fall back to individual payments
            logger.info("Bulk payment not supported, falling back to individual")
            for payment, invoice in payments_to_create:
                sync_result = self.create_payment(invoice, funding_account_id=account_id)
                result.results.append(sync_result)

                if sync_result.action == "create":
                    result.created += 1
                elif sync_result.action == "error":
                    result.errors += 1

        except Exception as e:
            logger.error(f"Bulk payment failed: {e}")
            result.errors += len(payments_to_create)
            for payment, invoice in payments_to_create:
                result.results.append(
                    SyncResult(
                        success=False,
                        action="error",
                        entity_id=invoice.id,
                        message=str(e),
                    )
                )

        result.end_time = datetime.now()

        total_amount = sum(
            float(p[0].amount) for p in payments_to_create
            if result.created > 0
        )
        logger.info(
            f"Bulk payment complete: {result.created} payments created, "
            f"{result.errors} errors, total ${total_amount:.2f} "
            f"[correlation_id={correlation_id}]"
        )

        return result

    def record_external_payment(
        self,
        bill_id: str,
        amount: float,
        payment_date: str,
        reference: Optional[str] = None,
    ) -> SyncResult:
        """
        Record a payment made outside BILL.com.

        Args:
            bill_id: BILL invoice ID.
            amount: Payment amount.
            payment_date: Date payment was made (YYYY-MM-DD).
            reference: External reference number.

        Returns:
            SyncResult with operation details.
        """
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate inputs
            if amount <= 0:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=bill_id,
                    message="Payment amount must be positive",
                )

            # Parse payment date
            try:
                pay_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
            except ValueError:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=bill_id,
                    message="Invalid payment date format (expected YYYY-MM-DD)",
                )

            # Create external payment record
            payment = Payment(
                bill_id=bill_id,
                amount=Decimal(str(amount)),
                status=PaymentStatus.COMPLETED,
                process_date=pay_date,
                payment_method=PaymentMethod.CHECK,  # External payments often via check
                reference=reference or "",
            )

            # Record via repository (this would call BILL's record-payment endpoint)
            recorded = self.payment_repo.record_external(payment)

            # Update invoice status
            if self.invoice_repo:
                self._update_invoice_status(bill_id, BillStatus.PAID)

            logger.info(
                f"Recorded external payment for invoice {bill_id}: ${amount}"
            )

            return SyncResult(
                success=True,
                action="create",
                entity_id=recorded.id if recorded else bill_id,
                message=f"Recorded external payment of ${amount}",
                details={
                    "bill_id": bill_id,
                    "amount": amount,
                    "payment_date": payment_date,
                    "reference": reference,
                },
            )

        except Exception as e:
            logger.error(f"Failed to record external payment for {bill_id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=bill_id,
                message=str(e),
            )

    def get_payment_status(self, payment_id: str) -> Payment:
        """
        Get current status of a payment.

        Args:
            payment_id: Payment ID.

        Returns:
            Payment with current status.

        Raises:
            ValueError: If payment not found.
        """
        if self.rate_limiter:
            self.rate_limiter()

        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")

        return payment

    def get_pending_payments(self) -> List[Payment]:
        """
        Get all pending payments.

        Returns:
            List of payments with PENDING status.
        """
        payments = []
        page = 1

        while True:
            batch = self.payment_repo.list(
                page=page,
                page_size=200,
                filters={"status": PaymentStatus.PENDING.value},
            )
            if not batch:
                break

            payments.extend(batch)

            if len(batch) < 200:
                break
            page += 1

        return payments

    def get_completed_payments(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Payment]:
        """
        Get completed payments within date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            List of completed payments.
        """
        payments = []
        page = 1

        filters = {"status": PaymentStatus.COMPLETED.value}
        if start_date:
            filters["start_date"] = start_date.isoformat()
        if end_date:
            filters["end_date"] = end_date.isoformat()

        while True:
            batch = self.payment_repo.list(
                page=page,
                page_size=200,
                filters=filters,
            )
            if not batch:
                break

            payments.extend(batch)

            if len(batch) < 200:
                break
            page += 1

        return payments

    def cancel_payment(self, payment_id: str, reason: str = "") -> SyncResult:
        """
        Cancel a pending payment.

        Args:
            payment_id: Payment ID to cancel.
            reason: Reason for cancellation.

        Returns:
            SyncResult with operation details.
        """
        try:
            payment = self.payment_repo.get_by_id(payment_id)
            if not payment:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=payment_id,
                    message="Payment not found",
                )

            # Check if payment can be cancelled
            if payment.status != PaymentStatus.PENDING:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=payment_id,
                    message=f"Cannot cancel payment with status {payment.status.value}",
                )

            # Cancel payment
            payment.status = PaymentStatus.CANCELLED
            updated = self.payment_repo.update(payment)

            # Reset invoice status if we have the repo
            if self.invoice_repo and payment.bill_id:
                self._update_invoice_status(payment.bill_id, BillStatus.APPROVED)

            logger.info(f"Cancelled payment {payment_id}")

            return SyncResult(
                success=True,
                action="update",
                entity_id=payment_id,
                message="Payment cancelled",
                details={"reason": reason},
            )

        except Exception as e:
            logger.error(f"Failed to cancel payment {payment_id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=payment_id,
                message=str(e),
            )
