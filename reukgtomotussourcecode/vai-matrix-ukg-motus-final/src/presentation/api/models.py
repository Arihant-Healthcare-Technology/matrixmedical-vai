"""
Pydantic models for Debug API requests and responses.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ Enums ============

class ValidationScenario(str, Enum):
    """Supported validation scenarios."""

    NEW_HIRE = "new_hire"
    TERMINATION = "termination"
    MANAGER_CHANGE = "manager_change"
    LEAVE = "leave"
    ADDRESS = "address"


class CheckStatus(str, Enum):
    """Status of a validation check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class OverallStatus(str, Enum):
    """Overall validation status."""

    OK = "OK"
    ISSUE_DETECTED = "ISSUE_DETECTED"
    ERROR = "ERROR"


# ============ Request Models ============

class BuildDriverRequest(BaseModel):
    """Request to build a Motus driver payload from UKG data."""

    employee_number: str = Field(..., description="UKG employee number")
    company_id: str = Field(default="J9A6Y", description="UKG company ID")


class CompareRequest(BaseModel):
    """Request to compare UKG data with Motus current state."""

    employee_number: str = Field(..., description="UKG employee number")
    company_id: str = Field(default="J9A6Y", description="UKG company ID")


class ValidateScenarioRequest(BaseModel):
    """Request to validate a specific scenario."""

    employee_number: str = Field(..., description="UKG employee number")
    company_id: str = Field(default="J9A6Y", description="UKG company ID")
    scenario: ValidationScenario = Field(..., description="Scenario to validate")


class SyncRequest(BaseModel):
    """Request to sync an employee to Motus."""

    employee_number: str = Field(..., description="UKG employee number")
    company_id: str = Field(default="J9A6Y", description="UKG company ID")
    dry_run: bool = Field(default=True, description="If true, validate without making changes")


# ============ Response Models ============

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"
    service: str = "motus-debug-api"


class UKGDataResponse(BaseModel):
    """Raw UKG data response wrapper."""

    success: bool
    employee_number: str
    company_id: str
    data: Dict[str, Any]
    error: Optional[str] = None


class TransformationInfo(BaseModel):
    """Information about data transformations applied."""

    derived_status: str
    program_id: Optional[int] = None
    program_type: Optional[str] = None
    job_code: Optional[str] = None


class BuildDriverResponse(BaseModel):
    """Response from building a Motus driver payload."""

    success: bool
    employee_number: str
    company_id: str
    ukg_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw UKG data from all endpoints"
    )
    transformations: Optional[TransformationInfo] = None
    motus_payload: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class FieldDifference(BaseModel):
    """A single field difference between UKG and Motus."""

    field: str
    ukg_value: Optional[Any] = None
    motus_value: Optional[Any] = None
    action_needed: str = "UPDATE"


class CompareResponse(BaseModel):
    """Response from comparing UKG data with Motus."""

    employee_number: str
    company_id: str
    exists_in_motus: bool
    ukg_built_payload: Optional[Dict[str, Any]] = None
    motus_current: Optional[Dict[str, Any]] = None
    differences: List[FieldDifference] = Field(default_factory=list)
    error: Optional[str] = None


class ValidationCheck(BaseModel):
    """A single validation check result."""

    check: str
    status: CheckStatus
    value: Optional[Any] = None
    expected: Optional[Any] = None
    message: Optional[str] = None


class ValidateScenarioResponse(BaseModel):
    """Response from scenario validation."""

    scenario: str
    employee_number: str
    company_id: str
    checks: List[ValidationCheck] = Field(default_factory=list)
    overall_status: OverallStatus
    recommendation: Optional[str] = None
    error: Optional[str] = None


class SyncResponse(BaseModel):
    """Response from syncing an employee to Motus."""

    success: bool
    employee_number: str
    company_id: str
    action: str  # insert, update, skipped, error, dry_run
    dry_run: bool
    motus_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MotusDriverResponse(BaseModel):
    """Response containing Motus driver data."""

    success: bool
    employee_id: str
    exists: bool
    driver: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============ Trace Models ============

class APICallLogModel(BaseModel):
    """API call log entry."""

    timestamp: str
    direction: str
    system: str
    endpoint: str
    method: str
    status_code: Optional[int] = None
    request_params: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class TransformationLogModel(BaseModel):
    """Transformation log entry."""

    timestamp: str
    step: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    transformation_type: str
    details: Optional[str] = None


class RequestTraceModel(BaseModel):
    """Complete request trace."""

    trace_id: str
    employee_number: str
    company_id: str
    operation: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    ukg_calls: List[APICallLogModel] = Field(default_factory=list)
    transformations: List[TransformationLogModel] = Field(default_factory=list)
    motus_calls: List[APICallLogModel] = Field(default_factory=list)
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============ Enhanced Response Models with Trace ============

class BuildDriverResponseWithTrace(BuildDriverResponse):
    """Build driver response with full trace."""

    trace: Optional[RequestTraceModel] = None


class CompareResponseWithTrace(CompareResponse):
    """Compare response with full trace."""

    trace: Optional[RequestTraceModel] = None


class SyncResponseWithTrace(SyncResponse):
    """Sync response with full trace."""

    trace: Optional[RequestTraceModel] = None


class ValidateScenarioResponseWithTrace(ValidateScenarioResponse):
    """Validate scenario response with full trace."""

    trace: Optional[RequestTraceModel] = None
