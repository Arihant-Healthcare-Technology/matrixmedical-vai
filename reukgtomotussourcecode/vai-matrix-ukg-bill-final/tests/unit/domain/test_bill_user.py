"""
Unit tests for BillUser domain model.
"""

import pytest
from datetime import date

from src.domain.models.bill_user import BillRole, BillUser
from src.domain.models.employee import Employee, EmployeeStatus


class TestBillRole:
    """Tests for BillRole enum."""

    def test_from_string_valid_roles(self):
        """Test converting valid role strings."""
        assert BillRole.from_string("ADMIN") == BillRole.ADMIN
        assert BillRole.from_string("admin") == BillRole.ADMIN
        assert BillRole.from_string("  MEMBER  ") == BillRole.MEMBER
        assert BillRole.from_string("NO_ACCESS") == BillRole.NO_ACCESS

    def test_from_string_invalid_defaults_to_member(self):
        """Test invalid role defaults to MEMBER."""
        assert BillRole.from_string("INVALID") == BillRole.MEMBER
        assert BillRole.from_string("") == BillRole.MEMBER
        assert BillRole.from_string(None) == BillRole.MEMBER  # type: ignore

    def test_has_access_property(self):
        """Test has_access property for roles."""
        assert BillRole.ADMIN.has_access is True
        assert BillRole.MEMBER.has_access is True
        assert BillRole.AUDITOR.has_access is True
        assert BillRole.NO_ACCESS.has_access is False


class TestBillUser:
    """Tests for BillUser domain model."""

    def test_basic_creation(self):
        """Test basic BillUser creation."""
        user = BillUser(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
        )
        assert user.email == "john.doe@example.com"
        assert user.full_name == "John Doe"
        assert user.role == BillRole.MEMBER
        assert user.is_active is True

    def test_email_normalization(self):
        """Test email is normalized to lowercase."""
        user = BillUser(
            email="JOHN.DOE@EXAMPLE.COM",
            first_name="John",
            last_name="Doe",
        )
        assert user.email == "john.doe@example.com"

    def test_name_stripping(self):
        """Test names are stripped of whitespace."""
        user = BillUser(
            email="john@example.com",
            first_name="  John  ",
            last_name="  Doe  ",
        )
        assert user.first_name == "John"
        assert user.last_name == "Doe"

    def test_phone_normalization(self):
        """Test phone number normalization."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            phone="(415) 555-1234",
        )
        assert user.phone == "4155551234"

    def test_is_active_with_role(self):
        """Test is_active considers role."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.NO_ACCESS,
        )
        assert user.is_active is False

    def test_is_active_when_retired(self):
        """Test is_active when retired."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            retired=True,
        )
        assert user.is_active is False

    def test_exists_in_bill_without_id(self):
        """Test exists_in_bill without ID."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        assert user.exists_in_bill is False

    def test_exists_in_bill_with_id(self):
        """Test exists_in_bill with ID."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            id="uuid-12345",
        )
        assert user.exists_in_bill is True

    def test_validate_valid_user(self):
        """Test validation of valid user."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        errors = user.validate()
        assert len(errors) == 0
        assert user.is_valid() is True

    def test_validate_missing_email(self):
        """Test validation catches missing email."""
        user = BillUser(
            email="",
            first_name="John",
            last_name="Doe",
        )
        errors = user.validate()
        assert "email is required" in errors

    def test_validate_invalid_email(self):
        """Test validation catches invalid email."""
        user = BillUser(
            email="invalid-email",
            first_name="John",
            last_name="Doe",
        )
        errors = user.validate()
        assert any("Invalid email" in e for e in errors)

    def test_validate_missing_first_name(self):
        """Test validation catches missing first name."""
        user = BillUser(
            email="john@example.com",
            first_name="",
            last_name="Doe",
        )
        errors = user.validate()
        assert "first_name is required" in errors

    def test_validate_missing_last_name(self):
        """Test validation catches missing last name."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="",
        )
        errors = user.validate()
        assert "last_name is required" in errors

    def test_to_api_payload(self):
        """Test conversion to API payload."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.ADMIN,
            phone="4155551234",
        )
        payload = user.to_api_payload()
        assert payload == {
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "role": "ADMIN",
            "phone": "4155551234",
        }

    def test_to_api_payload_minimal(self):
        """Test API payload with minimal fields."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        payload = user.to_api_payload()
        assert "phone" not in payload
        assert "externalId" not in payload
        assert "manager" not in payload
        assert "costCenter" not in payload

    def test_to_api_payload_with_manager_and_cost_center(self):
        """Test API payload includes manager and cost center fields."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            manager_email="boss@example.com",
            cost_center="CC001",
            external_id="EMP123",
        )
        payload = user.to_api_payload()
        assert payload["manager"] == "boss@example.com"
        assert payload["costCenter"] == "CC001"
        assert payload["externalId"] == "EMP123"

    def test_to_csv_row(self):
        """Test conversion to CSV row."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            manager_email="boss@example.com",
        )
        row = user.to_csv_row()
        assert row == {
            "first name": "John",
            "last name": "Doe",
            "email address": "john@example.com",
            "role": "Member",
            "manager": "boss@example.com",
            "cost center": "",
            "budget count": "",  # Budget is resolved from cost center via department API
            "company": "",
            "employee type": "",
            "sal": "Hourly",
        }

    def test_to_csv_row_no_access(self):
        """Test CSV row for NO_ACCESS role."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.NO_ACCESS,
        )
        row = user.to_csv_row()
        assert row["role"] == "No access"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            id="uuid-123",
            role=BillRole.ADMIN,
        )
        result = user.to_dict()
        assert result["id"] == "uuid-123"
        assert result["full_name"] == "John Doe"
        assert result["role"] == "ADMIN"
        assert result["is_active"] is True

    def test_diff_same_users(self):
        """Test diff returns empty for identical users."""
        user1 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        user2 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        diffs = user1.diff(user2)
        assert len(diffs) == 0

    def test_diff_different_users(self):
        """Test diff returns differences."""
        user1 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
        )
        user2 = BillUser(
            email="john@example.com",
            first_name="Johnny",
            last_name="Doe",
            role=BillRole.ADMIN,
        )
        diffs = user1.diff(user2)
        assert "first_name" in diffs
        assert diffs["first_name"] == ("John", "Johnny")
        assert "role" in diffs
        assert diffs["role"] == ("MEMBER", "ADMIN")

    def test_needs_update(self):
        """Test needs_update returns True for different users."""
        user1 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        user2 = BillUser(
            email="john@example.com",
            first_name="Johnny",
            last_name="Doe",
        )
        assert user1.needs_update(user2) is True

    def test_needs_update_same(self):
        """Test needs_update returns False for identical users."""
        user1 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        user2 = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        assert user1.needs_update(user2) is False

    def test_from_employee(self):
        """Test creating BillUser from Employee."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="4155551234",
            supervisor_email="boss@example.com",
        )
        user = BillUser.from_employee(emp)
        assert user.email == "jane.smith@example.com"
        assert user.first_name == "Jane"
        assert user.last_name == "Smith"
        assert user.phone == "4155551234"
        assert user.role == BillRole.MEMBER
        assert user.manager_email == "boss@example.com"
        assert user.external_id == "12345"

    def test_from_employee_with_role_override(self):
        """Test creating BillUser from Employee with role override."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
        )
        user = BillUser.from_employee(emp, role=BillRole.ADMIN)
        assert user.role == BillRole.ADMIN

    def test_from_employee_inactive(self):
        """Test creating BillUser from terminated Employee."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            status=EmployeeStatus.TERMINATED,
        )
        user = BillUser.from_employee(emp)
        assert user.retired is True
        assert user.is_active is False

    def test_from_bill_api(self):
        """Test creating BillUser from BILL API response."""
        data = {
            "id": "uuid-12345",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "role": "ADMIN",
            "phone": "4155551234",
            "retired": False,
            "externalId": "EMP001",
        }
        user = BillUser.from_bill_api(data)
        assert user.id == "uuid-12345"
        assert user.email == "john@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.role == BillRole.ADMIN
        assert user.external_id == "EMP001"

    def test_from_bill_api_with_uuid(self):
        """Test from_bill_api extracts UUID if id is missing."""
        data = {
            "uuid": "uuid-67890",
            "email": "john@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }
        user = BillUser.from_bill_api(data)
        assert user.id == "uuid-67890"

    def test_role_string_conversion(self):
        """Test role string is converted to enum."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role="ADMIN",  # type: ignore
        )
        assert user.role == BillRole.ADMIN

    def test_cost_center_fields(self):
        """Test cost_center and cost_center_description fields."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            cost_center="5230",
            cost_center_description="Engineering",
        )
        assert user.cost_center == "5230"
        assert user.cost_center_description == "Engineering"

    def test_direct_labor_field(self):
        """Test direct_labor field."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            direct_labor=True,
        )
        assert user.direct_labor is True

    def test_direct_labor_defaults_to_false(self):
        """Test direct_labor defaults to False."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )
        assert user.direct_labor is False

    def test_to_csv_row_with_cost_center(self):
        """Test CSV row includes formatted cost center."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            role=BillRole.MEMBER,
            cost_center="5230",
            cost_center_description="Engineering",
            direct_labor=True,
            budget="Matrix Clinical / Direct",  # Budget resolved from department API
        )
        row = user.to_csv_row()
        assert row["cost center"] == "5230 – Engineering"
        assert row["budget count"] == "Matrix Clinical / Direct"

    def test_to_csv_row_cost_center_code_only(self):
        """Test CSV row with cost center code only (no description)."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            cost_center="5230",
        )
        row = user.to_csv_row()
        assert row["cost center"] == "5230"

    def test_to_csv_row_with_budget(self):
        """Test CSV row shows budget field value."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            budget="Matrix Corporate / Indirect",
        )
        row = user.to_csv_row()
        assert row["budget count"] == "Matrix Corporate / Indirect"

    def test_to_dict_includes_new_fields(self):
        """Test to_dict includes cost_center and direct_labor."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            cost_center="5230",
            cost_center_description="Engineering",
            direct_labor=True,
        )
        result = user.to_dict()
        assert result["cost_center"] == "5230"
        assert result["cost_center_description"] == "Engineering"
        assert result["direct_labor"] is True

    def test_from_employee_with_cost_center(self):
        """Test from_employee extracts cost center fields."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            cost_center="5230",
            cost_center_description="Engineering",
            direct_labor=True,
        )
        user = BillUser.from_employee(emp)
        assert user.cost_center == "5230"
        assert user.cost_center_description == "Engineering"
        assert user.direct_labor is True

    def test_from_employee_indirect_labor(self):
        """Test from_employee with indirect labor."""
        emp = Employee(
            employee_id="EMP001",
            employee_number="12345",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            direct_labor=False,
        )
        user = BillUser.from_employee(emp)
        assert user.direct_labor is False

    def test_to_csv_row_with_salaried_pay_frequency(self):
        """Test CSV row shows Salaried for salaried pay frequency."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            pay_frequency="Salary",
        )
        row = user.to_csv_row()
        assert row["sal"] == "Salaried"

    def test_to_csv_row_with_hourly_pay_frequency(self):
        """Test CSV row shows Hourly for hourly pay frequency."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            pay_frequency="Hourly",
        )
        row = user.to_csv_row()
        assert row["sal"] == "Hourly"

    def test_to_csv_row_with_employee_type_code(self):
        """Test CSV row includes employee type code."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            employee_type_code="PRD",
        )
        row = user.to_csv_row()
        assert row["employee type"] == "PRD"

    def test_to_csv_row_with_company(self):
        """Test CSV row includes company."""
        user = BillUser(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            company="CCHN",
        )
        row = user.to_csv_row()
        assert row["company"] == "CCHN"
