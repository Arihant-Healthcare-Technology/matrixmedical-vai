"""
Reusable mock data factories for tests.

Provides factory classes to generate consistent test data for UKG and Motus APIs.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class UKGMockDataFactory:
    """Factory for creating UKG API mock responses."""

    @staticmethod
    def employment_details(
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
        employee_id: str = "EMP001",
        job_code: str = "4154",
        status_code: str = "A",
        start_date: Optional[str] = None,
        termination_date: Optional[str] = None,
        leave_start_date: Optional[str] = None,
        leave_end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create employment details mock data.

        Args:
            employee_number: Employee number
            company_id: Company ID
            employee_id: Employee ID (internal)
            job_code: Primary job code
            status_code: Employment status code (A=Active, T=Terminated, L=Leave)
            start_date: Employment start date
            termination_date: Termination date (for terminated employees)
            leave_start_date: Leave start date (for employees on leave)
            leave_end_date: Leave end date
            **kwargs: Additional fields to include

        Returns:
            Employment details dictionary
        """
        return {
            "employeeId": employee_id,
            "employeeNumber": employee_number,
            "companyID": company_id,
            "employeeStatusCode": status_code,
            "primaryJobCode": job_code,
            "jobDescription": kwargs.get("job_description", "Field Technician"),
            "originalHireDate": start_date or "2020-01-15T00:00:00Z",
            "dateOfTermination": termination_date,
            "employeeStatusStartDate": leave_start_date,
            "employeeStatusExpectedEndDate": leave_end_date,
            "lastHireDate": kwargs.get("last_hire_date", "2020-01-15T00:00:00Z"),
            "fullTimeOrPartTimeCode": kwargs.get("ft_pt_code", "F"),
            "employeeTypeCode": kwargs.get("emp_type_code", "FTC"),
            "primaryWorkLocationCode": kwargs.get("location_code", "LOC001"),
            "orgLevel1Code": kwargs.get("org1", "DIV1"),
            "orgLevel2Code": kwargs.get("org2", "DEPT1"),
            "orgLevel3Code": kwargs.get("org3", "TEAM1"),
            "orgLevel4Code": kwargs.get("org4"),
        }

    @staticmethod
    def employee_employment_details(
        employee_number: str = "12345",
        company_id: str = "J9A6Y",
        employee_id: str = "EMP001",
        project_code: str = "PROJ001",
        project_description: str = "Main Project",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create employee employment details mock data.

        Args:
            employee_number: Employee number
            company_id: Company ID
            employee_id: Employee ID
            project_code: Primary project code
            project_description: Primary project description
            **kwargs: Additional fields

        Returns:
            Employee employment details dictionary
        """
        return {
            "employeeNumber": employee_number,
            "employeeID": employee_id,
            "companyID": company_id,
            "primaryProjectCode": project_code,
            "primaryProjectDescription": project_description,
            **kwargs,
        }

    @staticmethod
    def person_details(
        employee_id: str = "EMP001",
        first_name: str = "John",
        last_name: str = "Doe",
        email: str = "john.doe@example.com",
        state: str = "FL",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create person details mock data.

        Args:
            employee_id: Employee ID
            first_name: First name
            last_name: Last name
            email: Email address
            state: State code
            **kwargs: Additional fields

        Returns:
            Person details dictionary
        """
        return {
            "employeeId": employee_id,
            "firstName": first_name,
            "lastName": last_name,
            "emailAddress": email,
            "homePhone": kwargs.get("home_phone", "5551234567"),
            "mobilePhone": kwargs.get("mobile_phone", "5559876543"),
            "addressLine1": kwargs.get("address1", "123 Main St"),
            "addressLine2": kwargs.get("address2", "Apt 4B"),
            "addressCity": kwargs.get("city", "Orlando"),
            "addressState": state,
            "addressCountry": kwargs.get("country", "USA"),
            "addressZipCode": kwargs.get("postal_code", "32801"),
        }

    @staticmethod
    def supervisor_details(
        employee_id: str = "EMP001",
        supervisor_first_name: str = "Jane",
        supervisor_last_name: str = "Manager",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create supervisor details mock data.

        Args:
            employee_id: Employee ID
            supervisor_first_name: Supervisor first name
            supervisor_last_name: Supervisor last name
            **kwargs: Additional fields

        Returns:
            Supervisor details dictionary
        """
        return {
            "employeeId": employee_id,
            "supervisorFirstName": supervisor_first_name,
            "supervisorLastName": supervisor_last_name,
            "supervisorEmployeeId": kwargs.get("supervisor_id", "MGR001"),
            "supervisorEmployeeNumber": kwargs.get("supervisor_number", "99999"),
        }

    @staticmethod
    def location(
        code: str = "LOC001",
        description: str = "Orlando Office",
        state: str = "FL",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create location mock data.

        Args:
            code: Location code
            description: Location description
            state: State code
            **kwargs: Additional fields

        Returns:
            Location details dictionary
        """
        return {
            "locationCode": code,
            "description": description,
            "state": state,
            "country": kwargs.get("country", "USA"),
        }

    @classmethod
    def active_employee(
        cls,
        employee_number: str = "12345",
        **kwargs: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Create complete mock data for an active employee.

        Returns:
            Dictionary with all UKG data endpoints
        """
        emp_id = kwargs.get("employee_id", "EMP001")
        company_id = kwargs.get("company_id", "J9A6Y")

        return {
            "employment": cls.employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
                status_code="A",
                **kwargs,
            ),
            "employee_employment": cls.employee_employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
            ),
            "person": cls.person_details(employee_id=emp_id, **kwargs),
            "supervisor": cls.supervisor_details(employee_id=emp_id),
            "location": cls.location(),
        }

    @classmethod
    def terminated_employee(
        cls,
        employee_number: str = "12345",
        termination_date: str = "2024-03-01T00:00:00Z",
        **kwargs: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Create complete mock data for a terminated employee.

        Returns:
            Dictionary with all UKG data endpoints
        """
        emp_id = kwargs.get("employee_id", "EMP001")
        company_id = kwargs.get("company_id", "J9A6Y")

        return {
            "employment": cls.employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
                status_code="T",
                termination_date=termination_date,
                **kwargs,
            ),
            "employee_employment": cls.employee_employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
            ),
            "person": cls.person_details(employee_id=emp_id, **kwargs),
            "supervisor": cls.supervisor_details(employee_id=emp_id),
            "location": cls.location(),
        }

    @classmethod
    def leave_employee(
        cls,
        employee_number: str = "12345",
        leave_start_date: str = "2024-02-01T00:00:00Z",
        leave_end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Create complete mock data for an employee on leave.

        Returns:
            Dictionary with all UKG data endpoints
        """
        emp_id = kwargs.get("employee_id", "EMP001")
        company_id = kwargs.get("company_id", "J9A6Y")

        return {
            "employment": cls.employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
                status_code="A",
                leave_start_date=leave_start_date,
                leave_end_date=leave_end_date,
                **kwargs,
            ),
            "employee_employment": cls.employee_employment_details(
                employee_number=employee_number,
                employee_id=emp_id,
                company_id=company_id,
            ),
            "person": cls.person_details(employee_id=emp_id, **kwargs),
            "supervisor": cls.supervisor_details(employee_id=emp_id),
            "location": cls.location(),
        }


class MotusMockDataFactory:
    """Factory for creating Motus API mock responses."""

    @staticmethod
    def driver(
        client_employee_id1: str = "12345",
        program_id: int = 21233,
        first_name: str = "John",
        last_name: str = "Doe",
        email: str = "john.doe@example.com",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a Motus driver mock data.

        Args:
            client_employee_id1: Primary employee ID
            program_id: Motus program ID (21232=FAVR, 21233=CPM)
            first_name: Driver first name
            last_name: Driver last name
            email: Driver email
            **kwargs: Additional fields

        Returns:
            Driver dictionary matching Motus API schema
        """
        return {
            "clientEmployeeId1": client_employee_id1,
            "clientEmployeeId2": kwargs.get("client_employee_id2"),
            "programId": program_id,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "address1": kwargs.get("address1", "123 Main St"),
            "address2": kwargs.get("address2", "Apt 4B"),
            "city": kwargs.get("city", "Orlando"),
            "stateProvince": kwargs.get("state_province", "FL"),
            "country": kwargs.get("country", "US"),
            "postalCode": kwargs.get("postal_code", "32801"),
            "phone": kwargs.get("phone", "555-123-4567"),
            "alternatePhone": kwargs.get("alternate_phone", ""),
            "startDate": kwargs.get("start_date", "2020-01-15"),
            "endDate": kwargs.get("end_date"),
            "leaveStartDate": kwargs.get("leave_start_date"),
            "leaveEndDate": kwargs.get("leave_end_date"),
            "annualBusinessMiles": kwargs.get("annual_business_miles", 0),
            "commuteDeductionType": kwargs.get("commute_deduction_type"),
            "commuteDeductionCap": kwargs.get("commute_deduction_cap"),
            "customVariables": kwargs.get("custom_variables", []),
        }

    @staticmethod
    def driver_with_custom_variables(
        client_employee_id1: str = "12345",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a driver with standard custom variables.

        Returns:
            Driver dictionary with custom variables
        """
        custom_vars = [
            {"name": "Project Code", "value": "PROJ001"},
            {"name": "Project", "value": "Main Project"},
            {"name": "Job Code", "value": "4154"},
            {"name": "Job", "value": "Field Technician"},
            {"name": "Location Code", "value": "Orlando Office"},
            {"name": "Location", "value": "FL"},
            {"name": "Org Level 1 Code", "value": "DIV1"},
            {"name": "Org Level 2 Code", "value": "DEPT1"},
            {"name": "Org Level 3 Code", "value": "TEAM1"},
            {"name": "Org Level 4 Code", "value": ""},
            {"name": "Full/Part Time Code", "value": "F"},
            {"name": "Employment Type Code", "value": "FTC"},
            {"name": "Employment Status Code", "value": "A"},
            {"name": "Last Hire", "value": "2020-01-15"},
            {"name": "Termination Date", "value": ""},
            {"name": "Manager Name", "value": "Jane Manager"},
            {"name": "Derived Status", "value": "Active"},
        ]

        return MotusMockDataFactory.driver(
            client_employee_id1=client_employee_id1,
            custom_variables=custom_vars,
            **kwargs,
        )

    @staticmethod
    def error_response(
        code: int = 400,
        message: str = "Validation failed",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create an error response mock data.

        Args:
            code: Error code
            message: Error message
            **kwargs: Additional error details

        Returns:
            Error response dictionary
        """
        return {
            "code": code,
            "message": message,
            **kwargs,
        }

    @staticmethod
    def validation_error(
        field: str = "email",
        message: str = "Invalid email format",
    ) -> Dict[str, Any]:
        """
        Create a validation error response.

        Returns:
            Validation error dictionary
        """
        return {
            "code": 400,
            "message": f"Validation error: {field} - {message}",
        }

    @staticmethod
    def rate_limit_error(retry_after: int = 60) -> Dict[str, Any]:
        """
        Create a rate limit error response.

        Args:
            retry_after: Seconds to wait before retrying

        Returns:
            Rate limit error dictionary
        """
        return {
            "code": 429,
            "message": "Rate limit exceeded",
            "retryAfter": retry_after,
        }

    @staticmethod
    def auth_error() -> Dict[str, Any]:
        """
        Create an authentication error response.

        Returns:
            Auth error dictionary
        """
        return {
            "code": 401,
            "message": "Unauthorized - Invalid or expired token",
        }

    @staticmethod
    def token_response(
        access_token: str = "test-jwt-token",
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """
        Create a token endpoint response.

        Args:
            access_token: JWT access token
            expires_in: Token expiration in seconds

        Returns:
            Token response dictionary
        """
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
        }


# Convenience instances for direct use
ukg_factory = UKGMockDataFactory()
motus_factory = MotusMockDataFactory()
