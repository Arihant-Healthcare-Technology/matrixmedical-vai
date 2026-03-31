"""
Motus API mock fixtures using responses library.

Provides mock server class for Motus Driver API endpoints.
"""

import re
from typing import Any, Dict, List, Optional

import responses

from .mock_data import MotusMockDataFactory


class MotusMockServer:
    """Helper class to set up Motus API mocks using responses library."""

    DEFAULT_BASE_URL = "https://api.motus.com/v1"

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize Motus mock server.

        Args:
            base_url: Motus API base URL (defaults to DEFAULT_BASE_URL)
        """
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.factory = MotusMockDataFactory()

    def mock_get_driver(
        self,
        client_employee_id1: str = "12345",
        exists: bool = True,
        status: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mock GET /drivers/{id} endpoint.

        Args:
            client_employee_id1: Client employee ID
            exists: Whether the driver exists
            status: HTTP status code (auto-determined if not provided)
            data: Response data (auto-generated if not provided)
        """
        if status is None:
            status = 200 if exists else 404

        if data is None:
            if exists:
                data = self.factory.driver(client_employee_id1=client_employee_id1)
            else:
                data = {"error": "Not found", "message": f"Driver {client_employee_id1} not found"}

        pattern = rf"{re.escape(self.base_url)}/drivers/{re.escape(client_employee_id1)}$"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_get_all_drivers(
        self,
        drivers: Optional[List[Dict[str, Any]]] = None,
        status: int = 200,
    ) -> None:
        """
        Mock GET /drivers endpoint (list all drivers).

        Args:
            drivers: List of driver data
            status: HTTP status code
        """
        if drivers is None:
            drivers = [
                self.factory.driver(client_employee_id1="12345"),
                self.factory.driver(client_employee_id1="67890"),
            ]

        pattern = rf"{re.escape(self.base_url)}/drivers$"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=drivers,
            status=status,
        )

    def mock_create_driver(
        self,
        status: int = 201,
        data: Optional[Dict[str, Any]] = None,
        client_employee_id1: str = "12345",
    ) -> None:
        """
        Mock POST /drivers endpoint.

        Args:
            status: HTTP status code
            data: Response data
            client_employee_id1: Client employee ID for response
        """
        if data is None:
            data = {
                "clientEmployeeId1": client_employee_id1,
                "message": "Driver created successfully",
            }

        pattern = rf"{re.escape(self.base_url)}/drivers$"

        responses.add(
            responses.POST,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_update_driver(
        self,
        client_employee_id1: str = "12345",
        status: int = 200,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mock PUT /drivers/{id} endpoint.

        Args:
            client_employee_id1: Client employee ID
            status: HTTP status code
            data: Response data
        """
        if data is None:
            data = {
                "clientEmployeeId1": client_employee_id1,
                "message": "Driver updated successfully",
            }

        pattern = rf"{re.escape(self.base_url)}/drivers/{re.escape(client_employee_id1)}$"

        responses.add(
            responses.PUT,
            re.compile(pattern),
            json=data,
            status=status,
        )

    def mock_token_endpoint(
        self,
        access_token: str = "test-jwt-token",
        expires_in: int = 3600,
        status: int = 200,
        token_url: str = "https://api.motus.com/tokenservice/token/api",
    ) -> None:
        """
        Mock token endpoint.

        Args:
            access_token: JWT access token
            expires_in: Token expiration in seconds
            status: HTTP status code
            token_url: Token endpoint URL
        """
        data = self.factory.token_response(
            access_token=access_token,
            expires_in=expires_in,
        )

        responses.add(
            responses.POST,
            re.compile(rf"{re.escape(token_url)}.*"),
            json=data,
            status=status,
        )

    def mock_upsert_new_driver(
        self,
        client_employee_id1: str = "12345",
    ) -> None:
        """
        Set up mocks for inserting a new driver (driver doesn't exist).

        Args:
            client_employee_id1: Client employee ID
        """
        self.mock_get_driver(client_employee_id1, exists=False)
        self.mock_create_driver(client_employee_id1=client_employee_id1)

    def mock_upsert_existing_driver(
        self,
        client_employee_id1: str = "12345",
    ) -> None:
        """
        Set up mocks for updating an existing driver.

        Args:
            client_employee_id1: Client employee ID
        """
        self.mock_get_driver(client_employee_id1, exists=True)
        self.mock_update_driver(client_employee_id1)

    def mock_validation_error(
        self,
        field: str = "email",
        message: str = "Invalid email format",
    ) -> None:
        """
        Mock create/update returning validation error.

        Args:
            field: Field that failed validation
            message: Error message
        """
        error_data = self.factory.validation_error(field=field, message=message)

        pattern = rf"{re.escape(self.base_url)}/drivers.*"

        responses.add(
            responses.POST,
            re.compile(pattern),
            json=error_data,
            status=400,
        )

        responses.add(
            responses.PUT,
            re.compile(pattern),
            json=error_data,
            status=400,
        )

    def mock_rate_limit(
        self,
        retry_after: int = 60,
    ) -> None:
        """
        Mock rate limit (429) response.

        Args:
            retry_after: Seconds to wait before retrying
        """
        error_data = self.factory.rate_limit_error(retry_after=retry_after)

        pattern = rf"{re.escape(self.base_url)}/drivers.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=error_data,
            status=429,
            headers={"Retry-After": str(retry_after)},
        )

        responses.add(
            responses.POST,
            re.compile(pattern),
            json=error_data,
            status=429,
            headers={"Retry-After": str(retry_after)},
        )

        responses.add(
            responses.PUT,
            re.compile(pattern),
            json=error_data,
            status=429,
            headers={"Retry-After": str(retry_after)},
        )

    def mock_rate_limit_then_success(
        self,
        client_employee_id1: str = "12345",
        retry_after: int = 1,
    ) -> None:
        """
        Mock rate limit (429) followed by success.

        First call returns 429, subsequent calls succeed.

        Args:
            client_employee_id1: Client employee ID
            retry_after: Seconds to wait before retrying
        """
        error_data = self.factory.rate_limit_error(retry_after=retry_after)

        # First GET call returns 429
        pattern = rf"{re.escape(self.base_url)}/drivers/{re.escape(client_employee_id1)}$"
        responses.add(
            responses.GET,
            re.compile(pattern),
            json=error_data,
            status=429,
            headers={"Retry-After": str(retry_after)},
        )

        # Second GET call succeeds (driver not found)
        responses.add(
            responses.GET,
            re.compile(pattern),
            json={"error": "Not found"},
            status=404,
        )

        # POST succeeds
        self.mock_create_driver(client_employee_id1=client_employee_id1)

    def mock_auth_error(self) -> None:
        """Mock authentication error (401) response."""
        error_data = self.factory.auth_error()

        pattern = rf"{re.escape(self.base_url)}/drivers.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=error_data,
            status=401,
        )

        responses.add(
            responses.POST,
            re.compile(pattern),
            json=error_data,
            status=401,
        )

        responses.add(
            responses.PUT,
            re.compile(pattern),
            json=error_data,
            status=401,
        )

    def mock_server_error(self) -> None:
        """Mock server error (500) response."""
        error_data = {"code": 500, "message": "Internal Server Error"}

        pattern = rf"{re.escape(self.base_url)}/drivers.*"

        responses.add(
            responses.GET,
            re.compile(pattern),
            json=error_data,
            status=500,
        )

        responses.add(
            responses.POST,
            re.compile(pattern),
            json=error_data,
            status=500,
        )

        responses.add(
            responses.PUT,
            re.compile(pattern),
            json=error_data,
            status=500,
        )

    def mock_terminated_driver_update(
        self,
        client_employee_id1: str = "12345",
        end_date: str = "2024-03-01",
    ) -> None:
        """
        Set up mocks for updating a driver with termination date.

        Args:
            client_employee_id1: Client employee ID
            end_date: Termination end date
        """
        # Driver exists
        driver_data = self.factory.driver(
            client_employee_id1=client_employee_id1,
            end_date=end_date,
        )
        self.mock_get_driver(client_employee_id1, exists=True, data=driver_data)

        # Update succeeds
        update_response = {
            "clientEmployeeId1": client_employee_id1,
            "endDate": end_date,
            "message": "Driver updated with termination date",
        }
        self.mock_update_driver(client_employee_id1, data=update_response)

    def mock_leave_driver_update(
        self,
        client_employee_id1: str = "12345",
        leave_start_date: str = "2024-02-01",
        leave_end_date: Optional[str] = None,
    ) -> None:
        """
        Set up mocks for updating a driver with leave dates.

        Args:
            client_employee_id1: Client employee ID
            leave_start_date: Leave start date
            leave_end_date: Leave end date (None for indefinite)
        """
        # Driver exists
        driver_data = self.factory.driver(
            client_employee_id1=client_employee_id1,
            leave_start_date=leave_start_date,
            leave_end_date=leave_end_date,
        )
        self.mock_get_driver(client_employee_id1, exists=True, data=driver_data)

        # Update succeeds
        update_response = {
            "clientEmployeeId1": client_employee_id1,
            "leaveStartDate": leave_start_date,
            "leaveEndDate": leave_end_date,
            "message": "Driver updated with leave dates",
        }
        self.mock_update_driver(client_employee_id1, data=update_response)
