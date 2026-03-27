"""
Unit tests for BILL.com data mappers.
"""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.models.bill_user import BillRole, BillUser
from src.domain.models.employee import Employee, EmployeeStatus
from src.domain.models.invoice import BillStatus, Invoice, InvoiceLineItem
from src.domain.models.payment import (
    FundingAccount,
    FundingAccountType,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from src.domain.models.vendor import PaymentMethod as VendorPaymentMethod
from src.domain.models.vendor import Vendor, VendorAddress, VendorStatus
from src.infrastructure.adapters.bill.mappers import (
    build_bill_user_csv_row,
    build_bulk_payment_payload,
    build_invoice_csv_row,
    build_vendor_csv_row,
    extract_api_error,
    format_date,
    map_bill_status,
    map_employee_to_bill_user,
    map_funding_account_from_api,
    map_payment_method,
    map_payment_status,
    map_vendor_payment_method,
    map_vendor_status,
    normalize_email,
    normalize_phone,
    parse_bulk_payment_results,
    parse_date,
    parse_decimal,
    validate_invoice_for_api,
    validate_payment_for_api,
    validate_vendor_for_api,
)


class TestParseDate:
    """Tests for parse_date function."""

    def test_iso_8601_with_z(self):
        """Should parse ISO 8601 date with Z timezone."""
        result = parse_date("2024-01-15T00:00:00Z")
        assert result == date(2024, 1, 15)

    def test_iso_8601_with_offset(self):
        """Should parse ISO 8601 date with offset."""
        result = parse_date("2024-03-20T10:30:00+05:00")
        assert result == date(2024, 3, 20)

    def test_plain_date(self):
        """Should parse plain YYYY-MM-DD date."""
        result = parse_date("2024-06-15")
        assert result == date(2024, 6, 15)

    def test_empty_date(self):
        """Should return None for empty/None input."""
        assert parse_date(None) is None
        assert parse_date("") is None

    def test_invalid_date(self):
        """Should return None for invalid date format."""
        assert parse_date("not-a-date") is None


class TestFormatDate:
    """Tests for format_date function."""

    def test_valid_date(self):
        """Should format date to YYYY-MM-DD."""
        result = format_date(date(2024, 3, 15))
        assert result == "2024-03-15"

    def test_none_date(self):
        """Should return empty string for None."""
        assert format_date(None) == ""


class TestParseDecimal:
    """Tests for parse_decimal function."""

    def test_string_value(self):
        """Should parse string to Decimal."""
        assert parse_decimal("100.50") == Decimal("100.50")

    def test_int_value(self):
        """Should parse int to Decimal."""
        assert parse_decimal(100) == Decimal("100")

    def test_float_value(self):
        """Should parse float to Decimal."""
        result = parse_decimal(99.99)
        assert result == Decimal("99.99")

    def test_decimal_value(self):
        """Should return Decimal as-is."""
        d = Decimal("123.45")
        assert parse_decimal(d) == d

    def test_none_value(self):
        """Should return zero for None."""
        assert parse_decimal(None) == Decimal("0")

    def test_invalid_value(self):
        """Should return zero for invalid value."""
        assert parse_decimal("not-a-number") == Decimal("0")


class TestNormalizeEmail:
    """Tests for normalize_email function."""

    def test_lowercase(self):
        """Should lowercase email."""
        assert normalize_email("John.Doe@Example.COM") == "john.doe@example.com"

    def test_trim_whitespace(self):
        """Should trim whitespace."""
        assert normalize_email("  test@example.com  ") == "test@example.com"

    def test_empty(self):
        """Should return empty string for None/empty."""
        assert normalize_email(None) == ""
        assert normalize_email("") == ""


class TestNormalizePhone:
    """Tests for normalize_phone function."""

    def test_ten_digit(self):
        """Should format 10-digit phone."""
        assert normalize_phone("5551234567") == "555-123-4567"

    def test_eleven_digit_with_country(self):
        """Should handle 11-digit with leading 1."""
        assert normalize_phone("15551234567") == "555-123-4567"

    def test_empty(self):
        """Should return empty for None/empty."""
        assert normalize_phone(None) == ""
        assert normalize_phone("") == ""


class TestMapVendorStatus:
    """Tests for map_vendor_status function."""

    def test_active(self):
        """Should map active status."""
        assert map_vendor_status("active") == VendorStatus.ACTIVE
        assert map_vendor_status("ACTIVE") == VendorStatus.ACTIVE

    def test_inactive(self):
        """Should map inactive status."""
        assert map_vendor_status("inactive") == VendorStatus.INACTIVE
        assert map_vendor_status("retired") == VendorStatus.INACTIVE

    def test_archived(self):
        """Should map archived status."""
        assert map_vendor_status("archived") == VendorStatus.ARCHIVED

    def test_default(self):
        """Should default to active."""
        assert map_vendor_status(None) == VendorStatus.ACTIVE
        assert map_vendor_status("unknown") == VendorStatus.ACTIVE


class TestMapVendorPaymentMethod:
    """Tests for map_vendor_payment_method function."""

    def test_ach(self):
        """Should map ACH."""
        assert map_vendor_payment_method("ACH") == VendorPaymentMethod.ACH

    def test_check(self):
        """Should map CHECK."""
        assert map_vendor_payment_method("CHECK") == VendorPaymentMethod.CHECK

    def test_wire(self):
        """Should map WIRE."""
        assert map_vendor_payment_method("WIRE") == VendorPaymentMethod.WIRE

    def test_card_account(self):
        """Should map card account variants."""
        assert map_vendor_payment_method("CARD_ACCOUNT") == VendorPaymentMethod.CARD_ACCOUNT
        assert map_vendor_payment_method("CARD") == VendorPaymentMethod.CARD_ACCOUNT
        assert map_vendor_payment_method("VIRTUAL_CARD") == VendorPaymentMethod.CARD_ACCOUNT

    def test_default(self):
        """Should default to CHECK."""
        assert map_vendor_payment_method(None) == VendorPaymentMethod.CHECK
        assert map_vendor_payment_method("unknown") == VendorPaymentMethod.CHECK


class TestMapBillStatus:
    """Tests for map_bill_status function."""

    def test_open(self):
        """Should map open status."""
        assert map_bill_status("open") == BillStatus.OPEN

    def test_approved(self):
        """Should map approved status."""
        assert map_bill_status("approved") == BillStatus.APPROVED

    def test_paid(self):
        """Should map paid status."""
        assert map_bill_status("paid") == BillStatus.PAID

    def test_voided(self):
        """Should map voided status."""
        assert map_bill_status("voided") == BillStatus.VOIDED
        assert map_bill_status("void") == BillStatus.VOIDED

    def test_scheduled(self):
        """Should map scheduled status."""
        assert map_bill_status("scheduled") == BillStatus.SCHEDULED

    def test_processing(self):
        """Should map processing status."""
        assert map_bill_status("processing") == BillStatus.PROCESSING

    def test_partial(self):
        """Should map partial status."""
        assert map_bill_status("partial") == BillStatus.PARTIAL

    def test_default(self):
        """Should default to open."""
        assert map_bill_status(None) == BillStatus.OPEN
        assert map_bill_status("unknown") == BillStatus.OPEN


class TestMapPaymentStatus:
    """Tests for map_payment_status function."""

    def test_pending(self):
        """Should map pending status."""
        assert map_payment_status("PENDING") == PaymentStatus.PENDING

    def test_completed(self):
        """Should map completed status."""
        assert map_payment_status("COMPLETED") == PaymentStatus.COMPLETED
        assert map_payment_status("PAID") == PaymentStatus.COMPLETED

    def test_failed(self):
        """Should map failed status."""
        assert map_payment_status("FAILED") == PaymentStatus.FAILED
        assert map_payment_status("ERROR") == PaymentStatus.FAILED

    def test_cancelled(self):
        """Should map cancelled status."""
        assert map_payment_status("CANCELLED") == PaymentStatus.CANCELLED
        assert map_payment_status("CANCELED") == PaymentStatus.CANCELLED

    def test_default(self):
        """Should default to pending."""
        assert map_payment_status(None) == PaymentStatus.PENDING
        assert map_payment_status("unknown") == PaymentStatus.PENDING


class TestMapPaymentMethod:
    """Tests for map_payment_method function."""

    def test_ach(self):
        """Should map ACH."""
        assert map_payment_method("ACH") == PaymentMethod.ACH

    def test_check(self):
        """Should map CHECK."""
        assert map_payment_method("CHECK") == PaymentMethod.CHECK

    def test_wire(self):
        """Should map WIRE."""
        assert map_payment_method("WIRE") == PaymentMethod.WIRE

    def test_card_account(self):
        """Should map card account variants."""
        assert map_payment_method("CARD_ACCOUNT") == PaymentMethod.CARD_ACCOUNT
        assert map_payment_method("CARD") == PaymentMethod.CARD_ACCOUNT
        assert map_payment_method("VIRTUAL_CARD") == PaymentMethod.CARD_ACCOUNT

    def test_default(self):
        """Should default to CHECK."""
        assert map_payment_method(None) == PaymentMethod.CHECK
        assert map_payment_method("unknown") == PaymentMethod.CHECK


class TestMapFundingAccountFromApi:
    """Tests for map_funding_account_from_api function."""

    def test_valid_account(self):
        """Should map valid funding account."""
        data = {"id": "ACC001", "type": "BANK_ACCOUNT"}
        result = map_funding_account_from_api(data)
        assert result is not None
        assert result.id == "ACC001"
        assert result.account_type == FundingAccountType.BANK_ACCOUNT

    def test_alternate_id_field(self):
        """Should handle accountId field."""
        data = {"accountId": "ACC002", "type": "CARD_ACCOUNT"}
        result = map_funding_account_from_api(data)
        assert result is not None
        assert result.id == "ACC002"

    def test_empty_data(self):
        """Should return None for empty data."""
        assert map_funding_account_from_api({}) is None
        assert map_funding_account_from_api(None) is None

    def test_missing_id(self):
        """Should return None when id is missing."""
        assert map_funding_account_from_api({"type": "BANK_ACCOUNT"}) is None


class TestMapEmployeeToBillUser:
    """Tests for map_employee_to_bill_user function."""

    def test_basic_mapping(self):
        """Should map Employee to BillUser."""
        employee = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            status=EmployeeStatus.ACTIVE,
        )

        user = map_employee_to_bill_user(employee)

        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"
        assert user.role == BillRole.MEMBER  # Default

    def test_with_role_override(self):
        """Should use role override."""
        employee = Employee(
            employee_id="EMP002",
            employee_number="67890",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
        )

        user = map_employee_to_bill_user(employee, role=BillRole.ADMIN)

        assert user.role == BillRole.ADMIN

    def test_with_manager_email(self):
        """Should use manager email override."""
        employee = Employee(
            employee_id="EMP003",
            employee_number="11111",
            first_name="Bob",
            last_name="Wilson",
            email="bob.wilson@example.com",
        )

        user = map_employee_to_bill_user(employee, manager_email="manager@example.com")

        assert user.manager_email == "manager@example.com"


class TestBuildBillUserCsvRow:
    """Tests for build_bill_user_csv_row function."""

    def test_full_user(self):
        """Should build complete CSV row."""
        user = BillUser(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            role=BillRole.ADMIN,
            manager_email="manager@example.com",
            cost_center="5230",
            cost_center_description="Engineering",
            direct_labor=True,
        )

        row = build_bill_user_csv_row(user)

        assert row["first name"] == "John"
        assert row["last name"] == "Doe"
        assert row["email address"] == "john.doe@example.com"
        assert row["role"] == "Admin"  # Capitalized format
        assert row["manager"] == "manager@example.com"
        assert row["cost center"] == "5230 – Engineering"
        assert row["budget count"] == "Direct"

    def test_minimal_user(self):
        """Should handle minimal user."""
        user = BillUser(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
        )

        row = build_bill_user_csv_row(user)

        assert row["first name"] == "Jane"
        assert row["role"] == "Member"  # Default, capitalized
        assert row["manager"] == ""
        assert row["cost center"] == ""
        assert row["budget count"] == "Indirect"

    def test_user_with_cost_center_only(self):
        """Should handle cost center without description."""
        user = BillUser(
            first_name="Bob",
            last_name="Wilson",
            email="bob@example.com",
            cost_center="4500",
        )

        row = build_bill_user_csv_row(user)

        assert row["cost center"] == "4500"
        assert row["budget count"] == "Indirect"


class TestBuildVendorCsvRow:
    """Tests for build_vendor_csv_row function."""

    def test_full_vendor(self):
        """Should build complete vendor CSV row."""
        vendor = Vendor(
            name="Acme Corp",
            short_name="ACME",
            email="vendor@acme.com",
            phone="555-123-4567",
            address=VendorAddress(
                line1="123 Main St",
                city="Austin",
                state="TX",
                zip_code="78701",
            ),
            payment_method=VendorPaymentMethod.ACH,
            payment_term_days=30,
            external_id="EXT001",
        )

        row = build_vendor_csv_row(vendor)

        assert row["name"] == "Acme Corp"
        assert row["short_name"] == "ACME"
        assert row["email"] == "vendor@acme.com"
        assert row["address_line1"] == "123 Main St"
        assert row["city"] == "Austin"
        assert row["state"] == "TX"
        assert row["payment_method"] == "ACH"


class TestBuildInvoiceCsvRow:
    """Tests for build_invoice_csv_row function."""

    def test_full_invoice(self):
        """Should build complete invoice CSV row."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="VEND001",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[
                InvoiceLineItem(amount=Decimal("1000.00"), description="Services"),
            ],
            status=BillStatus.OPEN,
            external_id="EXT001",
        )

        row = build_invoice_csv_row(invoice)

        assert row["invoice_number"] == "INV-001"
        assert row["vendor_id"] == "VEND001"
        assert row["invoice_date"] == "2024-01-15"
        assert row["due_date"] == "2024-02-15"
        assert row["amount"] == "1000.00"
        assert row["status"] == "open"


class TestBuildBulkPaymentPayload:
    """Tests for build_bulk_payment_payload function."""

    def test_multiple_payments(self):
        """Should build bulk payment payload."""
        payments = [
            Payment(
                bill_id="BILL001",
                amount=Decimal("500.00"),
                process_date=date(2024, 3, 15),
            ),
            Payment(
                bill_id="BILL002",
                amount=Decimal("750.00"),
                process_date=date(2024, 3, 15),
            ),
        ]

        payload = build_bulk_payment_payload(payments)

        assert "payments" in payload
        assert len(payload["payments"]) == 2


class TestParseBulkPaymentResults:
    """Tests for parse_bulk_payment_results function."""

    def test_successful_results(self):
        """Should parse successful payment results."""
        data = {
            "results": [
                {"id": "PAY001", "billId": "BILL001", "amount": 500.00},
                {"id": "PAY002", "billId": "BILL002", "amount": 750.00},
            ]
        }

        payments = parse_bulk_payment_results(data)

        assert len(payments) == 2
        assert payments[0].id == "PAY001"
        assert payments[1].id == "PAY002"

    def test_partial_results(self):
        """Should handle partial results."""
        data = {
            "results": [
                {"id": "PAY001", "billId": "BILL001"},
                {"error": "Payment failed"},  # No id
            ]
        }

        payments = parse_bulk_payment_results(data)

        assert len(payments) == 1

    def test_empty_results(self):
        """Should handle empty results."""
        data = {"results": []}
        payments = parse_bulk_payment_results(data)
        assert len(payments) == 0


class TestExtractApiError:
    """Tests for extract_api_error function."""

    def test_string_error(self):
        """Should extract string error."""
        data = {"error": "Invalid request"}
        assert extract_api_error(data) == "Invalid request"

    def test_dict_error(self):
        """Should extract error from dict."""
        data = {"error": {"message": "Validation failed"}}
        assert extract_api_error(data) == "Validation failed"

    def test_message_field(self):
        """Should extract message field."""
        data = {"message": "Something went wrong"}
        assert extract_api_error(data) == "Something went wrong"

    def test_errors_array(self):
        """Should join errors array."""
        data = {
            "errors": [
                {"message": "Field A is required"},
                {"message": "Field B is invalid"},
            ]
        }
        result = extract_api_error(data)
        assert "Field A is required" in result
        assert "Field B is invalid" in result

    def test_empty_data(self):
        """Should handle empty data."""
        result = extract_api_error({})
        assert result  # Should return some string representation
        assert extract_api_error(None) == "Unknown API error"


class TestValidateVendorForApi:
    """Tests for validate_vendor_for_api function."""

    def test_valid_vendor(self):
        """Should return no errors for valid vendor."""
        vendor = Vendor(
            name="Valid Vendor Co",
            email="vendor@example.com",
        )
        errors = validate_vendor_for_api(vendor)
        assert len(errors) == 0

    def test_missing_name(self):
        """Should require vendor name."""
        vendor = Vendor(name="", email="vendor@example.com")
        errors = validate_vendor_for_api(vendor)
        assert any("name" in e.lower() for e in errors)

    def test_short_name(self):
        """Should require min 2 char name."""
        vendor = Vendor(name="A", email="vendor@example.com")
        errors = validate_vendor_for_api(vendor)
        assert any("name" in e.lower() for e in errors)

    def test_invalid_email(self):
        """Should validate email format."""
        vendor = Vendor(name="Valid Name", email="not-an-email")
        errors = validate_vendor_for_api(vendor)
        assert any("email" in e.lower() for e in errors)


class TestValidateInvoiceForApi:
    """Tests for validate_invoice_for_api function."""

    def test_valid_invoice(self):
        """Should return no errors for valid invoice."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="VEND001",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[
                InvoiceLineItem(amount=Decimal("100.00")),
            ],
        )
        errors = validate_invoice_for_api(invoice)
        assert len(errors) == 0

    def test_missing_invoice_number(self):
        """Should require invoice number."""
        invoice = Invoice(
            invoice_number="",
            vendor_id="VEND001",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = validate_invoice_for_api(invoice)
        assert any("invoice number" in e.lower() for e in errors)

    def test_missing_vendor_id(self):
        """Should require vendor ID."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = validate_invoice_for_api(invoice)
        assert any("vendor" in e.lower() for e in errors)

    def test_no_line_items(self):
        """Should require line items."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="VEND001",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[],
        )
        errors = validate_invoice_for_api(invoice)
        assert any("line item" in e.lower() for e in errors)

    def test_due_date_before_invoice_date(self):
        """Should validate due date >= invoice date."""
        invoice = Invoice(
            invoice_number="INV-001",
            vendor_id="VEND001",
            invoice_date=date(2024, 2, 15),
            due_date=date(2024, 1, 15),  # Before invoice date
            line_items=[InvoiceLineItem(amount=Decimal("100.00"))],
        )
        errors = validate_invoice_for_api(invoice)
        assert any("due date" in e.lower() for e in errors)


class TestValidatePaymentForApi:
    """Tests for validate_payment_for_api function."""

    def test_valid_payment(self):
        """Should return no errors for valid payment."""
        payment = Payment(
            bill_id="BILL001",
            amount=Decimal("500.00"),
            process_date=date(2024, 3, 15),
            funding_account=FundingAccount(
                id="ACC001",
                account_type=FundingAccountType.BANK_ACCOUNT,
            ),
        )
        errors = validate_payment_for_api(payment)
        assert len(errors) == 0

    def test_missing_bill_id(self):
        """Should require bill ID."""
        payment = Payment(
            bill_id="",
            amount=Decimal("500.00"),
            process_date=date(2024, 3, 15),
            funding_account=FundingAccount(id="ACC001", account_type=FundingAccountType.BANK_ACCOUNT),
        )
        errors = validate_payment_for_api(payment)
        assert any("bill" in e.lower() for e in errors)

    def test_zero_amount(self):
        """Should require positive amount."""
        payment = Payment(
            bill_id="BILL001",
            amount=Decimal("0"),
            process_date=date(2024, 3, 15),
            funding_account=FundingAccount(id="ACC001", account_type=FundingAccountType.BANK_ACCOUNT),
        )
        errors = validate_payment_for_api(payment)
        assert any("amount" in e.lower() for e in errors)

    def test_missing_funding_account(self):
        """Should require funding account."""
        payment = Payment(
            bill_id="BILL001",
            amount=Decimal("500.00"),
            process_date=date(2024, 3, 15),
            funding_account=None,
        )
        errors = validate_payment_for_api(payment)
        assert any("funding" in e.lower() for e in errors)
