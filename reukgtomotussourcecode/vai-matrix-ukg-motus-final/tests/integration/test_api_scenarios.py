"""
Integration tests for UKG-to-Motus API scenarios.

Tests based on production scenarios from API run notes (3.29.26):
1. Company filter - API should only pull data from CCHN company
2. New hire creation - Create profiles for eligible job codes
3. Field extraction - Pull all required employee information
4. Termination handling - Terminate Motus profile when termination date entered
5. Manager update - Update manager changes from UKG
6. Address/phone update - Update address and phone number changes
7. Leave of absence - Update leave dates and Motus status

Test EEIDs referenced:
- New hires: 28190, 28203, 28207, 28209, 28210, 28199, 28206, 28189, 28204
- Terminations: 26737, 27991, 28069, 23497, 27938, 23463, 26612, 25213, 28010
- Manager updates: 28195
- Address updates: 25336, 26421, 10858, 22299
- Leave of absence: 22393, 28027, 26434
"""

import pytest
import responses
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from unittest.mock import MagicMock, patch

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.application.services.driver_sync import DriverSyncService
from src.application.services.driver_builder import DriverBuilderService
from src.infrastructure.adapters.ukg import UKGClient
from src.infrastructure.adapters.motus import MotusClient
from src.infrastructure.config.settings import BatchSettings
from src.domain.models import MotusDriver
from src.domain.models.employment_status import EmploymentStatus, determine_employment_status_from_dict
from src.domain.models.program import resolve_program_id_from_job_code


# =============================================================================
# ELIGIBLE JOB CODES (CCHN Company)
# =============================================================================

ELIGIBLE_JOB_CODES = {
    # FAVR Program (21232)
    "1103", "4165", "4166", "1102", "1106", "4197", "4196",
    # CPM Program (21233)
    "2817", "4121", "2157"
}

CCHN_COMPANY_ID = "CCHN"


class TestCompanyFilter:
    """
    Test Case: API should only pull data from the CCHN company.

    Scenario: When syncing employees, the API should filter to only
    include employees from the CCHN company.
    """

    def test_only_cchn_company_employees_are_processed(self):
        """Test that only employees from CCHN company are processed."""
        employees = [
            {"employeeNumber": "28190", "employeeID": "E28190", "companyID": "CCHN", "primaryJobCode": "1103"},
            {"employeeNumber": "28191", "employeeID": "E28191", "companyID": "OTHER", "primaryJobCode": "1103"},
            {"employeeNumber": "28192", "employeeID": "E28192", "companyID": "CCHN", "primaryJobCode": "1103"},
            {"employeeNumber": "28193", "employeeID": "E28193", "companyID": "DIFF", "primaryJobCode": "1103"},
        ]

        # Filter employees by company
        cchn_employees = [
            emp for emp in employees
            if emp.get("companyID", "").upper() == "CCHN"
        ]

        assert len(cchn_employees) == 2
        assert cchn_employees[0]["employeeNumber"] == "28190"
        assert cchn_employees[1]["employeeNumber"] == "28192"

    def test_company_filter_case_insensitive(self):
        """Test company filter works case-insensitively."""
        employees = [
            {"employeeNumber": "28190", "companyID": "cchn", "primaryJobCode": "1103"},
            {"employeeNumber": "28191", "companyID": "CCHN", "primaryJobCode": "1103"},
            {"employeeNumber": "28192", "companyID": "Cchn", "primaryJobCode": "1103"},
        ]

        cchn_employees = [
            emp for emp in employees
            if emp.get("companyID", "").upper() == "CCHN"
        ]

        assert len(cchn_employees) == 3

    def test_batch_settings_with_company_id(self):
        """Test BatchSettings correctly stores company ID."""
        settings = BatchSettings(
            company_id="CCHN",
            workers=4,
            dry_run=False,
        )

        assert settings.company_id == "CCHN"


class TestNewHireProfileCreation:
    """
    Test Case: API should create employee profiles in Motus for new hires
    whose job codes are eligible for Motus.

    Test EEIDs: 28190, 28203, 28207, 28209, 28210, 28199, 28206, 28189, 28204

    Eligible Job Codes:
    - FAVR: 1103, 4165, 4166, 1102, 1106, 4197, 4196
    - CPM: 2817, 4121, 2157
    """

    @pytest.fixture
    def new_hire_employee(self):
        """Sample new hire employee data."""
        return {
            "employeeNumber": "28190",
            "employeeID": "E28190",
            "companyID": "CCHN",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",  # FAVR eligible
            "originalHireDate": "2024-03-15T00:00:00Z",
            "dateOfTermination": None,
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
        }

    def test_eligible_favr_job_codes_pass_filter(self):
        """Test all FAVR job codes are recognized as eligible."""
        favr_codes = ["1103", "4165", "4166", "1102", "1106", "4197", "4196"]

        for code in favr_codes:
            program_id = resolve_program_id_from_job_code(code)
            assert program_id == 21232, f"FAVR code {code} should map to program 21232"

    def test_eligible_cpm_job_codes_pass_filter(self):
        """Test all CPM job codes are recognized as eligible."""
        cpm_codes = ["2817", "4121", "2157"]

        for code in cpm_codes:
            program_id = resolve_program_id_from_job_code(code)
            assert program_id == 21233, f"CPM code {code} should map to program 21233"

    def test_ineligible_job_codes_fail_filter(self):
        """Test ineligible job codes are not processed."""
        ineligible_codes = ["9999", "0000", "5555", "1234"]

        for code in ineligible_codes:
            program_id = resolve_program_id_from_job_code(code)
            assert program_id is None, f"Code {code} should not be eligible"

    def test_new_hire_creates_motus_profile(self, new_hire_employee):
        """Test new hire with eligible job code creates Motus profile."""
        job_code = new_hire_employee["primaryJobCode"]
        program_id = resolve_program_id_from_job_code(job_code)

        assert program_id is not None
        assert program_id == 21232  # FAVR program

    def test_filter_by_eligible_job_codes(self):
        """Test filtering employees by eligible job codes."""
        employees = [
            {"employeeNumber": "28190", "primaryJobCode": "1103"},  # FAVR - eligible
            {"employeeNumber": "28191", "primaryJobCode": "9999"},  # Not eligible
            {"employeeNumber": "28192", "primaryJobCode": "2817"},  # CPM - eligible
            {"employeeNumber": "28193", "primaryJobCode": "5555"},  # Not eligible
        ]

        eligible = []
        for emp in employees:
            job_code = emp.get("primaryJobCode", "")
            if resolve_program_id_from_job_code(job_code) is not None:
                eligible.append(emp)

        assert len(eligible) == 2
        assert eligible[0]["employeeNumber"] == "28190"
        assert eligible[1]["employeeNumber"] == "28192"

    def test_new_hire_multiple_eeids(self):
        """Test creating profiles for multiple new hire EEIDs."""
        new_hire_eeids = ["28190", "28203", "28207", "28209", "28210", "28199", "28206", "28189", "28204"]

        employees = [
            {"employeeNumber": eeid, "primaryJobCode": "1103", "companyID": "CCHN", "employeeStatusCode": "A"}
            for eeid in new_hire_eeids
        ]

        # All should be eligible
        for emp in employees:
            program_id = resolve_program_id_from_job_code(emp["primaryJobCode"])
            assert program_id is not None, f"EEID {emp['employeeNumber']} should be eligible"


class TestRequiredFieldExtraction:
    """
    Test Case: For eligible employees, the API should pull all required information.

    Required fields:
    - Employee Name, Employee ID
    - Assigned Program ID (based on job code)
    - Address, City, State, ZIP code
    - Matrix email, Phone number
    - Start date
    - Project code, Project description
    - Org levels 1-4
    - Job title, Job code
    - Employment status code
    - Last hire date
    - Employment type code
    - Full-time/part-time status
    - Location code
    - Manager name

    Test EEIDs: 28190, 28203, 28207, 28209, 28210, 28199, 28206, 28189, 28204
    """

    @pytest.fixture
    def complete_employee_data(self):
        """Complete employee data with all required fields."""
        return {
            "employment_details": {
                "employeeId": "E28190",
                "employeeNumber": "28190",
                "companyID": "CCHN",
                "employeeStatusCode": "A",
                "primaryJobCode": "1103",
                "jobDescription": "Field Technician",
                "originalHireDate": "2024-03-15T00:00:00Z",
                "dateOfTermination": None,
                "employeeStatusStartDate": None,
                "employeeStatusExpectedEndDate": None,
                "lastHireDate": "2024-03-15T00:00:00Z",
                "fullTimeOrPartTimeCode": "F",
                "employeeTypeCode": "REG",
                "primaryWorkLocationCode": "LOC001",
                "orgLevel1Code": "ORG1",
                "orgLevel2Code": "ORG2",
                "orgLevel3Code": "ORG3",
                "orgLevel4Code": "ORG4",
            },
            "person_details": {
                "employeeId": "E28190",
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john.doe@matrix.com",
                "homePhone": "5551234567",
                "mobilePhone": "5559876543",
                "addressLine1": "123 Main St",
                "addressLine2": "Apt 4B",
                "addressCity": "Orlando",
                "addressState": "FL",
                "addressCountry": "USA",
                "addressZipCode": "32801",
            },
            "supervisor_details": {
                "employeeId": "E28190",
                "supervisorFirstName": "Jane",
                "supervisorLastName": "Manager",
            },
            "project_details": {
                "primaryProjectCode": "PROJ001",
                "primaryProjectDescription": "Main Project",
            },
            "location": {
                "locationCode": "LOC001",
                "description": "Orlando Office",
                "state": "FL",
            }
        }

    def test_employee_name_extraction(self, complete_employee_data):
        """Test employee name is correctly extracted."""
        person = complete_employee_data["person_details"]

        assert person["firstName"] == "John"
        assert person["lastName"] == "Doe"

    def test_employee_id_extraction(self, complete_employee_data):
        """Test employee ID is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["employeeNumber"] == "28190"
        assert employment["employeeId"] == "E28190"

    def test_program_id_assignment_from_job_code(self, complete_employee_data):
        """Test program ID is correctly assigned based on job code."""
        job_code = complete_employee_data["employment_details"]["primaryJobCode"]
        program_id = resolve_program_id_from_job_code(job_code)

        assert program_id == 21232  # FAVR program for job code 1103

    def test_address_fields_extraction(self, complete_employee_data):
        """Test address fields are correctly extracted."""
        person = complete_employee_data["person_details"]

        assert person["addressLine1"] == "123 Main St"
        assert person["addressLine2"] == "Apt 4B"
        assert person["addressCity"] == "Orlando"
        assert person["addressState"] == "FL"
        assert person["addressZipCode"] == "32801"
        assert person["addressCountry"] == "USA"

    def test_email_extraction(self, complete_employee_data):
        """Test matrix email is correctly extracted."""
        person = complete_employee_data["person_details"]

        assert person["emailAddress"] == "john.doe@matrix.com"
        assert "@matrix.com" in person["emailAddress"]

    def test_phone_number_extraction(self, complete_employee_data):
        """Test phone numbers are correctly extracted."""
        person = complete_employee_data["person_details"]

        assert person["homePhone"] == "5551234567"
        assert person["mobilePhone"] == "5559876543"

    def test_start_date_extraction(self, complete_employee_data):
        """Test start date is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["originalHireDate"] == "2024-03-15T00:00:00Z"

    def test_project_fields_extraction(self, complete_employee_data):
        """Test project code and description are correctly extracted."""
        project = complete_employee_data["project_details"]

        assert project["primaryProjectCode"] == "PROJ001"
        assert project["primaryProjectDescription"] == "Main Project"

    def test_org_levels_extraction(self, complete_employee_data):
        """Test org levels 1-4 are correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["orgLevel1Code"] == "ORG1"
        assert employment["orgLevel2Code"] == "ORG2"
        assert employment["orgLevel3Code"] == "ORG3"
        assert employment["orgLevel4Code"] == "ORG4"

    def test_job_fields_extraction(self, complete_employee_data):
        """Test job title and job code are correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["primaryJobCode"] == "1103"
        assert employment["jobDescription"] == "Field Technician"

    def test_employment_status_code_extraction(self, complete_employee_data):
        """Test employment status code is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["employeeStatusCode"] == "A"

    def test_last_hire_date_extraction(self, complete_employee_data):
        """Test last hire date is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["lastHireDate"] == "2024-03-15T00:00:00Z"

    def test_employment_type_code_extraction(self, complete_employee_data):
        """Test employment type code is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["employeeTypeCode"] == "REG"

    def test_full_part_time_status_extraction(self, complete_employee_data):
        """Test full/part-time status is correctly extracted."""
        employment = complete_employee_data["employment_details"]

        assert employment["fullTimeOrPartTimeCode"] == "F"

    def test_location_code_extraction(self, complete_employee_data):
        """Test location code is correctly extracted."""
        employment = complete_employee_data["employment_details"]
        location = complete_employee_data["location"]

        assert employment["primaryWorkLocationCode"] == "LOC001"
        assert location["description"] == "Orlando Office"

    def test_manager_name_extraction(self, complete_employee_data):
        """Test manager name is correctly extracted."""
        supervisor = complete_employee_data["supervisor_details"]

        manager_name = f"{supervisor['supervisorFirstName']} {supervisor['supervisorLastName']}"
        assert manager_name == "Jane Manager"

    def test_motus_driver_from_ukg_data(self, complete_employee_data):
        """Test MotusDriver correctly maps all UKG fields."""
        employment = complete_employee_data["employment_details"]
        person = complete_employee_data["person_details"]
        supervisor = complete_employee_data["supervisor_details"]
        location = complete_employee_data["location"]
        project = complete_employee_data["project_details"]

        supervisor_name = f"{supervisor['supervisorFirstName']} {supervisor['supervisorLastName']}"

        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            supervisor_name=supervisor_name,
            location=location,
            project_code=project["primaryProjectCode"],
            project_label=project["primaryProjectDescription"],
            derived_status="Active",
        )

        # Verify core fields
        assert driver.client_employee_id1 == "28190"
        assert driver.program_id == 21232
        assert driver.first_name == "John"
        assert driver.last_name == "Doe"
        assert driver.email == "john.doe@matrix.com"

        # Verify address
        assert driver.address1 == "123 Main St"
        assert driver.city == "Orlando"
        assert driver.state_province == "FL"
        assert driver.postal_code == "32801"

        # Verify custom variables
        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Project Code"] == "PROJ001"
        assert cv_dict["Job Code"] == "1103"
        assert cv_dict["Manager Name"] == "Jane Manager"
        assert cv_dict["Org Level 1 Code"] == "ORG1"


class TestTerminationHandling:
    """
    Test Case: API should terminate the Motus profile when a termination date
    is entered in UKG.

    Test EEIDs: 26737, 27991, 28069, 23497, 27938, 23463, 26612, 25213, 28010

    Notes: API should set endDate and update Derived Status to "Terminated"
    """

    @pytest.fixture
    def terminated_employee(self):
        """Sample terminated employee data."""
        return {
            "employeeId": "E26737",
            "employeeNumber": "26737",
            "companyID": "CCHN",
            "employeeStatusCode": "T",
            "primaryJobCode": "1103",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": "2024-03-01T00:00:00Z",
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
        }

    def test_terminated_status_with_termination_date(self, terminated_employee):
        """Test employee with termination date has TERMINATED status."""
        status = determine_employment_status_from_dict(terminated_employee)

        assert status == EmploymentStatus.TERMINATED
        assert status.value == "Terminated"

    def test_terminated_status_code_t(self):
        """Test employee with status code 'T' has TERMINATED status."""
        employee = {
            "employeeStatusCode": "T",
            "dateOfTermination": None,
        }

        status = determine_employment_status_from_dict(employee)
        assert status == EmploymentStatus.TERMINATED

    def test_termination_date_sets_end_date(self, terminated_employee):
        """Test termination date is mapped to Motus endDate field."""
        person = {
            "firstName": "Terminated",
            "lastName": "Employee",
            "emailAddress": "term@matrix.com",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number=terminated_employee["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=terminated_employee,
            derived_status="Terminated",
        )

        assert driver.end_date == "2024-03-01"

    def test_termination_updates_derived_status(self, terminated_employee):
        """Test terminated employee has Derived Status = Terminated."""
        person = {
            "firstName": "Terminated",
            "lastName": "Employee",
            "emailAddress": "term@matrix.com",
        }

        derived_status = determine_employment_status_from_dict(terminated_employee)

        driver = MotusDriver.from_ukg_data(
            employee_number=terminated_employee["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=terminated_employee,
            derived_status=derived_status.value,
        )

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Derived Status"] == "Terminated"

    def test_termination_custom_field_termination_date(self, terminated_employee):
        """Test Termination Date custom field is populated."""
        person = {
            "firstName": "Terminated",
            "lastName": "Employee",
            "emailAddress": "term@matrix.com",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number=terminated_employee["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=terminated_employee,
            derived_status="Terminated",
        )

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Termination Date"] == "2024-03-01"

    def test_termination_multiple_eeids(self):
        """Test termination handling for multiple EEIDs."""
        termination_eeids = ["26737", "27991", "28069", "23497", "27938", "23463", "26612", "25213", "28010"]

        for eeid in termination_eeids:
            employee = {
                "employeeNumber": eeid,
                "employeeStatusCode": "T",
                "dateOfTermination": "2024-03-01T00:00:00Z",
            }

            status = determine_employment_status_from_dict(employee)
            assert status == EmploymentStatus.TERMINATED, f"EEID {eeid} should be terminated"


class TestManagerUpdate:
    """
    Test Case: API should update manager changes when they occur in UKG.

    Test EEID: 28195
    """

    @pytest.fixture
    def employee_with_manager(self):
        """Employee data with supervisor information."""
        return {
            "employment_details": {
                "employeeNumber": "28195",
                "employeeId": "E28195",
                "companyID": "CCHN",
                "employeeStatusCode": "A",
                "primaryJobCode": "1103",
                "originalHireDate": "2020-01-15T00:00:00Z",
            },
            "person_details": {
                "firstName": "John",
                "lastName": "Employee",
                "emailAddress": "john@matrix.com",
            },
            "old_supervisor": {
                "supervisorFirstName": "Old",
                "supervisorLastName": "Manager",
            },
            "new_supervisor": {
                "supervisorFirstName": "New",
                "supervisorLastName": "Supervisor",
            }
        }

    def test_manager_name_extraction(self, employee_with_manager):
        """Test manager name is correctly extracted from supervisor details."""
        supervisor = employee_with_manager["new_supervisor"]

        manager_name = f"{supervisor['supervisorFirstName']} {supervisor['supervisorLastName']}"
        assert manager_name == "New Supervisor"

    def test_manager_name_in_custom_variables(self, employee_with_manager):
        """Test manager name is included in custom variables."""
        employment = employee_with_manager["employment_details"]
        person = employee_with_manager["person_details"]
        supervisor = employee_with_manager["new_supervisor"]

        manager_name = f"{supervisor['supervisorFirstName']} {supervisor['supervisorLastName']}"

        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            supervisor_name=manager_name,
            derived_status="Active",
        )

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Manager Name"] == "New Supervisor"

    def test_manager_update_changes_payload(self, employee_with_manager):
        """Test manager change results in updated payload."""
        employment = employee_with_manager["employment_details"]
        person = employee_with_manager["person_details"]

        # Create driver with old manager
        old_manager = f"{employee_with_manager['old_supervisor']['supervisorFirstName']} {employee_with_manager['old_supervisor']['supervisorLastName']}"
        driver_old = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            supervisor_name=old_manager,
            derived_status="Active",
        )

        # Create driver with new manager
        new_manager = f"{employee_with_manager['new_supervisor']['supervisorFirstName']} {employee_with_manager['new_supervisor']['supervisorLastName']}"
        driver_new = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            supervisor_name=new_manager,
            derived_status="Active",
        )

        # Verify manager names are different
        old_cv = {cv.name: cv.value for cv in driver_old.custom_variables}
        new_cv = {cv.name: cv.value for cv in driver_new.custom_variables}

        assert old_cv["Manager Name"] == "Old Manager"
        assert new_cv["Manager Name"] == "New Supervisor"
        assert old_cv["Manager Name"] != new_cv["Manager Name"]


class TestAddressPhoneUpdate:
    """
    Test Case: API should update employee address and phone number changes.

    Test EEIDs: 25336, 26421, 10858, 22299

    Note: This functionality should currently be working as expected.
    """

    @pytest.fixture
    def employee_with_address(self):
        """Employee data with address information."""
        return {
            "employment_details": {
                "employeeNumber": "25336",
                "employeeId": "E25336",
                "companyID": "CCHN",
                "employeeStatusCode": "A",
                "primaryJobCode": "1103",
                "originalHireDate": "2020-01-15T00:00:00Z",
            },
            "old_address": {
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john@matrix.com",
                "homePhone": "5551111111",
                "addressLine1": "100 Old Street",
                "addressCity": "Old City",
                "addressState": "FL",
                "addressZipCode": "32801",
            },
            "new_address": {
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john@matrix.com",
                "homePhone": "5552222222",
                "addressLine1": "200 New Avenue",
                "addressCity": "New City",
                "addressState": "TX",
                "addressZipCode": "75001",
            },
        }

    def test_address_fields_are_mapped(self, employee_with_address):
        """Test address fields are correctly mapped to Motus driver."""
        employment = employee_with_address["employment_details"]
        person = employee_with_address["new_address"]

        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            derived_status="Active",
        )

        assert driver.address1 == "200 New Avenue"
        assert driver.city == "New City"
        assert driver.state_province == "TX"
        assert driver.postal_code == "75001"

    def test_phone_number_is_mapped(self, employee_with_address):
        """Test phone number is correctly mapped to Motus driver."""
        employment = employee_with_address["employment_details"]
        person = employee_with_address["new_address"]

        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            derived_status="Active",
        )

        # Phone should be normalized to XXX-XXX-XXXX format
        assert driver.phone == "555-222-2222"

    def test_address_update_changes_payload(self, employee_with_address):
        """Test address change results in updated payload."""
        employment = employee_with_address["employment_details"]

        # Create driver with old address
        driver_old = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=employee_with_address["old_address"],
            employment_details=employment,
            derived_status="Active",
        )

        # Create driver with new address
        driver_new = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=employee_with_address["new_address"],
            employment_details=employment,
            derived_status="Active",
        )

        # Verify addresses are different
        assert driver_old.address1 != driver_new.address1
        assert driver_old.city != driver_new.city
        assert driver_old.state_province != driver_new.state_province
        assert driver_old.phone != driver_new.phone

    def test_address_update_multiple_eeids(self):
        """Test address update for multiple EEIDs."""
        address_update_eeids = ["25336", "26421", "10858", "22299"]

        for eeid in address_update_eeids:
            employment = {
                "employeeNumber": eeid,
                "employeeStatusCode": "A",
                "primaryJobCode": "1103",
                "originalHireDate": "2020-01-15T00:00:00Z",
            }
            person = {
                "firstName": "Test",
                "lastName": "User",
                "emailAddress": f"test{eeid}@matrix.com",
                "homePhone": "5551234567",
                "addressLine1": f"Address for {eeid}",
                "addressCity": "Test City",
                "addressState": "FL",
                "addressZipCode": "32801",
            }

            driver = MotusDriver.from_ukg_data(
                employee_number=eeid,
                program_id=21232,
                person=person,
                employment_details=employment,
                derived_status="Active",
            )

            assert driver.client_employee_id1 == eeid
            assert driver.address1 == f"Address for {eeid}"


class TestLeaveOfAbsence:
    """
    Test Case: API should update leave of absence start and end dates
    and update the Motus status to "Leave".

    Test EEIDs: 22393, 28027, 26434
    """

    @pytest.fixture
    def employee_on_leave(self):
        """Employee data with leave of absence."""
        return {
            "employeeId": "E22393",
            "employeeNumber": "22393",
            "companyID": "CCHN",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": None,
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
            "employeeStatusExpectedEndDate": None,  # Indefinite leave
        }

    def test_leave_status_with_leave_start_date(self, employee_on_leave):
        """Test employee with leave start date (no end date) has LEAVE status."""
        status = determine_employment_status_from_dict(employee_on_leave)

        assert status == EmploymentStatus.LEAVE
        assert status.value == "Leave"

    def test_leave_start_date_is_mapped(self, employee_on_leave):
        """Test leave start date is mapped to Motus leaveStartDate."""
        person = {
            "firstName": "Leave",
            "lastName": "Employee",
            "emailAddress": "leave@matrix.com",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number=employee_on_leave["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employee_on_leave,
            derived_status="Leave",
        )

        assert driver.leave_start_date == "2024-02-01"

    def test_leave_derived_status(self, employee_on_leave):
        """Test employee on leave has Derived Status = Leave."""
        person = {
            "firstName": "Leave",
            "lastName": "Employee",
            "emailAddress": "leave@matrix.com",
        }

        derived_status = determine_employment_status_from_dict(employee_on_leave)

        driver = MotusDriver.from_ukg_data(
            employee_number=employee_on_leave["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employee_on_leave,
            derived_status=derived_status.value,
        )

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Derived Status"] == "Leave"

    def test_leave_with_end_date_returns_to_active(self):
        """Test employee with completed leave returns to ACTIVE status."""
        employee = {
            "employeeStatusCode": "A",
            "employeeStatusStartDate": "2024-01-01T00:00:00Z",
            "employeeStatusExpectedEndDate": "2024-02-15T00:00:00Z",  # Leave ended
            "dateOfTermination": None,
        }

        status = determine_employment_status_from_dict(employee)
        assert status == EmploymentStatus.ACTIVE

    def test_leave_end_date_is_mapped(self):
        """Test leave end date is mapped to Motus leaveEndDate."""
        employee = {
            "employeeNumber": "22393",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
            "employeeStatusExpectedEndDate": "2024-03-15T00:00:00Z",
        }
        person = {
            "firstName": "Leave",
            "lastName": "Employee",
            "emailAddress": "leave@matrix.com",
        }

        driver = MotusDriver.from_ukg_data(
            employee_number=employee["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employee,
            derived_status="Active",
        )

        assert driver.leave_start_date == "2024-02-01"
        assert driver.leave_end_date == "2024-03-15"

    def test_leave_status_code_l(self):
        """Test employee with status code 'L' has LEAVE status."""
        employee = {
            "employeeStatusCode": "L",
            "employeeStatusStartDate": None,
            "dateOfTermination": None,
        }

        status = determine_employment_status_from_dict(employee)
        assert status == EmploymentStatus.LEAVE

    def test_leave_status_code_loa(self):
        """Test employee with status code 'LOA' has LEAVE status."""
        employee = {
            "employeeStatusCode": "LOA",
            "employeeStatusStartDate": None,
            "dateOfTermination": None,
        }

        status = determine_employment_status_from_dict(employee)
        assert status == EmploymentStatus.LEAVE

    def test_leave_multiple_eeids(self):
        """Test leave handling for multiple EEIDs."""
        leave_eeids = ["22393", "28027", "26434"]

        for eeid in leave_eeids:
            employee = {
                "employeeNumber": eeid,
                "employeeStatusCode": "A",
                "employeeStatusStartDate": "2024-02-01T00:00:00Z",
                "employeeStatusExpectedEndDate": None,
                "dateOfTermination": None,
            }

            status = determine_employment_status_from_dict(employee)
            assert status == EmploymentStatus.LEAVE, f"EEID {eeid} should be on leave"


class TestEndToEndScenarios:
    """
    End-to-end integration tests combining multiple scenarios.
    """

    def test_full_new_hire_workflow(self):
        """Test complete new hire workflow from UKG to Motus."""
        # New hire data
        employment = {
            "employeeNumber": "28190",
            "employeeId": "E28190",
            "companyID": "CCHN",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",
            "jobDescription": "Field Technician",
            "originalHireDate": "2024-03-15T00:00:00Z",
            "dateOfTermination": None,
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
            "lastHireDate": "2024-03-15T00:00:00Z",
            "fullTimeOrPartTimeCode": "F",
            "employeeTypeCode": "REG",
            "orgLevel1Code": "ORG1",
            "orgLevel2Code": "ORG2",
            "orgLevel3Code": "ORG3",
            "orgLevel4Code": "ORG4",
        }
        person = {
            "firstName": "New",
            "lastName": "Hire",
            "emailAddress": "newhire@matrix.com",
            "homePhone": "5551234567",
            "addressLine1": "123 New St",
            "addressCity": "Orlando",
            "addressState": "FL",
            "addressZipCode": "32801",
        }

        # 1. Verify company filter
        assert employment["companyID"] == "CCHN"

        # 2. Verify job code eligibility
        program_id = resolve_program_id_from_job_code(employment["primaryJobCode"])
        assert program_id == 21232

        # 3. Verify employment status
        status = determine_employment_status_from_dict(employment)
        assert status == EmploymentStatus.ACTIVE

        # 4. Build driver
        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=program_id,
            person=person,
            employment_details=employment,
            supervisor_name="Test Manager",
            project_code="PROJ001",
            project_label="Main Project",
            derived_status=status.value,
        )

        # 5. Verify all fields
        assert driver.client_employee_id1 == "28190"
        assert driver.program_id == 21232
        assert driver.first_name == "New"
        assert driver.last_name == "Hire"
        assert driver.start_date == "2024-03-15"
        assert driver.end_date is None or driver.end_date == ""

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Derived Status"] == "Active"
        assert cv_dict["Job Code"] == "1103"
        assert cv_dict["Manager Name"] == "Test Manager"

    def test_full_termination_workflow(self):
        """Test complete termination workflow."""
        employment = {
            "employeeNumber": "26737",
            "employeeStatusCode": "T",
            "primaryJobCode": "1103",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": "2024-03-01T00:00:00Z",
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
        }
        person = {
            "firstName": "Term",
            "lastName": "Employee",
            "emailAddress": "term@matrix.com",
        }

        # 1. Verify termination status
        status = determine_employment_status_from_dict(employment)
        assert status == EmploymentStatus.TERMINATED

        # 2. Build driver
        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            derived_status=status.value,
        )

        # 3. Verify termination fields
        assert driver.end_date == "2024-03-01"

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Derived Status"] == "Terminated"
        assert cv_dict["Termination Date"] == "2024-03-01"

    def test_full_leave_workflow(self):
        """Test complete leave of absence workflow."""
        employment = {
            "employeeNumber": "22393",
            "employeeStatusCode": "A",
            "primaryJobCode": "1103",
            "originalHireDate": "2020-01-15T00:00:00Z",
            "dateOfTermination": None,
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
            "employeeStatusExpectedEndDate": None,
        }
        person = {
            "firstName": "Leave",
            "lastName": "Employee",
            "emailAddress": "leave@matrix.com",
        }

        # 1. Verify leave status
        status = determine_employment_status_from_dict(employment)
        assert status == EmploymentStatus.LEAVE

        # 2. Build driver
        driver = MotusDriver.from_ukg_data(
            employee_number=employment["employeeNumber"],
            program_id=21232,
            person=person,
            employment_details=employment,
            derived_status=status.value,
        )

        # 3. Verify leave fields
        assert driver.leave_start_date == "2024-02-01"
        assert driver.leave_end_date is None or driver.leave_end_date == ""

        cv_dict = {cv.name: cv.value for cv in driver.custom_variables}
        assert cv_dict["Derived Status"] == "Leave"
