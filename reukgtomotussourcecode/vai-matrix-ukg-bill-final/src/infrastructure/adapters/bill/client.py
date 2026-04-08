"""
BILL.com API base client adapter.

This module provides the base BILL.com API client that is extended
by the S&E and AP adapters.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from src.infrastructure.config.constants import (
    BATCH_TIMEOUT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
)
from src.infrastructure.http.client import BillHttpClient
from src.infrastructure.http.response import safe_json

logger = logging.getLogger(__name__)


class BillClient:
    """
    Base BILL.com API client.

    Provides common functionality for BILL API operations.
    Extended by SpendExpenseClient and AccountsPayableClient.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """
        Initialize BILL client.

        Args:
            api_base: BILL API base URL
            api_token: BILL API token
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limiter: Optional rate limiter
        """
        if not api_token:
            raise ConfigurationError(
                "Missing BILL API token",
                config_key="BILL_API_TOKEN",
            )

        self._http = BillHttpClient(
            api_base=api_base,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )
        self._api_base = api_base

    def _handle_response(
        self,
        response: Any,
        expected_status: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Handle API response and convert to dict.

        Args:
            response: HTTP response object
            expected_status: List of expected status codes

        Returns:
            Response data as dict

        Raises:
            AuthenticationError: For 401/403 responses
            NotFoundError: For 404 responses
            RateLimitError: For 429 responses
            ApiError: For other error responses
        """
        expected = expected_status or [200, 201, 204]

        if response.status_code in expected:
            if response.status_code == 204:
                return {}
            return safe_json(response)

        # Handle error responses
        error_data = safe_json(response)
        error_message = self._extract_error_message(error_data)

        if response.status_code == 401:
            raise AuthenticationError(
                message=f"BILL API authentication failed: {error_message}",
                auth_type="api_token",
            )
        elif response.status_code == 403:
            raise AuthenticationError(
                message=f"BILL API access denied: {error_message}",
                auth_type="api_token",
            )
        elif response.status_code == 404:
            raise NotFoundError(
                message=f"Resource not found: {error_message}",
                status_code=404,
            )
        elif response.status_code == 429:
            raise RateLimitError(
                message=f"BILL API rate limit exceeded: {error_message}",
                limit=60,
                window_seconds=60,
            )
        else:
            raise ApiError(
                message=f"BILL API error: {error_message}",
                status_code=response.status_code,
                response_body=error_data,
            )

    @staticmethod
    def _extract_error_message(error_data: Dict[str, Any]) -> str:
        """Extract error message from API response."""
        if isinstance(error_data, dict):
            return (
                error_data.get("message")
                or error_data.get("error")
                or error_data.get("errorMessage")
                or error_data.get("_raw_text", "")[:200]
                or str(error_data)[:200]
            )
        return str(error_data)[:200]

    def _extract_items(
        self,
        data: Any,
        item_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract items list from varying API response formats.

        BILL API returns items in different formats:
        - Direct list
        - {"items": [...]}
        - {"data": [...]}
        - {"users": [...]}
        - etc.

        Args:
            data: Response data
            item_keys: List of keys to check for items

        Returns:
            List of items
        """
        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            return []

        # Check common keys
        keys_to_check = item_keys or [
            "items",
            "data",
            "content",
            "values",
            "results",
        ]

        for key in keys_to_check:
            val = data.get(key)
            if isinstance(val, list):
                return val

        # Single object with ID
        if data.get("id") or data.get("uuid"):
            return [data]

        return []

    def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        item_keys: Optional[List[str]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginate through API results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            item_keys: Keys to extract items from response
            page_size: Page size
            max_pages: Maximum pages to fetch (None = all)

        Returns:
            All items from all pages
        """
        all_items = []
        page = 1
        params = params or {}

        while True:
            page_params = {**params, "page": page, "pageSize": page_size}
            response = self._http.get(endpoint, params=page_params)
            data = self._handle_response(response)
            items = self._extract_items(data, item_keys)

            all_items.extend(items)

            # Check if we have more pages
            if len(items) < page_size:
                break

            if max_pages and page >= max_pages:
                break

            page += 1

        return all_items

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> "BillClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class SpendExpenseClient(BillClient):
    """
    BILL.com Spend & Expense API client.

    Provides operations for S&E user management.
    """

    def __init__(
        self,
        api_base: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        rate_limiter: Optional[Any] = None,
    ) -> None:
        """Initialize S&E client."""
        # Ensure we're using the S&E endpoint
        if not api_base.endswith("/spend"):
            api_base = api_base.rstrip("/") + "/spend"

        super().__init__(
            api_base=api_base,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )

    # User Operations

    def list_users(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """
        List all S&E users.

        Args:
            page: Page number
            page_size: Page size

        Returns:
            List of user dicts
        """
        params = {"page": page, "pageSize": page_size}
        response = self._http.get("/users", params=params)
        data = self._handle_response(response)
        return self._extract_items(data, ["users", "items", "data"])

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get S&E user by ID.

        Args:
            user_id: User UUID

        Returns:
            User dict
        """
        response = self._http.get(f"/users/{user_id}")
        return self._handle_response(response)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find S&E user by email.

        Args:
            email: User email

        Returns:
            User dict or None if not found
        """
        email_lower = email.lower().strip()

        # Paginate through all users
        for user in self._paginate("/users", item_keys=["users"]):
            if user.get("email", "").lower().strip() == email_lower:
                return user

        return None

    def create_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new S&E user.

        Args:
            payload: User creation payload

        Returns:
            Created user dict
        """
        email = payload.get("email", "unknown")
        logger.info(f"BILL S&E creating user: email={email}")
        response = self._http.post("/users", json=payload, timeout=BATCH_TIMEOUT)
        result = self._handle_response(response, [200, 201])
        user_id = result.get("uuid") or result.get("id")
        logger.info(f"BILL S&E user created: id={user_id} email={email}")
        return result

    def update_user(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing S&E user.

        Args:
            user_id: User UUID
            payload: Update payload

        Returns:
            Updated user dict
        """
        logger.info(f"BILL S&E updating user: id={user_id}")
        response = self._http.patch(f"/users/{user_id}", json=payload)
        result = self._handle_response(response, [200, 204])
        logger.info(f"BILL S&E user updated: id={user_id}")
        return result

    def retire_user(self, user_id: str) -> bool:
        """
        Retire (deactivate) S&E user.

        Note: In BILL S&E, you retire users via DELETE endpoint.

        Args:
            user_id: User UUID

        Returns:
            True if retired successfully
        """
        logger.info(f"BILL S&E retiring user: id={user_id}")
        response = self._http.delete(f"/users/{user_id}")
        self._handle_response(response, [200, 204])
        logger.info(f"BILL S&E user retired: id={user_id}")
        return True

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all S&E users (paginated)."""
        return self._paginate("/users", item_keys=["users"])


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
