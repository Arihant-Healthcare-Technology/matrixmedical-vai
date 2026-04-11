"""
BILL.com Accounts Payable payment repository implementation.

This module implements the PaymentRepository interface using the AP API client.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import PaymentRepository
from src.domain.models.payment import ExternalPayment, Payment, PaymentStatus
from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient

logger = logging.getLogger(__name__)


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
