"""
Integration tests for BILL.com Accounts Payable API client.

Tests verify BILL AP client behavior with mocked HTTP responses.
Run with: pytest tests/integration/test_bill_ap_integration.py -v -m integration
"""
from unittest.mock import MagicMock

import pytest
import responses

from src.infrastructure.adapters.bill.accounts_payable import BillAccountsPayableClient
from src.domain.exceptions.api_exceptions import BillApiError


@pytest.mark.integration
class TestBillAPAuthentication:
    """Test BILL AP client authentication."""

    def test_bill_ap_authentication_valid_token(self, mock_bill_ap_settings):
        """Test authentication with valid API token."""
        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        headers = client._headers()

        assert "apiToken" in headers
        assert headers["apiToken"] == "test_ap_token"

    def test_bill_ap_authentication_missing_token_raises_error(self):
        """Test that missing API token raises error."""
        settings = MagicMock()
        settings.api_base = "https://gateway.stage.bill.com/connect/v3"
        settings.api_token = MagicMock()
        settings.api_token.get_secret_value.return_value = ""
        settings.timeout = 30.0

        with pytest.raises(BillApiError, match="Missing BILL_AP_API_TOKEN"):
            client = BillAccountsPayableClient(settings=settings)
            client._headers()


@pytest.mark.integration
class TestBillAPVendorOperations:
    """Test BILL AP vendor operations."""

    @responses.activate
    def test_bill_ap_create_vendor(
        self, mock_bill_ap_settings, sample_vendor_response,
        sample_vendor_create_payload, bill_ap_base_url
    ):
        """Test creating a new vendor."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/vendors",
            json=sample_vendor_response,
            status=201,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.create_vendor(sample_vendor_create_payload)

        assert result is not None
        assert result["name"] == "Acme Corporation"

    @responses.activate
    def test_bill_ap_get_vendor_by_id(
        self, mock_bill_ap_settings, sample_vendor_response, bill_ap_base_url
    ):
        """Test fetching vendor by ID."""
        vendor_id = sample_vendor_response["id"]
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json=sample_vendor_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_vendor_by_id(vendor_id)

        assert result is not None
        assert result["id"] == vendor_id

    @responses.activate
    def test_bill_ap_get_vendor_by_name(
        self, mock_bill_ap_settings, sample_vendor_response, bill_ap_base_url
    ):
        """Test fetching vendor by name."""
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors",
            json={"vendors": [sample_vendor_response]},
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_vendor_by_name("Acme Corporation")

        assert result is not None
        assert result["name"] == "Acme Corporation"

    @responses.activate
    def test_bill_ap_get_vendor_not_found(
        self, mock_bill_ap_settings, bill_ap_base_url
    ):
        """Test fetching vendor when not found."""
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/nonexistent",
            json={"error": "Vendor not found"},
            status=404,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_vendor_by_id("nonexistent")

        assert result is None

    @responses.activate
    def test_bill_ap_update_vendor(
        self, mock_bill_ap_settings, sample_vendor_response, bill_ap_base_url
    ):
        """Test updating an existing vendor."""
        vendor_id = sample_vendor_response["id"]
        updated_response = {**sample_vendor_response, "phone": "555-999-9999"}
        responses.add(
            responses.PATCH,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json=updated_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.update_vendor(vendor_id, {"phone": "555-999-9999"})

        assert result["phone"] == "555-999-9999"


@pytest.mark.integration
class TestBillAPBillOperations:
    """Test BILL AP bill/invoice operations."""

    @responses.activate
    def test_bill_ap_create_bill(
        self, mock_bill_ap_settings, sample_bill_response,
        sample_bill_create_payload, bill_ap_base_url
    ):
        """Test creating a new bill/invoice."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/bills",
            json=sample_bill_response,
            status=201,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.create_bill(sample_bill_create_payload)

        assert result is not None
        assert result["invoice"]["number"] == "INV-2024-001"

    @responses.activate
    def test_bill_ap_get_bill_by_id(
        self, mock_bill_ap_settings, sample_bill_response, bill_ap_base_url
    ):
        """Test fetching bill by ID."""
        bill_id = sample_bill_response["id"]
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/bills/{bill_id}",
            json=sample_bill_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_bill_by_id(bill_id)

        assert result is not None
        assert result["id"] == bill_id

    @responses.activate
    def test_bill_ap_get_bills_by_vendor(
        self, mock_bill_ap_settings, sample_bill_response, bill_ap_base_url
    ):
        """Test fetching bills by vendor ID."""
        vendor_id = sample_bill_response["vendorId"]
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/bills",
            json={"bills": [sample_bill_response]},
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_bills_by_vendor(vendor_id)

        assert len(result) > 0
        assert result[0]["vendorId"] == vendor_id

    @responses.activate
    def test_bill_ap_create_bill_validation_error(
        self, mock_bill_ap_settings, bill_ap_base_url
    ):
        """Test creating bill with validation error."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/bills",
            json={"error": "Missing required field: vendorId"},
            status=400,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.create_bill({"invoice": {"number": "INV-001"}})

        assert exc_info.value.status_code == 400


@pytest.mark.integration
class TestBillAPPaymentOperations:
    """Test BILL AP payment operations."""

    @responses.activate
    def test_bill_ap_create_payment(
        self, mock_bill_ap_settings, sample_payment_response, bill_ap_base_url
    ):
        """Test creating a new payment."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/payments",
            json=sample_payment_response,
            status=201,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.create_payment({
            "billId": "00501000000BILXX",
            "amount": 1500.00,
            "processDate": "2024-04-15",
        })

        assert result is not None
        assert result["amount"] == "1500.00"

    @responses.activate
    def test_bill_ap_record_external_payment(
        self, mock_bill_ap_settings, bill_ap_base_url
    ):
        """Test recording an external payment."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/bills/record-payment",
            json={"success": True, "billId": "00501000000BILXX"},
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.record_external_payment({
            "billId": "00501000000BILXX",
            "amount": 1500.00,
            "paymentDate": "2024-04-15",
            "referenceNumber": "CHK-12345",
        })

        assert result["success"] is True

    @responses.activate
    def test_bill_ap_create_payment_mfa_required(
        self, mock_bill_ap_settings, bill_ap_base_url
    ):
        """Test payment creation when MFA is required."""
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/payments",
            json={"error": "MFA verification required"},
            status=403,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.create_payment({
                "billId": "00501000000BILXX",
                "amount": 1500.00,
            })

        assert exc_info.value.status_code == 403


@pytest.mark.integration
class TestBillAPRateLimiting:
    """Test BILL AP rate limiting behavior."""

    @responses.activate
    def test_bill_ap_rate_limiting_429(
        self, mock_bill_ap_settings, sample_vendor_response, bill_ap_base_url
    ):
        """Test handling of 429 Too Many Requests."""
        vendor_id = sample_vendor_response["id"]

        # First request returns 429
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json={"error": "Too Many Requests"},
            status=429,
            headers={"Retry-After": "1"},
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json=sample_vendor_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_vendor_by_id(vendor_id)

        assert result is not None
        assert len(responses.calls) == 2


@pytest.mark.integration
class TestBillAPErrorHandling:
    """Test BILL AP error handling."""

    @responses.activate
    def test_bill_ap_unauthorized(
        self, mock_bill_ap_settings, bill_ap_base_url
    ):
        """Test handling of 401 Unauthorized."""
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors",
            json={"error": "Invalid API token"},
            status=401,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)

        with pytest.raises(BillApiError) as exc_info:
            client.list_vendors()

        assert exc_info.value.status_code == 401

    @responses.activate
    def test_bill_ap_server_error_with_retry(
        self, mock_bill_ap_settings, sample_vendor_response, bill_ap_base_url
    ):
        """Test retry on 500 server error."""
        vendor_id = sample_vendor_response["id"]

        # First request returns 500
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json={"error": "Internal Server Error"},
            status=500,
        )
        # Retry succeeds
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json=sample_vendor_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.get_vendor_by_id(vendor_id)

        assert result is not None


@pytest.mark.integration
class TestBillAPUpsertOperations:
    """Test BILL AP upsert operations."""

    @responses.activate
    def test_bill_ap_upsert_vendor_create(
        self, mock_bill_ap_settings, sample_vendor_response,
        sample_vendor_create_payload, bill_ap_base_url
    ):
        """Test upsert creates vendor when not exists."""
        # Check by external ID returns empty
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors",
            json={"vendors": []},
            status=200,
        )
        # Create vendor
        responses.add(
            responses.POST,
            f"{bill_ap_base_url}/vendors",
            json=sample_vendor_response,
            status=201,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.upsert_vendor(sample_vendor_create_payload)

        assert result["action"] == "created"

    @responses.activate
    def test_bill_ap_upsert_vendor_update(
        self, mock_bill_ap_settings, sample_vendor_response,
        sample_vendor_create_payload, bill_ap_base_url
    ):
        """Test upsert updates vendor when exists."""
        vendor_id = sample_vendor_response["id"]

        # Check by external ID returns vendor
        responses.add(
            responses.GET,
            f"{bill_ap_base_url}/vendors",
            json={"vendors": [sample_vendor_response]},
            status=200,
        )
        # Update vendor
        responses.add(
            responses.PATCH,
            f"{bill_ap_base_url}/vendors/{vendor_id}",
            json=sample_vendor_response,
            status=200,
        )

        client = BillAccountsPayableClient(settings=mock_bill_ap_settings)
        result = client.upsert_vendor(sample_vendor_create_payload)

        assert result["action"] == "updated"
