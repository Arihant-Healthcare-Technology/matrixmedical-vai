"""
Unit tests for Vendor domain model.
"""

import pytest

from src.domain.models.vendor import (
    PaymentMethod,
    Vendor,
    VendorAddress,
    VendorStatus,
)


class TestPaymentMethod:
    """Tests for PaymentMethod enum."""

    def test_from_string_valid_methods(self):
        """Test converting valid method strings."""
        assert PaymentMethod.from_string("CHECK") == PaymentMethod.CHECK
        assert PaymentMethod.from_string("check") == PaymentMethod.CHECK
        assert PaymentMethod.from_string("ACH") == PaymentMethod.ACH
        assert PaymentMethod.from_string("WIRE") == PaymentMethod.WIRE

    def test_from_string_invalid_defaults_to_ach(self):
        """Test invalid method defaults to ACH."""
        assert PaymentMethod.from_string("INVALID") == PaymentMethod.ACH
        assert PaymentMethod.from_string("") == PaymentMethod.ACH


class TestVendorStatus:
    """Tests for VendorStatus enum."""

    def test_values(self):
        """Test status values."""
        assert VendorStatus.ACTIVE.value == "active"
        assert VendorStatus.INACTIVE.value == "inactive"
        assert VendorStatus.ARCHIVED.value == "archived"


class TestVendorAddress:
    """Tests for VendorAddress dataclass."""

    def test_is_us_address(self):
        """Test US address detection."""
        us_addr = VendorAddress(country="US")
        assert us_addr.is_us_address() is True

        usa_addr = VendorAddress(country="USA")
        assert usa_addr.is_us_address() is True

        intl_addr = VendorAddress(country="CA")
        assert intl_addr.is_us_address() is False

    def test_is_complete(self):
        """Test address completeness check."""
        complete = VendorAddress(
            line1="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
        )
        assert complete.is_complete() is True

        incomplete = VendorAddress(
            line1="123 Main St",
            city="San Francisco",
        )
        assert incomplete.is_complete() is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        addr = VendorAddress(
            line1="123 Main St",
            line2="Suite 100",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            country="US",
        )
        result = addr.to_dict()
        assert result["line1"] == "123 Main St"
        assert result["zip"] == "94105"  # Note: uses "zip" not "zip_code"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "line1": "456 Oak Ave",
            "line2": "",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
            "country": "US",
        }
        addr = VendorAddress.from_dict(data)
        assert addr.line1 == "456 Oak Ave"
        assert addr.zip_code == "90001"

    def test_from_dict_with_zip_code_key(self):
        """Test from_dict handles both zip and zip_code keys."""
        data = {
            "line1": "789 Pine St",
            "city": "Seattle",
            "state": "WA",
            "zip_code": "98101",
        }
        addr = VendorAddress.from_dict(data)
        assert addr.zip_code == "98101"


class TestVendor:
    """Tests for Vendor domain model."""

    def test_basic_creation(self):
        """Test basic vendor creation."""
        vendor = Vendor(name="Acme Corp")
        assert vendor.name == "Acme Corp"
        assert vendor.status == VendorStatus.ACTIVE
        assert vendor.payment_method == PaymentMethod.ACH

    def test_name_stripping(self):
        """Test name is stripped of whitespace."""
        vendor = Vendor(name="  Acme Corp  ")
        assert vendor.name == "Acme Corp"

    def test_email_normalization(self):
        """Test email is normalized to lowercase."""
        vendor = Vendor(
            name="Acme Corp",
            email="VENDOR@ACME.COM",
        )
        assert vendor.email == "vendor@acme.com"

    def test_phone_normalization(self):
        """Test phone number normalization."""
        vendor = Vendor(
            name="Acme Corp",
            phone="(415) 555-1234",
        )
        assert vendor.phone == "4155551234"

    def test_is_active(self):
        """Test is_active property."""
        active = Vendor(name="Acme", status=VendorStatus.ACTIVE)
        inactive = Vendor(name="Acme", status=VendorStatus.INACTIVE)

        assert active.is_active is True
        assert inactive.is_active is False

    def test_is_international(self):
        """Test is_international property."""
        us_vendor = Vendor(
            name="US Vendor",
            address=VendorAddress(country="US"),
        )
        intl_vendor = Vendor(
            name="Intl Vendor",
            address=VendorAddress(country="CA"),
        )

        assert us_vendor.is_international is False
        assert intl_vendor.is_international is True

    def test_exists_in_bill(self):
        """Test exists_in_bill property."""
        new_vendor = Vendor(name="New Vendor")
        existing_vendor = Vendor(name="Existing Vendor", id="vendor-123")

        assert new_vendor.exists_in_bill is False
        assert existing_vendor.exists_in_bill is True

    def test_validate_valid_vendor(self):
        """Test validation of valid vendor."""
        vendor = Vendor(name="Acme Corp")
        errors = vendor.validate()
        assert len(errors) == 0
        assert vendor.is_valid() is True

    def test_validate_missing_name(self):
        """Test validation catches missing name."""
        vendor = Vendor(name="")
        errors = vendor.validate()
        assert "name is required" in errors

    def test_validate_invalid_email(self):
        """Test validation catches invalid email."""
        vendor = Vendor(
            name="Acme Corp",
            email="invalid-email",
        )
        errors = vendor.validate()
        assert any("Invalid email" in e for e in errors)

    def test_validate_negative_payment_terms(self):
        """Test validation catches negative payment terms."""
        vendor = Vendor(
            name="Acme Corp",
            payment_term_days=-5,
        )
        errors = vendor.validate()
        assert any("payment_term_days must be >= 0" in e for e in errors)

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        vendor = Vendor(
            name="Acme Corp",
            short_name="ACME",
            email="vendor@acme.com",
            phone="4155551234",
            payment_method=PaymentMethod.CHECK,
            payment_term_days=45,
            external_id="EXT-001",
        )
        payload = vendor.to_api_payload()
        assert payload["name"] == "Acme Corp"
        assert payload["shortName"] == "ACME"
        assert payload["email"] == "vendor@acme.com"
        assert payload["paymentMethod"] == "CHECK"
        assert payload["paymentTermDays"] == 45
        assert payload["externalId"] == "EXT-001"

    def test_to_api_payload_with_address(self):
        """Test API payload includes address when complete."""
        vendor = Vendor(
            name="Acme Corp",
            address=VendorAddress(
                line1="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94105",
            ),
        )
        payload = vendor.to_api_payload()
        assert "address" in payload
        assert payload["address"]["line1"] == "123 Main St"

    def test_to_api_payload_excludes_incomplete_address(self):
        """Test API payload excludes incomplete address."""
        vendor = Vendor(
            name="Acme Corp",
            address=VendorAddress(
                line1="123 Main St",
                # Missing city, state, zip
            ),
        )
        payload = vendor.to_api_payload()
        assert "address" not in payload

    def test_to_dict(self):
        """Test conversion to dictionary."""
        vendor = Vendor(
            name="Acme Corp",
            id="vendor-123",
            external_id="EXT-001",
            payment_method=PaymentMethod.ACH,
        )
        result = vendor.to_dict()
        assert result["id"] == "vendor-123"
        assert result["name"] == "Acme Corp"
        assert result["payment_method"] == "ACH"
        assert result["is_active"] is True

    def test_diff_same_vendors(self):
        """Test diff returns empty for identical vendors."""
        v1 = Vendor(name="Acme Corp", email="vendor@acme.com")
        v2 = Vendor(name="Acme Corp", email="vendor@acme.com")
        diffs = v1.diff(v2)
        assert len(diffs) == 0

    def test_diff_different_vendors(self):
        """Test diff returns differences."""
        v1 = Vendor(name="Acme Corp", email="old@acme.com")
        v2 = Vendor(name="Acme Corp", email="new@acme.com")
        diffs = v1.diff(v2)
        assert "email" in diffs
        assert diffs["email"] == ("old@acme.com", "new@acme.com")

    def test_diff_address_changes(self):
        """Test diff detects address changes."""
        v1 = Vendor(
            name="Acme",
            address=VendorAddress(city="San Francisco"),
        )
        v2 = Vendor(
            name="Acme",
            address=VendorAddress(city="Los Angeles"),
        )
        diffs = v1.diff(v2)
        assert "address.city" in diffs

    def test_needs_update(self):
        """Test needs_update with different vendors."""
        v1 = Vendor(name="Acme Corp", email="old@acme.com")
        v2 = Vendor(name="Acme Corp", email="new@acme.com")
        assert v1.needs_update(v2) is True

    def test_needs_update_same(self):
        """Test needs_update with identical vendors."""
        v1 = Vendor(name="Acme Corp")
        v2 = Vendor(name="Acme Corp")
        assert v1.needs_update(v2) is False

    def test_from_bill_api(self):
        """Test creation from BILL API response."""
        data = {
            "id": "vendor-uuid-123",
            "name": "Test Vendor",
            "shortName": "TEST",
            "externalId": "EXT-001",
            "email": "test@vendor.com",
            "phone": "5551234567",
            "address": {
                "line1": "123 Test St",
                "city": "Test City",
                "state": "CA",
                "zip": "90001",
            },
            "paymentMethod": "CHECK",
            "paymentTermDays": 30,
            "status": "active",
            "hasBankInfo": True,
        }
        vendor = Vendor.from_bill_api(data)
        assert vendor.id == "vendor-uuid-123"
        assert vendor.name == "Test Vendor"
        assert vendor.short_name == "TEST"
        assert vendor.payment_method == PaymentMethod.CHECK
        assert vendor.has_bank_info is True
        assert vendor.address.city == "Test City"

    def test_from_csv_row(self):
        """Test creation from CSV row."""
        row = {
            "name": "CSV Vendor",
            "short_name": "CSV",
            "email": "csv@vendor.com",
            "phone": "5559876543",
            "address1": "456 CSV Ave",
            "city": "CSV City",
            "state": "NY",
            "zip": "10001",
            "payment_method": "ACH",
            "payment_term_days": "45",
        }
        vendor = Vendor.from_csv_row(row)
        assert vendor.name == "CSV Vendor"
        assert vendor.short_name == "CSV"
        assert vendor.email == "csv@vendor.com"
        assert vendor.payment_method == PaymentMethod.ACH
        assert vendor.payment_term_days == 45

    def test_from_csv_row_alternate_keys(self):
        """Test CSV row handles alternate column names."""
        row = {
            "vendor_name": "Alt Vendor",
            "vendor_email": "alt@vendor.com",
            "vendor_id": "VEND-001",
        }
        vendor = Vendor.from_csv_row(row)
        assert vendor.name == "Alt Vendor"
        assert vendor.email == "alt@vendor.com"
        assert vendor.external_id == "VEND-001"

    def test_status_string_conversion(self):
        """Test status string is converted to enum."""
        vendor = Vendor(
            name="Acme",
            status="inactive",  # type: ignore
        )
        assert vendor.status == VendorStatus.INACTIVE

    def test_payment_method_string_conversion(self):
        """Test payment method string is converted to enum."""
        vendor = Vendor(
            name="Acme",
            payment_method="wire",  # type: ignore
        )
        assert vendor.payment_method == PaymentMethod.WIRE
