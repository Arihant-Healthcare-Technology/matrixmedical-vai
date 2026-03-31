"""
Logging service for Debug API.

Captures detailed logs at each stage of data flow:
1. UKG API requests and responses
2. Data transformations
3. Motus API requests and responses
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("motus-debug-api")


@dataclass
class APICallLog:
    """Log entry for an API call."""

    timestamp: str
    direction: str  # "request" or "response"
    system: str  # "UKG" or "MOTUS"
    endpoint: str
    method: str
    status_code: Optional[int] = None
    request_params: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "system": self.system,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "request_params": self.request_params,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class TransformationLog:
    """Log entry for a data transformation."""

    timestamp: str
    step: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    transformation_type: str
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "step": self.step,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "transformation_type": self.transformation_type,
            "details": self.details,
        }


@dataclass
class RequestTrace:
    """Complete trace of a debug API request."""

    trace_id: str
    employee_number: str
    company_id: str
    operation: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    ukg_calls: List[APICallLog] = field(default_factory=list)
    transformations: List[TransformationLog] = field(default_factory=list)
    motus_calls: List[APICallLog] = field(default_factory=list)
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "employee_number": self.employee_number,
            "company_id": self.company_id,
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "ukg_calls": [c.to_dict() for c in self.ukg_calls],
            "transformations": [t.to_dict() for t in self.transformations],
            "motus_calls": [c.to_dict() for c in self.motus_calls],
            "final_result": self.final_result,
            "error": self.error,
        }


class DebugLogger:
    """
    Logger for Debug API operations.

    Captures detailed information at each stage of the data flow.
    """

    def __init__(self, employee_number: str, company_id: str, operation: str):
        """Initialize logger for a specific operation."""
        self.trace = RequestTrace(
            trace_id=str(uuid.uuid4())[:8],
            employee_number=employee_number,
            company_id=company_id,
            operation=operation,
            start_time=self._now(),
        )
        self._log_start()

    @staticmethod
    def _now() -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _log_start(self) -> None:
        """Log operation start."""
        logger.info(
            f"[{self.trace.trace_id}] START {self.trace.operation} | "
            f"employee={self.trace.employee_number} company={self.trace.company_id}"
        )

    def log_ukg_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a UKG API request."""
        log_entry = APICallLog(
            timestamp=self._now(),
            direction="request",
            system="UKG",
            endpoint=endpoint,
            method=method,
            request_params=params,
        )
        self.trace.ukg_calls.append(log_entry)
        logger.debug(
            f"[{self.trace.trace_id}] UKG REQUEST | {method} {endpoint} | params={json.dumps(params) if params else '{}'}"
        )

    def log_ukg_response(
        self,
        endpoint: str,
        status_code: int,
        response_data: Dict[str, Any],
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a UKG API response."""
        # Update the last request with response info
        for call in reversed(self.trace.ukg_calls):
            if call.endpoint == endpoint and call.direction == "request":
                call.status_code = status_code
                call.response_body = response_data
                call.duration_ms = duration_ms
                call.error = error
                call.direction = "complete"
                break

        # Log key fields from response
        key_fields = self._extract_key_fields(response_data, "UKG")
        logger.info(
            f"[{self.trace.trace_id}] UKG RESPONSE | {endpoint} | "
            f"status={status_code} | duration={duration_ms:.0f}ms | "
            f"key_fields={json.dumps(key_fields)}"
        )

        if error:
            logger.error(f"[{self.trace.trace_id}] UKG ERROR | {endpoint} | {error}")

    def log_transformation(
        self,
        step: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        transformation_type: str,
        details: Optional[str] = None,
    ) -> None:
        """Log a data transformation step."""
        log_entry = TransformationLog(
            timestamp=self._now(),
            step=step,
            input_data=input_data,
            output_data=output_data,
            transformation_type=transformation_type,
            details=details,
        )
        self.trace.transformations.append(log_entry)

        # Log summary
        logger.info(
            f"[{self.trace.trace_id}] TRANSFORM | {step} | "
            f"type={transformation_type} | "
            f"input_keys={list(input_data.keys())} | "
            f"output_keys={list(output_data.keys())}"
        )
        if details:
            logger.debug(f"[{self.trace.trace_id}] TRANSFORM DETAIL | {step} | {details}")

    def log_motus_request(
        self,
        endpoint: str,
        method: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a Motus API request."""
        log_entry = APICallLog(
            timestamp=self._now(),
            direction="request",
            system="MOTUS",
            endpoint=endpoint,
            method=method,
            request_body=body,
        )
        self.trace.motus_calls.append(log_entry)

        # Log key fields being sent
        key_fields = self._extract_key_fields(body, "MOTUS") if body else {}
        logger.info(
            f"[{self.trace.trace_id}] MOTUS REQUEST | {method} {endpoint} | "
            f"key_fields={json.dumps(key_fields)}"
        )
        logger.debug(
            f"[{self.trace.trace_id}] MOTUS REQUEST BODY | {json.dumps(body) if body else '{}'}"
        )

    def log_motus_response(
        self,
        endpoint: str,
        status_code: int,
        response_data: Dict[str, Any],
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a Motus API response."""
        # Update the last request with response info
        for call in reversed(self.trace.motus_calls):
            if call.endpoint == endpoint and call.direction == "request":
                call.status_code = status_code
                call.response_body = response_data
                call.duration_ms = duration_ms
                call.error = error
                call.direction = "complete"
                break

        logger.info(
            f"[{self.trace.trace_id}] MOTUS RESPONSE | {endpoint} | "
            f"status={status_code} | duration={duration_ms:.0f}ms"
        )
        logger.debug(
            f"[{self.trace.trace_id}] MOTUS RESPONSE BODY | {json.dumps(response_data)}"
        )

        if error:
            logger.error(f"[{self.trace.trace_id}] MOTUS ERROR | {endpoint} | {error}")

    def _extract_key_fields(
        self, data: Optional[Dict[str, Any]], system: str
    ) -> Dict[str, Any]:
        """Extract key fields from data for logging."""
        if not data:
            return {}

        key_fields: Dict[str, Any] = {}

        if system == "UKG":
            # UKG key fields
            ukg_keys = [
                "employeeNumber",
                "employeeId",
                "employeeID",
                "terminationDate",
                "leaveStartDate",
                "leaveEndDate",
                "employeeStatusCode",
                "startDate",
                "primaryJobCode",
                "firstName",
                "lastName",
                "emailAddress",
                "addressLine1",
                "addressCity",
                "addressState",
                "addressZipCode",
                "supervisorFirstName",
                "supervisorLastName",
                "primaryProjectCode",
                "primaryProjectDescription",
            ]
            for key in ukg_keys:
                if key in data and data[key]:
                    key_fields[key] = data[key]

        elif system == "MOTUS":
            # Motus key fields
            motus_keys = [
                "clientEmployeeId1",
                "programId",
                "firstName",
                "lastName",
                "email",
                "address1",
                "city",
                "stateProvince",
                "postalCode",
                "startDate",
                "endDate",
                "leaveStartDate",
                "leaveEndDate",
            ]
            for key in motus_keys:
                if key in data and data[key]:
                    key_fields[key] = data[key]

            # Extract key custom variables
            if "customVariables" in data:
                cv_keys = ["Derived Status", "Manager Name", "Termination Date"]
                for cv in data.get("customVariables", []):
                    if cv.get("name") in cv_keys:
                        key_fields[f"CV:{cv['name']}"] = cv.get("value")

        return key_fields

    def finalize(
        self,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> RequestTrace:
        """Finalize the trace and return it."""
        self.trace.end_time = self._now()

        # Calculate duration
        start = datetime.fromisoformat(self.trace.start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.trace.end_time.replace("Z", "+00:00"))
        self.trace.duration_ms = (end - start).total_seconds() * 1000

        self.trace.final_result = result
        self.trace.error = error

        # Log summary
        status = "SUCCESS" if not error else "FAILED"
        logger.info(
            f"[{self.trace.trace_id}] END {self.trace.operation} | "
            f"status={status} | duration={self.trace.duration_ms:.0f}ms | "
            f"ukg_calls={len(self.trace.ukg_calls)} | "
            f"transformations={len(self.trace.transformations)} | "
            f"motus_calls={len(self.trace.motus_calls)}"
        )

        if error:
            logger.error(f"[{self.trace.trace_id}] ERROR | {error}")

        return self.trace

    def get_trace(self) -> RequestTrace:
        """Get the current trace."""
        return self.trace
