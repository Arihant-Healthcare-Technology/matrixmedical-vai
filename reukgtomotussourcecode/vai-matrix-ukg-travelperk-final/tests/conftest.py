"""
Shared pytest fixtures for TravelPerk tests.
"""
import os
import sys
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required environment variables for tests
os.environ.setdefault("UKG_BASE_URL", "https://service4.ultipro.com")
os.environ.setdefault("UKG_USERNAME", "test_user")
os.environ.setdefault("UKG_PASSWORD", "test_pass")
os.environ.setdefault("UKG_CUSTOMER_API_KEY", "test_api_key")
os.environ.setdefault("TRAVELPERK_API_BASE", "https://app.sandbox-travelperk.com")
os.environ.setdefault("TRAVELPERK_API_KEY", "test_travelperk_key")


@pytest.fixture
def sample_ukg_employee_employment_details():
    """Sample UKG employee-employment-details response."""
    return {
        "employeeNumber": "12345",
        "employeeID": "EMP001",
        "companyID": "J9A6Y",
        "companyId": "J9A6Y",
        "primaryProjectCode": "PROJ001",
        "terminationDate": None,
        "employeeStatusCode": "A",
        "employeeTypeCode": "FTC",
        "supervisorEmployeeID": None,
        "supervisorEmployeeNumber": None,
    }


@pytest.fixture
def sample_ukg_person_details():
    """Sample UKG person-details response."""
    return {
        "employeeId": "EMP001",
        "firstName": "John",
        "lastName": "Doe",
        "emailAddress": "john.doe@example.com",
        "addressState": "FL",
        "phoneNumber": "555-123-4567",
    }


@pytest.fixture
def sample_travelperk_user_payload():
    """Sample TravelPerk SCIM user payload."""
    return {
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"
        ],
        "userName": "john.doe@example.com",
        "externalId": "12345",
        "name": {
            "givenName": "John",
            "familyName": "Doe"
        },
        "active": True,
        "emails": [
            {
                "value": "john.doe@example.com",
                "type": "work",
                "primary": True
            }
        ],
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
            "costCenter": "PROJ001"
        },
        "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User": {}
    }


@pytest.fixture
def sample_travelperk_user_response():
    """Sample TravelPerk API response for a user."""
    return {
        "id": "tp-user-123",
        "userName": "john.doe@example.com",
        "externalId": "12345",
        "name": {
            "givenName": "John",
            "familyName": "Doe"
        },
        "active": True,
        "emails": [
            {
                "value": "john.doe@example.com",
                "type": "work",
                "primary": True
            }
        ],
    }


@pytest.fixture
def sample_supervisor_details():
    """Sample UKG employee-supervisor-details response."""
    return [
        {
            "employeeNumber": "12345",
            "employeeID": "EMP001",
            "supervisorEmployeeNumber": "54321",
            "supervisorEmployeeID": "SUP001",
        },
        {
            "employeeNumber": "54321",
            "employeeID": "SUP001",
            "supervisorEmployeeNumber": None,
            "supervisorEmployeeID": None,
        },
        {
            "employeeNumber": "67890",
            "employeeID": "EMP002",
            "supervisorEmployeeNumber": "54321",
            "supervisorEmployeeID": "SUP001",
        },
    ]


@pytest.fixture
def sample_terminated_employee():
    """Sample terminated employee data."""
    return {
        "employeeNumber": "99999",
        "employeeID": "EMP999",
        "companyID": "J9A6Y",
        "companyId": "J9A6Y",
        "primaryProjectCode": "PROJ002",
        "terminationDate": "2024-12-31T00:00:00Z",
        "employeeStatusCode": "T",
    }


@pytest.fixture
def sample_travelperk_scim_list_response(sample_travelperk_user_response):
    """Sample TravelPerk SCIM list response."""
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 1,
        "itemsPerPage": 20,
        "startIndex": 1,
        "Resources": [sample_travelperk_user_response]
    }
