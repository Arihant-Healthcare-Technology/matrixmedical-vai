"""
Shared pytest fixtures for BILL integration tests.

This module provides common fixtures used across unit and integration tests.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required environment variables for tests
os.environ.setdefault("UKG_BASE_URL", "https://service4.ultipro.com")
os.environ.setdefault("UKG_USERNAME", "test_user")
os.environ.setdefault("UKG_PASSWORD", "test_pass")
os.environ.setdefault("UKG_CUSTOMER_API_KEY", "test_api_key")
os.environ.setdefault("BILL_API_BASE", "https://gateway.stage.bill.com/connect/v3/spend")
os.environ.setdefault("BILL_AP_API_BASE", "https://gateway.stage.bill.com/connect/v3")
os.environ.setdefault("BILL_API_TOKEN", "test_token")
os.environ.setdefault("BILL_SE_API_TOKEN", "test_se_token")
os.environ.setdefault("BILL_AP_API_TOKEN", "test_ap_token")


# -----------------------------------------------------------------------------
# UKG Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def ukg_base_url() -> str:
    """UKG API base URL for testing."""
    return "https://service4.ultipro.com"


@pytest.fixture
def ukg_headers() -> Dict[str, str]:
    """Standard UKG API headers."""
    import base64
    credentials = base64.b64encode(b"test_user:test_pass").decode()
    return {
        "Authorization": f"Basic {credentials}",
        "US-CUSTOMER-API-KEY": "test_api_key",
        "Accept": "application/json",
    }


@pytest.fixture
def sample_ukg_employment_details() -> Dict[str, Any]:
    """Sample UKG employee-employment-details response."""
    return {
        "employeeNumber": "12345",
        "employeeID": "EMP001-UUID",
        "companyID": "J9A6Y",
        "companyId": "J9A6Y",
        "primaryProjectCode": "PROJ001",
        "terminationDate": None,
        "employeeStatusCode": "A",
        "employeeTypeCode": "FTC",
        "supervisorEmployeeID": None,
        "supervisorEmployeeNumber": None,
        "hireDate": "2020-01-15T00:00:00Z",
        "directLabor": True,
    }


@pytest.fixture
def sample_ukg_employment_details_list(sample_ukg_employment_details) -> List[Dict[str, Any]]:
    """Sample UKG employee-employment-details list response."""
    return [
        sample_ukg_employment_details,
        {
            **sample_ukg_employment_details,
            "employeeNumber": "12346",
            "employeeID": "EMP002-UUID",
            "employeeStatusCode": "A",
            "employeeTypeCode": "HRC",
        },
        {
            **sample_ukg_employment_details,
            "employeeNumber": "12347",
            "employeeID": "EMP003-UUID",
            "employeeStatusCode": "T",
            "terminationDate": "2024-06-30T00:00:00Z",
        },
    ]


@pytest.fixture
def sample_ukg_person_details() -> Dict[str, Any]:
    """Sample UKG person-details response."""
    return {
        "employeeId": "EMP001-UUID",
        "firstName": "John",
        "lastName": "Doe",
        "middleName": "M",
        "emailAddress": "john.doe@example.com",
        "addressLine1": "123 Main Street",
        "addressLine2": "Apt 4B",
        "addressCity": "Miami",
        "addressState": "FL",
        "addressZipCode": "33101",
        "homePhone": "305-555-1234",
    }


@pytest.fixture
def sample_ukg_employment_details_single() -> Dict[str, Any]:
    """Sample UKG employment-details response for single employee."""
    return {
        "employeeNumber": "12345",
        "employeeId": "EMP001-UUID",
        "companyID": "J9A6Y",
        "hireDate": "2020-01-15T00:00:00Z",
        "terminationDate": None,
        "employeeStatusCode": "A",
        "originalHireDate": "2020-01-15T00:00:00Z",
    }


# -----------------------------------------------------------------------------
# BILL.com S&E Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def bill_se_base_url() -> str:
    """BILL S&E API base URL for testing."""
    return "https://gateway.stage.bill.com/connect/v3/spend"


@pytest.fixture
def bill_se_headers() -> Dict[str, str]:
    """Standard BILL S&E API headers."""
    return {
        "apiToken": "test_se_token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def sample_bill_user_response() -> Dict[str, Any]:
    """Sample BILL user response."""
    return {
        "uuid": "usr_12345",
        "id": "00501000000XXXXX",
        "email": "john.doe@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "role": "MEMBER",
        "retired": False,
        "createdAt": "2024-01-15T10:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_bill_user_list_response(sample_bill_user_response) -> Dict[str, Any]:
    """Sample BILL user list response."""
    return {
        "users": [sample_bill_user_response],
        "pagination": {
            "page": 1,
            "pageSize": 25,
            "totalCount": 1,
        }
    }


@pytest.fixture
def sample_bill_user_create_payload() -> Dict[str, Any]:
    """Sample BILL user creation payload."""
    return {
        "email": "john.doe@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "role": "MEMBER",
    }


# -----------------------------------------------------------------------------
# BILL.com AP Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def bill_ap_base_url() -> str:
    """BILL AP API base URL for testing."""
    return "https://gateway.stage.bill.com/connect/v3"


@pytest.fixture
def bill_ap_headers() -> Dict[str, str]:
    """Standard BILL AP API headers."""
    return {
        "apiToken": "test_ap_token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def sample_vendor_response() -> Dict[str, Any]:
    """Sample BILL vendor response."""
    return {
        "id": "00501000000VNDXX",
        "name": "Acme Corporation",
        "shortName": "ACME",
        "email": "accounts@acme.com",
        "phone": "555-123-4567",
        "externalId": "vendor_001",
        "isActive": True,
        "createdTime": "2024-01-15T10:00:00Z",
        "updatedTime": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_vendor_create_payload() -> Dict[str, Any]:
    """Sample vendor creation payload."""
    return {
        "name": "Acme Corporation",
        "shortName": "ACME",
        "email": "accounts@acme.com",
        "phone": "555-123-4567",
        "externalId": "vendor_001",
        "paymentTermDays": 30,
    }


@pytest.fixture
def sample_bill_response() -> Dict[str, Any]:
    """Sample BILL invoice/bill response."""
    return {
        "id": "00501000000BILXX",
        "vendorId": "00501000000VNDXX",
        "invoice": {
            "number": "INV-2024-001",
            "date": "2024-03-22",
        },
        "dueDate": "2024-04-22",
        "amount": "1500.00",
        "status": "Open",
        "createdTime": "2024-03-22T10:00:00Z",
    }


@pytest.fixture
def sample_bill_create_payload() -> Dict[str, Any]:
    """Sample bill/invoice creation payload."""
    return {
        "vendorId": "00501000000VNDXX",
        "invoice": {
            "number": "INV-2024-001",
            "date": "2024-03-22",
        },
        "dueDate": "2024-04-22",
        "billLineItems": [
            {
                "amount": 1500.00,
                "description": "Consulting services",
            }
        ],
    }


@pytest.fixture
def sample_payment_response() -> Dict[str, Any]:
    """Sample BILL payment response."""
    return {
        "id": "00501000000PAYXX",
        "billId": "00501000000BILXX",
        "amount": "1500.00",
        "processDate": "2024-04-15",
        "status": "Scheduled",
    }


# -----------------------------------------------------------------------------
# Mock Settings Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_ukg_settings():
    """Create mock UKG settings."""
    settings = MagicMock()
    settings.base_url = "https://service4.ultipro.com"
    settings.username = "test_user"
    settings.password = "test_pass"
    settings.customer_api_key = "test_api_key"
    settings.basic_b64 = None
    settings.timeout = 45.0
    return settings


@pytest.fixture
def mock_bill_se_settings():
    """Create mock BILL S&E settings."""
    settings = MagicMock()
    settings.api_base = "https://gateway.stage.bill.com/connect/v3/spend"
    settings.api_token = MagicMock()
    settings.api_token.get_secret_value.return_value = "test_se_token"
    settings.timeout = 30.0
    settings.max_retries = 3
    return settings


@pytest.fixture
def mock_bill_ap_settings():
    """Create mock BILL AP settings."""
    settings = MagicMock()
    settings.api_base = "https://gateway.stage.bill.com/connect/v3"
    settings.api_token = MagicMock()
    settings.api_token.get_secret_value.return_value = "test_ap_token"
    settings.timeout = 30.0
    settings.max_retries = 3
    return settings


# -----------------------------------------------------------------------------
# HTTP Response Mocking Helpers
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_successful_response():
    """Factory fixture for creating mock successful responses."""
    def _create_response(json_data: Dict[str, Any], status_code: int = 200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data
        response.text = str(json_data)
        response.headers = {"Content-Type": "application/json"}
        return response
    return _create_response


@pytest.fixture
def mock_error_response():
    """Factory fixture for creating mock error responses."""
    def _create_response(status_code: int, error_message: str = "Error"):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = {"error": error_message}
        response.text = f'{{"error": "{error_message}"}}'
        response.headers = {"Content-Type": "application/json"}
        if status_code == 429:
            response.headers["Retry-After"] = "60"
        return response
    return _create_response


# -----------------------------------------------------------------------------
# Test Data Generators
# -----------------------------------------------------------------------------

@pytest.fixture
def generate_employees():
    """Factory fixture for generating test employee data."""
    def _generate(count: int = 5, company_id: str = "J9A6Y"):
        employees = []
        for i in range(count):
            employees.append({
                "employeeNumber": f"1234{i}",
                "employeeID": f"EMP00{i}-UUID",
                "companyID": company_id,
                "companyId": company_id,
                "primaryProjectCode": f"PROJ00{i}",
                "terminationDate": None,
                "employeeStatusCode": "A",
                "employeeTypeCode": "FTC" if i % 2 == 0 else "HRC",
            })
        return employees
    return _generate


@pytest.fixture
def generate_vendors():
    """Factory fixture for generating test vendor data."""
    def _generate(count: int = 5):
        vendors = []
        for i in range(count):
            vendors.append({
                "id": f"VND{i:05d}",
                "name": f"Vendor {i}",
                "email": f"vendor{i}@example.com",
                "externalId": f"ext_vendor_{i}",
            })
        return vendors
    return _generate
