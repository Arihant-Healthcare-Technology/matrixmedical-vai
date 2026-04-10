"""
Debug API for UKG-to-Motus data validation.

Provides REST endpoints for debugging data synchronization issues.
Includes comprehensive logging at each stage:
1. UKG API requests and responses
2. Data transformations
3. Motus API requests and responses
"""

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from src.application.services.driver_builder import DriverBuilderService
from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError
from src.domain.models import MotusDriver
from src.domain.models.employment_status import determine_employment_status_from_dict
from src.domain.models.program import JOBCODE_TO_PROGRAM, ProgramType, resolve_program_id_from_job_code
from src.infrastructure.adapters.motus import MotusClient
from src.infrastructure.adapters.ukg import UKGClient
from src.infrastructure.config.settings import MotusSettings, UKGSettings

from .logging_service import DebugLogger
from .models import (
    BuildDriverRequest,
    BuildDriverResponse,
    BuildDriverResponseWithTrace,
    CheckStatus,
    CompareRequest,
    CompareResponse,
    CompareResponseWithTrace,
    FieldDifference,
    HealthResponse,
    MotusDriverResponse,
    OverallStatus,
    RequestTraceModel,
    SyncRequest,
    SyncResponse,
    SyncResponseWithTrace,
    TransformationInfo,
    UKGDataResponse,
    ValidateScenarioRequest,
    ValidateScenarioResponse,
    ValidateScenarioResponseWithTrace,
    ValidationCheck,
    ValidationScenario,
)


# ============ App Setup ============

app = FastAPI(
    title="MOTUS Debug API",
    description="Debug API for validating UKG-to-Motus data synchronization",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============ Client Factory ============

def get_ukg_client() -> UKGClient:
    """Create UKG client from environment."""
    return UKGClient(debug=os.getenv("DEBUG", "0") == "1")


def get_motus_client() -> MotusClient:
    """Create Motus client from environment."""
    return MotusClient(debug=os.getenv("DEBUG", "0") == "1")


# ============ Health Endpoint ============

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


# ============ UKG Raw Data Endpoints ============

@app.get(
    "/ukg/employment-details/{employee_number}",
    response_model=UKGDataResponse,
    tags=["UKG Raw Data"],
)
async def get_ukg_employment_details(
    employee_number: str,
    company_id: str = Query(default="J9A6Y", description="UKG company ID"),
):
    """Get raw employment details from UKG."""
    try:
        client = get_ukg_client()
        data = client.get_employment_details(employee_number, company_id)
        return UKGDataResponse(
            success=bool(data),
            employee_number=employee_number,
            company_id=company_id,
            data=data,
        )
    except Exception as e:
        return UKGDataResponse(
            success=False,
            employee_number=employee_number,
            company_id=company_id,
            data={},
            error=str(e),
        )


@app.get(
    "/ukg/employee-employment-details/{employee_number}",
    response_model=UKGDataResponse,
    tags=["UKG Raw Data"],
)
async def get_ukg_employee_employment_details(
    employee_number: str,
    company_id: str = Query(default="J9A6Y", description="UKG company ID"),
):
    """Get raw employee employment details from UKG (includes project info)."""
    try:
        client = get_ukg_client()
        data = client.get_employee_employment_details(employee_number, company_id)
        return UKGDataResponse(
            success=bool(data),
            employee_number=employee_number,
            company_id=company_id,
            data=data,
        )
    except Exception as e:
        return UKGDataResponse(
            success=False,
            employee_number=employee_number,
            company_id=company_id,
            data={},
            error=str(e),
        )


@app.get(
    "/ukg/person-details/{employee_id}",
    response_model=UKGDataResponse,
    tags=["UKG Raw Data"],
)
async def get_ukg_person_details(employee_id: str):
    """Get raw person details from UKG (name, address, contact)."""
    try:
        client = get_ukg_client()
        data = client.get_person_details(employee_id)
        return UKGDataResponse(
            success=bool(data),
            employee_number=employee_id,
            company_id="",
            data=data,
        )
    except Exception as e:
        return UKGDataResponse(
            success=False,
            employee_number=employee_id,
            company_id="",
            data={},
            error=str(e),
        )


@app.get(
    "/ukg/supervisor-details/{employee_id}",
    response_model=UKGDataResponse,
    tags=["UKG Raw Data"],
)
async def get_ukg_supervisor_details(employee_id: str):
    """Get supervisor/manager details from UKG."""
    try:
        client = get_ukg_client()
        data = client.get_supervisor_details(employee_id)
        return UKGDataResponse(
            success=True,
            employee_number=employee_id,
            company_id="",
            data=data,
        )
    except Exception as e:
        return UKGDataResponse(
            success=False,
            employee_number=employee_id,
            company_id="",
            data={},
            error=str(e),
        )


# ============ Motus Raw Data Endpoints ============

@app.get(
    "/motus/driver/{employee_id}",
    response_model=MotusDriverResponse,
    tags=["Motus Raw Data"],
)
async def get_motus_driver(employee_id: str):
    """Get current driver data from Motus."""
    try:
        client = get_motus_client()
        driver = client.get_driver(employee_id)
        return MotusDriverResponse(
            success=True,
            employee_id=employee_id,
            exists=driver is not None,
            driver=driver,
        )
    except Exception as e:
        return MotusDriverResponse(
            success=False,
            employee_id=employee_id,
            exists=False,
            error=str(e),
        )


# ============ Debug Operations ============

def _fetch_all_ukg_data(
    ukg_client: UKGClient,
    employee_number: str,
    company_id: str,
    logger: Optional[DebugLogger] = None,
) -> Dict[str, Any]:
    """Fetch all UKG data for an employee with detailed logging."""
    result = {
        "employment_details": {},
        "employee_employment_details": {},
        "person_details": {},
        "supervisor_details": {},
        "location": {},
    }

    # 1. Employment details
    if logger:
        logger.log_ukg_request(
            "/personnel/v1/employment-details",
            "GET",
            {"employeeNumber": employee_number, "companyID": company_id},
        )
    start = time.time()
    try:
        result["employment_details"] = ukg_client.get_employment_details(
            employee_number, company_id
        )
        if logger:
            logger.log_ukg_response(
                "/personnel/v1/employment-details",
                200,
                result["employment_details"],
                (time.time() - start) * 1000,
            )
    except Exception as e:
        if logger:
            logger.log_ukg_response(
                "/personnel/v1/employment-details",
                500,
                {},
                (time.time() - start) * 1000,
                str(e),
            )

    # 2. Employee employment details
    if logger:
        logger.log_ukg_request(
            "/personnel/v1/employee-employment-details",
            "GET",
            {"employeeNumber": employee_number, "companyID": company_id},
        )
    start = time.time()
    try:
        result["employee_employment_details"] = ukg_client.get_employee_employment_details(
            employee_number, company_id
        )
        if logger:
            logger.log_ukg_response(
                "/personnel/v1/employee-employment-details",
                200,
                result["employee_employment_details"],
                (time.time() - start) * 1000,
            )
    except Exception as e:
        if logger:
            logger.log_ukg_response(
                "/personnel/v1/employee-employment-details",
                500,
                {},
                (time.time() - start) * 1000,
                str(e),
            )

    # 3. Resolve employee ID
    employee_id = (
        result["employment_details"].get("employeeId")
        or result["employment_details"].get("employeeID")
        or result["employee_employment_details"].get("employeeId")
        or result["employee_employment_details"].get("employeeID")
    )

    if employee_id:
        # 4. Person details
        if logger:
            logger.log_ukg_request(
                "/personnel/v1/person-details",
                "GET",
                {"employeeId": employee_id},
            )
        start = time.time()
        try:
            result["person_details"] = ukg_client.get_person_details(employee_id)
            if logger:
                logger.log_ukg_response(
                    "/personnel/v1/person-details",
                    200,
                    result["person_details"],
                    (time.time() - start) * 1000,
                )
        except Exception as e:
            if logger:
                logger.log_ukg_response(
                    "/personnel/v1/person-details",
                    500,
                    {},
                    (time.time() - start) * 1000,
                    str(e),
                )

        # 5. Supervisor details
        if logger:
            logger.log_ukg_request(
                "/personnel/v1/supervisor-details",
                "GET",
                {"employeeId": employee_id},
            )
        start = time.time()
        try:
            result["supervisor_details"] = ukg_client.get_supervisor_details(employee_id)
            if logger:
                logger.log_ukg_response(
                    "/personnel/v1/supervisor-details",
                    200,
                    result["supervisor_details"],
                    (time.time() - start) * 1000,
                )
        except Exception as e:
            if logger:
                logger.log_ukg_response(
                    "/personnel/v1/supervisor-details",
                    500,
                    {},
                    (time.time() - start) * 1000,
                    str(e),
                )

    # 6. Location details (same as batch runner)
    loc_code = result["employment_details"].get("primaryWorkLocationCode")
    if loc_code:
        if logger:
            logger.log_ukg_request(
                f"/configuration/v1/locations/{loc_code}",
                "GET",
                {"locationCode": loc_code},
            )
        start = time.time()
        try:
            result["location"] = ukg_client.get_location(loc_code)
            if logger:
                logger.log_ukg_response(
                    f"/configuration/v1/locations/{loc_code}",
                    200,
                    result["location"],
                    (time.time() - start) * 1000,
                )
        except Exception as e:
            if logger:
                logger.log_ukg_response(
                    f"/configuration/v1/locations/{loc_code}",
                    500,
                    {},
                    (time.time() - start) * 1000,
                    str(e),
                )

    return result


def _build_driver_from_ukg(
    ukg_data: Dict[str, Any],
    employee_number: str,
    logger: Optional[DebugLogger] = None,
) -> tuple[Optional[MotusDriver], TransformationInfo, List[str]]:
    """Build a MotusDriver from UKG data with transformation logging."""
    errors: List[str] = []

    employment_details = ukg_data.get("employment_details", {})
    employee_employment = ukg_data.get("employee_employment_details", {})
    person = ukg_data.get("person_details", {})
    supervisor = ukg_data.get("supervisor_details", {})

    # Derive status
    status_input = {
        "employeeStatusCode": employment_details.get("employeeStatusCode"),
        "dateOfTermination": employment_details.get("dateOfTermination"),
        "employeeStatusStartDate": employment_details.get("employeeStatusStartDate"),
        "employeeStatusExpectedEndDate": employment_details.get("employeeStatusExpectedEndDate"),
    }
    derived_status = determine_employment_status_from_dict(employment_details)

    if logger:
        logger.log_transformation(
            step="Derive Employment Status",
            input_data=status_input,
            output_data={"derived_status": derived_status.value},
            transformation_type="status_determination",
            details=f"Status code '{status_input.get('employeeStatusCode')}' + dates -> {derived_status.value}",
        )

    # Resolve program ID
    job_code = employment_details.get("primaryJobCode")
    program_id = resolve_program_id_from_job_code(job_code)

    # Get program type name
    program_type = None
    if program_id:
        for pt in ProgramType:
            if pt.value == program_id:
                program_type = pt.name
                break

    if logger:
        logger.log_transformation(
            step="Resolve Program ID",
            input_data={"primaryJobCode": job_code},
            output_data={"program_id": program_id, "program_type": program_type},
            transformation_type="program_mapping",
            details=f"Job code '{job_code}' -> Program ID {program_id} ({program_type})",
        )

    transformation_info = TransformationInfo(
        derived_status=derived_status.value,
        program_id=program_id,
        program_type=program_type,
        job_code=str(job_code) if job_code else None,
    )

    if not program_id:
        errors.append(f"No program ID found for job code: {job_code}")
        return None, transformation_info, errors

    # Build supervisor name
    supervisor_name = ""
    if supervisor:
        sup_first = supervisor.get("supervisorFirstName", "") or ""
        sup_last = supervisor.get("supervisorLastName", "") or ""
        supervisor_name = f"{sup_first} {sup_last}".strip()

    if logger:
        logger.log_transformation(
            step="Build Supervisor Name",
            input_data={
                "supervisorFirstName": supervisor.get("supervisorFirstName"),
                "supervisorLastName": supervisor.get("supervisorLastName"),
            },
            output_data={"supervisor_name": supervisor_name},
            transformation_type="name_concatenation",
        )

    # Get location (now fetched in _fetch_all_ukg_data, same as batch runner)
    location = ukg_data.get("location", {})

    # Get project info
    project_code = employee_employment.get("primaryProjectCode") or ""
    project_label = employee_employment.get("primaryProjectDescription") or ""

    # Log date transformations
    if logger:
        date_input = {
            "originalHireDate": employment_details.get("originalHireDate"),
            "dateOfTermination": employment_details.get("dateOfTermination"),
            "employeeStatusStartDate": employment_details.get("employeeStatusStartDate"),
            "employeeStatusExpectedEndDate": employment_details.get("employeeStatusExpectedEndDate"),
        }
        logger.log_transformation(
            step="Map Dates",
            input_data=date_input,
            output_data={
                "start_date": date_input.get("originalHireDate"),
                "end_date": date_input.get("dateOfTermination"),
                "leave_start_date": date_input.get("employeeStatusStartDate"),
                "leave_end_date": date_input.get("employeeStatusExpectedEndDate"),
            },
            transformation_type="date_mapping",
            details="UKG date fields -> Motus date fields (ISO format)",
        )

    # Log address transformation
    if logger:
        address_input = {
            "addressLine1": person.get("addressLine1"),
            "addressLine2": person.get("addressLine2"),
            "addressCity": person.get("addressCity"),
            "addressState": person.get("addressState"),
            "addressZipCode": person.get("addressZipCode"),
            "addressCountry": person.get("addressCountry"),
        }
        logger.log_transformation(
            step="Map Address",
            input_data=address_input,
            output_data={
                "address1": person.get("addressLine1"),
                "address2": person.get("addressLine2"),
                "city": person.get("addressCity"),
                "stateProvince": person.get("addressState"),
                "postalCode": person.get("addressZipCode"),
                "country": person.get("addressCountry"),
            },
            transformation_type="address_mapping",
        )

    try:
        driver = MotusDriver.from_ukg_data(
            employee_number=employee_number,
            program_id=program_id,
            person=person,
            employment_details=employment_details,
            supervisor_name=supervisor_name,
            location=location,
            project_code=project_code,
            project_label=project_label,
            derived_status=derived_status.value,
        )

        # Validate driver
        validation_errors = driver.validate()
        errors.extend(validation_errors)

        if logger:
            logger.log_transformation(
                step="Build Final Payload",
                input_data={"source": "all_ukg_data"},
                output_data=driver.to_api_payload(),
                transformation_type="payload_construction",
                details=f"Validation errors: {validation_errors}" if validation_errors else "Payload valid",
            )

        return driver, transformation_info, errors

    except Exception as e:
        errors.append(f"Failed to build driver: {str(e)}")
        return None, transformation_info, errors


@app.post(
    "/build-driver",
    response_model=BuildDriverResponseWithTrace,
    tags=["Debug Operations"],
)
async def build_driver(
    request: BuildDriverRequest,
    include_trace: bool = Query(default=True, description="Include detailed trace in response"),
):
    """
    Build a Motus driver payload from UKG data without syncing.

    This endpoint fetches all UKG data, applies transformations,
    and returns the final Motus payload for inspection.

    Includes detailed trace of:
    - All UKG API calls and responses
    - Data transformations applied
    - Final payload construction
    """
    logger = DebugLogger(request.employee_number, request.company_id, "build-driver")

    try:
        ukg_client = get_ukg_client()

        # Fetch all UKG data with logging
        ukg_data = _fetch_all_ukg_data(
            ukg_client, request.employee_number, request.company_id, logger
        )

        # Build driver with transformation logging
        driver, transformation_info, errors = _build_driver_from_ukg(
            ukg_data, request.employee_number, logger
        )

        result = {
            "success": driver is not None and len(errors) == 0,
            "payload": driver.to_api_payload() if driver else None,
        }
        trace = logger.finalize(result)

        return BuildDriverResponseWithTrace(
            success=driver is not None and len(errors) == 0,
            employee_number=request.employee_number,
            company_id=request.company_id,
            ukg_data=ukg_data,
            transformations=transformation_info,
            motus_payload=driver.to_api_payload() if driver else None,
            validation_errors=errors,
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )

    except Exception as e:
        trace = logger.finalize(error=str(e))
        return BuildDriverResponseWithTrace(
            success=False,
            employee_number=request.employee_number,
            company_id=request.company_id,
            error=str(e),
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )


def _compare_payloads(
    ukg_payload: Dict[str, Any],
    motus_current: Dict[str, Any],
) -> List[FieldDifference]:
    """Compare UKG-built payload with current Motus data."""
    differences: List[FieldDifference] = []

    # Fields to compare
    compare_fields = [
        "firstName",
        "lastName",
        "email",
        "address1",
        "address2",
        "city",
        "stateProvince",
        "postalCode",
        "phone",
        "alternatePhone",
        "endDate",
        "leaveStartDate",
        "leaveEndDate",
    ]

    for field in compare_fields:
        ukg_value = ukg_payload.get(field)
        motus_value = motus_current.get(field)

        # Normalize empty strings and None
        if ukg_value == "":
            ukg_value = None
        if motus_value == "":
            motus_value = None

        if ukg_value != motus_value:
            differences.append(
                FieldDifference(
                    field=field,
                    ukg_value=ukg_value,
                    motus_value=motus_value,
                    action_needed="UPDATE" if ukg_value else "CLEAR",
                )
            )

    # Compare custom variables
    ukg_cv = {cv["name"]: cv["value"] for cv in ukg_payload.get("customVariables", [])}
    motus_cv = {
        cv.get("name", ""): cv.get("value", "")
        for cv in motus_current.get("customVariables", [])
    }

    for name, ukg_value in ukg_cv.items():
        motus_value = motus_cv.get(name)
        if ukg_value != motus_value:
            differences.append(
                FieldDifference(
                    field=f"customVariables.{name}",
                    ukg_value=ukg_value,
                    motus_value=motus_value,
                    action_needed="UPDATE",
                )
            )

    return differences


@app.post(
    "/compare",
    response_model=CompareResponseWithTrace,
    tags=["Debug Operations"],
)
async def compare_employee(
    request: CompareRequest,
    include_trace: bool = Query(default=True, description="Include detailed trace in response"),
):
    """
    Compare UKG data with current Motus state.

    This endpoint builds the expected Motus payload from UKG,
    fetches the current Motus driver, and shows differences.

    Includes detailed trace of all API calls and transformations.
    """
    logger = DebugLogger(request.employee_number, request.company_id, "compare")

    try:
        ukg_client = get_ukg_client()
        motus_client = get_motus_client()

        # Fetch UKG data and build payload
        ukg_data = _fetch_all_ukg_data(
            ukg_client, request.employee_number, request.company_id, logger
        )

        driver, _, _ = _build_driver_from_ukg(ukg_data, request.employee_number, logger)
        ukg_payload = driver.to_api_payload() if driver else None

        # Fetch current Motus data
        logger.log_motus_request(
            f"/drivers/{request.employee_number}",
            "GET",
        )
        start = time.time()
        motus_current = motus_client.get_driver(request.employee_number)
        logger.log_motus_response(
            f"/drivers/{request.employee_number}",
            200 if motus_current else 404,
            motus_current or {},
            (time.time() - start) * 1000,
        )

        # Compare
        differences: List[FieldDifference] = []
        if ukg_payload and motus_current:
            differences = _compare_payloads(ukg_payload, motus_current)

        if logger and differences:
            logger.log_transformation(
                step="Compare Payloads",
                input_data={"ukg_fields": len(ukg_payload or {}), "motus_fields": len(motus_current or {})},
                output_data={"differences_count": len(differences)},
                transformation_type="comparison",
                details=f"Found {len(differences)} field differences",
            )

        result = {
            "exists_in_motus": motus_current is not None,
            "differences_count": len(differences),
        }
        trace = logger.finalize(result)

        return CompareResponseWithTrace(
            employee_number=request.employee_number,
            company_id=request.company_id,
            exists_in_motus=motus_current is not None,
            ukg_built_payload=ukg_payload,
            motus_current=motus_current,
            differences=differences,
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )

    except Exception as e:
        trace = logger.finalize(error=str(e))
        return CompareResponseWithTrace(
            employee_number=request.employee_number,
            company_id=request.company_id,
            exists_in_motus=False,
            error=str(e),
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )


# ============ Validation Scenarios ============

def _validate_new_hire(
    ukg_data: Dict[str, Any],
    motus_current: Optional[Dict[str, Any]],
    employee_number: str,
) -> tuple[List[ValidationCheck], str]:
    """Validate new hire scenario."""
    checks: List[ValidationCheck] = []
    recommendation = ""

    employment_details = ukg_data.get("employment_details", {})
    person = ukg_data.get("person_details", {})

    # Check 1: Job code eligibility
    job_code = employment_details.get("primaryJobCode")
    job_code_str = str(job_code).strip() if job_code else ""
    job_code_normalized = job_code_str.lstrip("0")
    is_eligible = job_code_str in JOBCODE_TO_PROGRAM or job_code_normalized in JOBCODE_TO_PROGRAM

    checks.append(
        ValidationCheck(
            check="Job code is eligible for Motus",
            status=CheckStatus.PASS if is_eligible else CheckStatus.FAIL,
            value=job_code_str,
            expected="One of: " + ", ".join(JOBCODE_TO_PROGRAM.keys()),
            message=f"Job code {job_code_str} {'is' if is_eligible else 'is NOT'} eligible",
        )
    )

    # Check 2: Required fields present
    required_fields = {
        "firstName": person.get("firstName"),
        "lastName": person.get("lastName"),
        "email": person.get("emailAddress"),
        "address1": person.get("addressLine1"),
        "city": person.get("addressCity"),
        "state": person.get("addressState"),
        "postalCode": person.get("addressZipCode"),
    }

    missing_fields = [k for k, v in required_fields.items() if not v]
    checks.append(
        ValidationCheck(
            check="Required fields present in UKG",
            status=CheckStatus.PASS if not missing_fields else CheckStatus.FAIL,
            value=str(required_fields) if missing_fields else "All present",
            message=f"Missing: {missing_fields}" if missing_fields else "All required fields present",
        )
    )

    # Check 3: Employee not already in Motus
    checks.append(
        ValidationCheck(
            check="Employee not already in Motus",
            status=CheckStatus.PASS if not motus_current else CheckStatus.WARN,
            value="Does not exist" if not motus_current else "Already exists",
            message="New profile will be created" if not motus_current else "Profile already exists - will be updated",
        )
    )

    # Check 4: Start date present
    start_date = employment_details.get("startDate")
    checks.append(
        ValidationCheck(
            check="Start date present",
            status=CheckStatus.PASS if start_date else CheckStatus.WARN,
            value=start_date or "Not set",
            message="Start date will default to today if not present",
        )
    )

    # Determine recommendation
    if not is_eligible:
        recommendation = f"Employee has ineligible job code ({job_code_str}). Cannot create in Motus."
    elif missing_fields:
        recommendation = f"Missing required fields: {missing_fields}. Update UKG data first."
    elif motus_current:
        recommendation = "Employee already exists in Motus. Sync will update existing profile."
    else:
        recommendation = "Employee is eligible for Motus. Run sync to create profile."

    return checks, recommendation


def _validate_termination(
    ukg_data: Dict[str, Any],
    motus_current: Optional[Dict[str, Any]],
    employee_number: str,
) -> tuple[List[ValidationCheck], str]:
    """Validate termination scenario."""
    checks: List[ValidationCheck] = []
    recommendation = ""

    employment_details = ukg_data.get("employment_details", {})

    # Check 1: Termination date in UKG
    termination_date = employment_details.get("dateOfTermination")
    checks.append(
        ValidationCheck(
            check="dateOfTermination in UKG",
            status=CheckStatus.PASS if termination_date else CheckStatus.FAIL,
            value=termination_date or "Not set",
        )
    )

    # Check 2: Status code indicates terminated
    status_code = employment_details.get("employeeStatusCode", "")
    terminated_codes = {"T", "TERM", "TERMINATED", "I", "INACTIVE"}
    is_termed_code = status_code.upper() in terminated_codes
    checks.append(
        ValidationCheck(
            check="employeeStatusCode indicates terminated",
            status=CheckStatus.PASS if is_termed_code else CheckStatus.WARN,
            value=status_code or "Not set",
            expected="T, TERM, or I",
        )
    )

    # Check 3: Derived status calculation
    derived_status = determine_employment_status_from_dict(employment_details)
    checks.append(
        ValidationCheck(
            check="Derived Status = Terminated",
            status=CheckStatus.PASS if derived_status.value == "Terminated" else CheckStatus.FAIL,
            value=derived_status.value,
            expected="Terminated",
        )
    )

    # Check 4: endDate in current Motus profile
    motus_end_date = motus_current.get("endDate") if motus_current else None
    checks.append(
        ValidationCheck(
            check="endDate in current Motus profile",
            status=CheckStatus.PASS if motus_end_date else CheckStatus.FAIL,
            value=motus_end_date or "Not set",
            expected=termination_date,
        )
    )

    # Check 5: Derived Status custom variable in Motus
    if motus_current:
        motus_cv = {
            cv.get("name"): cv.get("value")
            for cv in motus_current.get("customVariables", [])
        }
        motus_derived = motus_cv.get("Derived Status")
        checks.append(
            ValidationCheck(
                check="Derived Status custom variable in Motus",
                status=CheckStatus.PASS if motus_derived == "Terminated" else CheckStatus.FAIL,
                value=motus_derived or "Not set",
                expected="Terminated",
            )
        )

    # Determine recommendation
    if not termination_date:
        recommendation = "No termination date in UKG. Cannot terminate in Motus."
    elif not motus_current:
        recommendation = "Employee does not exist in Motus. No termination needed."
    elif motus_end_date == termination_date:
        recommendation = "Termination already synced to Motus. No action needed."
    else:
        recommendation = "Termination data exists in UKG but not reflected in Motus. Run sync to update."

    return checks, recommendation


def _validate_manager_change(
    ukg_data: Dict[str, Any],
    motus_current: Optional[Dict[str, Any]],
    employee_number: str,
) -> tuple[List[ValidationCheck], str]:
    """Validate manager change scenario."""
    checks: List[ValidationCheck] = []
    recommendation = ""

    supervisor = ukg_data.get("supervisor_details", {})

    # Check 1: Supervisor data in UKG
    sup_first = supervisor.get("supervisorFirstName", "") or ""
    sup_last = supervisor.get("supervisorLastName", "") or ""
    ukg_manager = f"{sup_first} {sup_last}".strip()

    checks.append(
        ValidationCheck(
            check="Supervisor details in UKG",
            status=CheckStatus.PASS if ukg_manager else CheckStatus.WARN,
            value=ukg_manager or "Not found",
        )
    )

    # Check 2: Manager Name in Motus
    motus_manager = None
    if motus_current:
        motus_cv = {
            cv.get("name"): cv.get("value")
            for cv in motus_current.get("customVariables", [])
        }
        motus_manager = motus_cv.get("Manager Name")

    checks.append(
        ValidationCheck(
            check="Manager Name in Motus",
            status=CheckStatus.PASS if motus_manager else CheckStatus.FAIL,
            value=motus_manager or "Not set",
        )
    )

    # Check 3: Manager names match
    names_match = ukg_manager == motus_manager
    checks.append(
        ValidationCheck(
            check="Manager names match (UKG vs Motus)",
            status=CheckStatus.PASS if names_match else CheckStatus.FAIL,
            value=f"UKG: '{ukg_manager}' vs Motus: '{motus_manager}'",
            expected=ukg_manager,
        )
    )

    # Determine recommendation
    if not motus_current:
        recommendation = "Employee does not exist in Motus. Create profile first."
    elif names_match:
        recommendation = "Manager name is already in sync. No action needed."
    else:
        recommendation = f"Manager name mismatch. UKG has '{ukg_manager}', Motus has '{motus_manager}'. Run sync to update."

    return checks, recommendation


def _validate_leave(
    ukg_data: Dict[str, Any],
    motus_current: Optional[Dict[str, Any]],
    employee_number: str,
) -> tuple[List[ValidationCheck], str]:
    """Validate leave of absence scenario."""
    checks: List[ValidationCheck] = []
    recommendation = ""

    employment_details = ukg_data.get("employment_details", {})

    # Check 1: Leave start date in UKG
    leave_start = employment_details.get("employeeStatusStartDate")
    checks.append(
        ValidationCheck(
            check="employeeStatusStartDate in UKG",
            status=CheckStatus.PASS if leave_start else CheckStatus.FAIL,
            value=leave_start or "Not set",
        )
    )

    # Check 2: Leave end date in UKG
    leave_end = employment_details.get("employeeStatusExpectedEndDate")
    checks.append(
        ValidationCheck(
            check="employeeStatusExpectedEndDate in UKG",
            status=CheckStatus.PASS if leave_end else CheckStatus.WARN,
            value=leave_end or "Not set (ongoing leave)",
        )
    )

    # Check 3: Derived status
    derived_status = determine_employment_status_from_dict(employment_details)
    is_leave = derived_status.value == "Leave"
    checks.append(
        ValidationCheck(
            check="Derived Status = Leave",
            status=CheckStatus.PASS if is_leave else CheckStatus.WARN,
            value=derived_status.value,
            expected="Leave" if leave_start and not leave_end else "Active (leave ended)",
        )
    )

    # Check 4: Leave dates in Motus
    if motus_current:
        motus_leave_start = motus_current.get("leaveStartDate")
        motus_leave_end = motus_current.get("leaveEndDate")

        checks.append(
            ValidationCheck(
                check="leaveStartDate in Motus",
                status=CheckStatus.PASS if motus_leave_start == leave_start else CheckStatus.FAIL,
                value=motus_leave_start or "Not set",
                expected=leave_start,
            )
        )

        checks.append(
            ValidationCheck(
                check="leaveEndDate in Motus",
                status=CheckStatus.PASS if motus_leave_end == leave_end else CheckStatus.FAIL,
                value=motus_leave_end or "Not set",
                expected=leave_end or "Not set",
            )
        )

    # Determine recommendation
    if not leave_start:
        recommendation = "No leave start date in UKG. Employee is not on leave."
    elif not motus_current:
        recommendation = "Employee does not exist in Motus. Create profile first."
    elif motus_current.get("leaveStartDate") == leave_start:
        recommendation = "Leave dates are already in sync. No action needed."
    else:
        recommendation = "Leave data exists in UKG but not synced to Motus. Run sync to update."

    return checks, recommendation


def _validate_address(
    ukg_data: Dict[str, Any],
    motus_current: Optional[Dict[str, Any]],
    employee_number: str,
) -> tuple[List[ValidationCheck], str]:
    """Validate address change scenario."""
    checks: List[ValidationCheck] = []
    recommendation = ""

    person = ukg_data.get("person_details", {})

    # Address fields mapping
    address_mapping = {
        "address1": ("addressLine1", "address1"),
        "city": ("addressCity", "city"),
        "stateProvince": ("addressState", "stateProvince"),
        "postalCode": ("addressZipCode", "postalCode"),
    }

    mismatches: List[str] = []

    for field_name, (ukg_key, motus_key) in address_mapping.items():
        ukg_value = person.get(ukg_key, "")
        motus_value = motus_current.get(motus_key, "") if motus_current else ""

        # Normalize
        ukg_value = (ukg_value or "").strip()
        motus_value = (motus_value or "").strip()

        matches = ukg_value == motus_value

        checks.append(
            ValidationCheck(
                check=f"{field_name} matches (UKG vs Motus)",
                status=CheckStatus.PASS if matches else CheckStatus.FAIL,
                value=f"UKG: '{ukg_value}' vs Motus: '{motus_value}'",
                expected=ukg_value,
            )
        )

        if not matches:
            mismatches.append(field_name)

    # Determine recommendation
    if not motus_current:
        recommendation = "Employee does not exist in Motus. Create profile first."
    elif not mismatches:
        recommendation = "Address is already in sync. No action needed."
    else:
        recommendation = f"Address fields differ: {mismatches}. Run sync to update."

    return checks, recommendation


@app.post(
    "/validate-scenario",
    response_model=ValidateScenarioResponseWithTrace,
    tags=["Validation Scenarios"],
)
async def validate_scenario(
    request: ValidateScenarioRequest,
    include_trace: bool = Query(default=True, description="Include detailed trace in response"),
):
    """
    Validate a specific synchronization scenario.

    Supported scenarios:
    - new_hire: Check if employee is eligible for Motus creation
    - termination: Check if termination is properly synced
    - manager_change: Check if manager name matches
    - leave: Check if leave dates are synced
    - address: Check if address fields match

    Includes detailed trace of all API calls.
    """
    logger = DebugLogger(
        request.employee_number,
        request.company_id,
        f"validate-{request.scenario.value}",
    )

    try:
        ukg_client = get_ukg_client()
        motus_client = get_motus_client()

        # Fetch UKG data
        ukg_data = _fetch_all_ukg_data(
            ukg_client, request.employee_number, request.company_id, logger
        )

        # Fetch Motus data
        logger.log_motus_request(
            f"/drivers/{request.employee_number}",
            "GET",
        )
        start = time.time()
        motus_current = motus_client.get_driver(request.employee_number)
        logger.log_motus_response(
            f"/drivers/{request.employee_number}",
            200 if motus_current else 404,
            motus_current or {},
            (time.time() - start) * 1000,
        )

        # Run scenario-specific validation
        checks: List[ValidationCheck] = []
        recommendation = ""

        if request.scenario == ValidationScenario.NEW_HIRE:
            checks, recommendation = _validate_new_hire(
                ukg_data, motus_current, request.employee_number
            )
        elif request.scenario == ValidationScenario.TERMINATION:
            checks, recommendation = _validate_termination(
                ukg_data, motus_current, request.employee_number
            )
        elif request.scenario == ValidationScenario.MANAGER_CHANGE:
            checks, recommendation = _validate_manager_change(
                ukg_data, motus_current, request.employee_number
            )
        elif request.scenario == ValidationScenario.LEAVE:
            checks, recommendation = _validate_leave(
                ukg_data, motus_current, request.employee_number
            )
        elif request.scenario == ValidationScenario.ADDRESS:
            checks, recommendation = _validate_address(
                ukg_data, motus_current, request.employee_number
            )

        # Determine overall status
        failed_checks = [c for c in checks if c.status == CheckStatus.FAIL]
        overall_status = OverallStatus.OK if not failed_checks else OverallStatus.ISSUE_DETECTED

        result = {
            "scenario": request.scenario.value,
            "overall_status": overall_status.value,
            "checks_passed": len([c for c in checks if c.status == CheckStatus.PASS]),
            "checks_failed": len(failed_checks),
        }
        trace = logger.finalize(result)

        return ValidateScenarioResponseWithTrace(
            scenario=request.scenario.value,
            employee_number=request.employee_number,
            company_id=request.company_id,
            checks=checks,
            overall_status=overall_status,
            recommendation=recommendation,
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )

    except Exception as e:
        trace = logger.finalize(error=str(e))
        return ValidateScenarioResponseWithTrace(
            scenario=request.scenario.value,
            employee_number=request.employee_number,
            company_id=request.company_id,
            overall_status=OverallStatus.ERROR,
            error=str(e),
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )


# ============ Sync Endpoint ============

@app.post(
    "/sync",
    response_model=SyncResponseWithTrace,
    tags=["Debug Operations"],
)
async def sync_employee(
    request: SyncRequest,
    include_trace: bool = Query(default=True, description="Include detailed trace in response"),
):
    """
    Sync an employee from UKG to Motus.

    Use dry_run=true to validate without making changes.

    This endpoint uses the same DriverBuilderService and flow as the batch runner
    to ensure consistent behavior between API and batch operations.

    Includes detailed trace of:
    - All UKG API calls and responses
    - Data transformations applied
    - Motus API request and response
    """
    logger = DebugLogger(
        request.employee_number,
        request.company_id,
        f"sync{'_dry_run' if request.dry_run else ''}",
    )

    try:
        ukg_client = get_ukg_client()
        motus_client = get_motus_client()
        debug = os.getenv("DEBUG", "0") == "1"

        # === STEP 1: Check if already terminated in MOTUS (same as batch runner) ===
        logger.log_motus_request(
            f"/drivers/{request.employee_number}",
            "GET",
        )
        start = time.time()
        is_terminated, existing_driver = motus_client.is_driver_terminated(
            request.employee_number
        )
        logger.log_motus_response(
            f"/drivers/{request.employee_number}",
            200 if existing_driver else 404,
            existing_driver or {},
            (time.time() - start) * 1000,
        )

        if is_terminated:
            motus_end_date = existing_driver.get("endDate", "") if existing_driver else ""
            result = {
                "success": True,
                "action": "skipped_terminated",
                "reason": f"Already terminated in MOTUS (endDate: {motus_end_date})",
            }
            trace = logger.finalize(result)
            return SyncResponseWithTrace(
                success=True,
                employee_number=request.employee_number,
                company_id=request.company_id,
                action="skipped_terminated",
                dry_run=request.dry_run,
                motus_response=result,
                trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
            )

        # === STEP 2: Build driver using DriverBuilderService (same as batch runner) ===
        driver_builder = DriverBuilderService(ukg_client, debug=debug)

        # Also fetch UKG data for trace logging
        ukg_data = _fetch_all_ukg_data(
            ukg_client, request.employee_number, request.company_id, logger
        )

        try:
            driver = driver_builder.build_driver(request.employee_number, request.company_id)
        except (EmployeeNotFoundError, ProgramNotFoundError) as e:
            trace = logger.finalize(error=str(e))
            return SyncResponseWithTrace(
                success=False,
                employee_number=request.employee_number,
                company_id=request.company_id,
                action="skipped",
                dry_run=request.dry_run,
                error=str(e),
                trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
            )

        # Validate driver
        validation_errors = driver.validate()
        if validation_errors:
            trace = logger.finalize(error=f"Validation errors: {validation_errors}")
            return SyncResponseWithTrace(
                success=False,
                employee_number=request.employee_number,
                company_id=request.company_id,
                action="validation_error",
                dry_run=request.dry_run,
                error=f"Validation errors: {validation_errors}",
                trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
            )

        # Log payload
        payload = driver.to_api_payload()
        driver_exists = existing_driver is not None

        # === STEP 3: Dry run or actual sync ===
        if request.dry_run:
            action = "would_update" if driver_exists else "would_insert"
            result = {"dry_run": True, "action": action, "id": request.employee_number}
        else:
            # === STEP 4: POST or PUT based on existence (same as batch runner) ===
            if driver_exists:
                logger.log_motus_request(
                    f"/drivers/{request.employee_number}",
                    "PUT",
                    payload,
                )
                start = time.time()
                motus_result = motus_client.update_driver(driver)
                action = "update"
            else:
                logger.log_motus_request(
                    "/drivers",
                    "POST",
                    payload,
                )
                start = time.time()
                motus_result = motus_client.create_driver(driver)
                action = "insert"

            logger.log_motus_response(
                f"/drivers/{request.employee_number}" if driver_exists else "/drivers",
                200,
                motus_result,
                (time.time() - start) * 1000,
            )

            result = {
                "success": True,
                "action": action,
                "id": request.employee_number,
                "name": f"{driver.first_name} {driver.last_name}",
                "program_id": driver.program_id,
                "data": motus_result,
            }

        trace = logger.finalize(result)

        return SyncResponseWithTrace(
            success=result.get("success", True),
            employee_number=request.employee_number,
            company_id=request.company_id,
            action=result.get("action", "unknown"),
            dry_run=request.dry_run,
            motus_response=result,
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )

    except Exception as e:
        trace = logger.finalize(error=str(e))
        return SyncResponseWithTrace(
            success=False,
            employee_number=request.employee_number,
            company_id=request.company_id,
            action="error",
            dry_run=request.dry_run,
            error=str(e),
            trace=RequestTraceModel(**trace.to_dict()) if include_trace else None,
        )
