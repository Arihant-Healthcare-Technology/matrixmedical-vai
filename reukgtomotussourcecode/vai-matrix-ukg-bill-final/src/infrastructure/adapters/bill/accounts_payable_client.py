"""
BILL.com Accounts Payable API client.

This module provides the AP API client for vendor, bill, and payment management.
"""

import logging
from typing import Any, Dict, List, Optional

from src.infrastructure.adapters.bill.base_client import BillClient
from src.infrastructure.config.constants import (
    BATCH_TIMEOUT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class AccountsPayableClient(BillClient):
    """
    BILL.com Accounts Payable API client.

    Provides operations for AP vendor, bill, and payment management.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """Initialize AP client."""
        # Remove /spend suffix if present (AP uses base v3 endpoint)
        if api_base.endswith("/spend"):
            api_base = api_base[:-6]

        super().__init__(
            api_base=api_base,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )

    # =========================================================================
    # Vendor Operations
    # =========================================================================

    def list_vendors(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List vendors with optional status filter."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status

        response = self._http.get("/vendors", params=params)
        data = self._handle_response(response)
        return self._extract_items(data, ["vendors", "items", "data"])

    def get_vendor(self, vendor_id: str) -> Dict[str, Any]:
        """Get vendor by ID."""
        response = self._http.get(f"/vendors/{vendor_id}")
        return self._handle_response(response)

    def get_vendor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find vendor by name (exact match)."""
        name_lower = name.lower().strip()

        for vendor in self._paginate("/vendors", item_keys=["vendors"]):
            if vendor.get("name", "").lower().strip() == name_lower:
                return vendor

        return None

    def get_vendor_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Find vendor by external ID."""
        for vendor in self._paginate("/vendors", item_keys=["vendors"]):
            if vendor.get("externalId") == external_id:
                return vendor

        return None

    def create_vendor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new vendor."""
        name = payload.get("name", "unknown")
        logger.info(f"BILL AP creating vendor: name={name}")
        response = self._http.post("/vendors", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201])
        vendor_id = result.get("id")
        logger.info(f"BILL AP vendor created: id={vendor_id} name={name}")
        return result

    def update_vendor(self, vendor_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing vendor."""
        logger.info(f"BILL AP updating vendor: id={vendor_id}")
        response = self._http.patch(f"/vendors/{vendor_id}", json=payload)
        result = self._handle_response(response, [200, 204])
        logger.info(f"BILL AP vendor updated: id={vendor_id}")
        return result

    def get_all_vendors(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all vendors (paginated)."""
        params = {"status": status} if status else {}
        return self._paginate("/vendors", params=params, item_keys=["vendors"])

    # =========================================================================
    # Bill Operations
    # =========================================================================

    def list_bills(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List bills with optional filters."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if vendor_id:
            params["vendorId"] = vendor_id
        if status:
            params["status"] = status

        response = self._http.get("/bills", params=params)
        data = self._handle_response(response)
        return self._extract_items(data, ["bills", "items", "data"])

    def get_bill(self, bill_id: str) -> Dict[str, Any]:
        """Get bill by ID."""
        response = self._http.get(f"/bills/{bill_id}")
        return self._handle_response(response)

    def get_bill_by_invoice_number(
        self,
        invoice_number: str,
        vendor_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find bill by invoice number."""
        invoice_lower = invoice_number.lower().strip()
        params = {"vendorId": vendor_id} if vendor_id else {}

        for bill in self._paginate("/bills", params=params, item_keys=["bills"]):
            invoice = bill.get("invoice", {}) or {}
            if invoice.get("number", "").lower().strip() == invoice_lower:
                if vendor_id and bill.get("vendorId") != vendor_id:
                    continue
                return bill

        return None

    def get_bill_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Find bill by external ID."""
        for bill in self._paginate("/bills", item_keys=["bills"]):
            if bill.get("externalId") == external_id:
                return bill

        return None

    def create_bill(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new bill."""
        vendor_id = payload.get("vendorId", "unknown")
        logger.info(f"BILL AP creating bill: vendorId={vendor_id}")
        response = self._http.post("/bills", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201])
        bill_id = result.get("id")
        logger.info(f"BILL AP bill created: id={bill_id} vendorId={vendor_id}")
        return result

    def update_bill(self, bill_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing bill."""
        logger.info(f"BILL AP updating bill: id={bill_id}")
        response = self._http.patch(f"/bills/{bill_id}", json=payload)
        result = self._handle_response(response, [200, 204])
        logger.info(f"BILL AP bill updated: id={bill_id}")
        return result

    def get_bills_for_vendor(
        self,
        vendor_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all bills for a vendor."""
        params: Dict[str, Any] = {"vendorId": vendor_id}
        if status:
            params["status"] = status
        return self._paginate("/bills", params=params, item_keys=["bills"])

    # =========================================================================
    # Payment Operations
    # =========================================================================

    def get_payment_options(self, bill_id: str) -> Dict[str, Any]:
        """Get available payment options for a bill."""
        params = {"billId": bill_id}
        response = self._http.get("/payments/options", params=params)
        return self._handle_response(response)

    def create_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create single payment."""
        bill_id = payload.get("billId", "unknown")
        logger.info(f"BILL AP creating payment: billId={bill_id}")
        response = self._http.post("/payments", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201])
        payment_id = result.get("id")
        logger.info(f"BILL AP payment created: id={payment_id} billId={bill_id}")
        return result

    def create_bulk_payments(
        self,
        payments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create bulk payments."""
        logger.info(f"BILL AP creating bulk payments: count={len(payments)}")
        payload = {"payments": payments}
        response = self._http.post(
            "/payments/bulk",
            json=payload,
            timeout=120,  # Longer timeout for bulk
        )
        result = self._handle_response(response, [200, 201])
        logger.info(f"BILL AP bulk payments created: count={len(payments)}")
        return result

    def record_external_payment(
        self,
        bill_id: str,
        amount: float,
        payment_date: str,
        reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record external payment made outside BILL."""
        logger.info(f"BILL AP recording external payment: billId={bill_id} amount={amount}")
        payload: Dict[str, Any] = {
            "billId": bill_id,
            "amount": amount,
            "paymentDate": payment_date,
        }
        if reference:
            payload["reference"] = reference

        response = self._http.post(
            "/bills/record-payment",
            json=payload,
            timeout=BATCH_TIMEOUT,
        )
        result = self._handle_response(response, [200, 201, 204])
        logger.info(f"BILL AP external payment recorded: billId={bill_id}")
        return result

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Get payment by ID."""
        response = self._http.get(f"/payments/{payment_id}")
        return self._handle_response(response)

    def list_payments(
        self,
        bill_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """List payments with optional filters."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if bill_id:
            params["billId"] = bill_id
        if status:
            params["status"] = status

        response = self._http.get("/payments", params=params)
        data = self._handle_response(response)
        return self._extract_items(data, ["payments", "items", "data"])

    def get_payments_for_bill(self, bill_id: str) -> List[Dict[str, Any]]:
        """Get all payments for a bill."""
        return self._paginate(
            "/payments",
            params={"billId": bill_id},
            item_keys=["payments"],
        )
