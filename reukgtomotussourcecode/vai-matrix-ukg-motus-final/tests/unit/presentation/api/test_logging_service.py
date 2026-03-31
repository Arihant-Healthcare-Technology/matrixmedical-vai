"""
Tests for Debug API logging service.

Tests the DebugLogger class and related data structures.
"""

import pytest
from datetime import datetime, timezone

from src.presentation.api.logging_service import (
    DebugLogger,
    APICallLog,
    TransformationLog,
    RequestTrace,
)


class TestAPICallLog:
    """Tests for APICallLog dataclass."""

    def test_to_dict(self):
        """Test APICallLog to_dict conversion."""
        log = APICallLog(
            timestamp="2024-01-15T10:00:00Z",
            direction="request",
            system="UKG",
            endpoint="/personnel/v1/employment-details",
            method="GET",
            status_code=200,
            request_params={"employeeNumber": "12345"},
            response_body={"data": "test"},
            duration_ms=100.0,
            error=None,
        )

        result = log.to_dict()

        assert result["timestamp"] == "2024-01-15T10:00:00Z"
        assert result["direction"] == "request"
        assert result["system"] == "UKG"
        assert result["endpoint"] == "/personnel/v1/employment-details"
        assert result["method"] == "GET"
        assert result["status_code"] == 200
        assert result["duration_ms"] == 100.0


class TestTransformationLog:
    """Tests for TransformationLog dataclass."""

    def test_to_dict(self):
        """Test TransformationLog to_dict conversion."""
        log = TransformationLog(
            timestamp="2024-01-15T10:00:00Z",
            step="Map Dates",
            input_data={"originalHireDate": "2024-01-15"},
            output_data={"start_date": "2024-01-15"},
            transformation_type="date_mapping",
            details="UKG to Motus date format",
        )

        result = log.to_dict()

        assert result["step"] == "Map Dates"
        assert result["transformation_type"] == "date_mapping"
        assert result["input_data"]["originalHireDate"] == "2024-01-15"
        assert result["output_data"]["start_date"] == "2024-01-15"
        assert result["details"] == "UKG to Motus date format"


class TestRequestTrace:
    """Tests for RequestTrace dataclass."""

    def test_to_dict(self):
        """Test RequestTrace to_dict conversion."""
        trace = RequestTrace(
            trace_id="abc123",
            employee_number="12345",
            company_id="J9A6Y",
            operation="build-driver",
            start_time="2024-01-15T10:00:00Z",
        )

        result = trace.to_dict()

        assert result["trace_id"] == "abc123"
        assert result["employee_number"] == "12345"
        assert result["company_id"] == "J9A6Y"
        assert result["operation"] == "build-driver"


class TestDebugLogger:
    """Tests for DebugLogger class."""

    def test_init_creates_trace(self):
        """Test logger initialization creates a trace."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        assert logger.trace.employee_number == "12345"
        assert logger.trace.company_id == "J9A6Y"
        assert logger.trace.operation == "build-driver"
        assert logger.trace.trace_id is not None
        assert len(logger.trace.trace_id) == 8

    def test_log_ukg_request(self):
        """Test logging a UKG request."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")
        logger.log_ukg_request(
            "/personnel/v1/employment-details",
            "GET",
            {"employeeNumber": "12345"},
        )

        assert len(logger.trace.ukg_calls) == 1
        assert logger.trace.ukg_calls[0].endpoint == "/personnel/v1/employment-details"
        assert logger.trace.ukg_calls[0].method == "GET"
        assert logger.trace.ukg_calls[0].request_params == {"employeeNumber": "12345"}

    def test_log_ukg_response_finds_matching_request(self):
        """Test log_ukg_response correctly matches and updates request."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        # Log a request first
        logger.log_ukg_request(
            "/personnel/v1/employment-details",
            "GET",
            {"employeeNumber": "12345"},
        )

        # Then log matching response
        logger.log_ukg_response(
            "/personnel/v1/employment-details",
            200,
            {"employeeNumber": "12345", "companyID": "J9A6Y"},
            100.0,
        )

        # Verify request was updated with response
        assert logger.trace.ukg_calls[0].status_code == 200
        assert logger.trace.ukg_calls[0].response_body == {
            "employeeNumber": "12345",
            "companyID": "J9A6Y",
        }
        assert logger.trace.ukg_calls[0].duration_ms == 100.0
        assert logger.trace.ukg_calls[0].direction == "complete"

    def test_log_ukg_response_with_error(self):
        """Test logging UKG response with error."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        logger.log_ukg_request("/personnel/v1/employment-details", "GET", {})
        logger.log_ukg_response(
            "/personnel/v1/employment-details",
            500,
            {},
            50.0,
            error="Internal server error",
        )

        assert logger.trace.ukg_calls[0].error == "Internal server error"
        assert logger.trace.ukg_calls[0].status_code == 500

    def test_log_transformation(self):
        """Test logging a transformation step."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        logger.log_transformation(
            step="Map Dates",
            input_data={"originalHireDate": "2024-01-15T00:00:00Z"},
            output_data={"start_date": "2024-01-15"},
            transformation_type="date_mapping",
            details="ISO to YYYY-MM-DD",
        )

        assert len(logger.trace.transformations) == 1
        assert logger.trace.transformations[0].step == "Map Dates"
        assert logger.trace.transformations[0].transformation_type == "date_mapping"
        assert logger.trace.transformations[0].details == "ISO to YYYY-MM-DD"

    def test_log_motus_request(self):
        """Test logging a Motus request."""
        logger = DebugLogger("12345", "J9A6Y", "sync")

        logger.log_motus_request(
            "/drivers",
            "POST",
            {"clientEmployeeId1": "12345", "firstName": "John"},
        )

        assert len(logger.trace.motus_calls) == 1
        assert logger.trace.motus_calls[0].endpoint == "/drivers"
        assert logger.trace.motus_calls[0].method == "POST"
        assert logger.trace.motus_calls[0].request_body["clientEmployeeId1"] == "12345"

    def test_log_motus_response_finds_matching_request(self):
        """Test log_motus_response correctly matches and updates request."""
        logger = DebugLogger("12345", "J9A6Y", "sync")

        # Log request first
        logger.log_motus_request("/drivers", "POST", {"clientEmployeeId1": "12345"})

        # Log matching response
        logger.log_motus_response(
            "/drivers",
            201,
            {"id": "driver-123", "status": "created"},
            150.0,
        )

        # Verify request was updated
        assert logger.trace.motus_calls[0].status_code == 201
        assert logger.trace.motus_calls[0].response_body["status"] == "created"
        assert logger.trace.motus_calls[0].duration_ms == 150.0
        assert logger.trace.motus_calls[0].direction == "complete"

    def test_log_motus_response_with_error(self):
        """Test logging Motus response with error."""
        logger = DebugLogger("12345", "J9A6Y", "sync")

        logger.log_motus_request("/drivers", "POST", {})
        logger.log_motus_response(
            "/drivers",
            400,
            {"error": "Bad request"},
            50.0,
            error="Validation failed",
        )

        assert logger.trace.motus_calls[0].error == "Validation failed"
        assert logger.trace.motus_calls[0].status_code == 400

    def test_finalize_sets_end_time_and_duration(self):
        """Test finalize sets end time and calculates duration."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        logger.finalize({"success": True})

        assert logger.trace.end_time is not None
        assert logger.trace.duration_ms is not None
        assert logger.trace.final_result == {"success": True}

    def test_finalize_with_error(self):
        """Test finalize with error."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")

        logger.finalize({"success": False}, error="Employee not found")

        assert logger.trace.error == "Employee not found"

    def test_get_trace(self):
        """Test getting trace object."""
        logger = DebugLogger("12345", "J9A6Y", "build-driver")
        logger.log_ukg_request("/test", "GET", {})
        logger.finalize({"success": True})

        trace = logger.get_trace()

        assert isinstance(trace, RequestTrace)
        assert trace.employee_number == "12345"
        assert trace.operation == "build-driver"
        assert len(trace.ukg_calls) == 1

        # Test to_dict conversion
        trace_dict = trace.to_dict()
        assert isinstance(trace_dict, dict)
        assert trace_dict["employee_number"] == "12345"

    def test_complete_debug_logger_flow(self):
        """Test complete logger workflow with multiple operations."""
        logger = DebugLogger("28190", "J9A6Y", "sync")

        # Log UKG requests
        logger.log_ukg_request("/personnel/v1/employment-details", "GET", {"employeeNumber": "28190"})
        logger.log_ukg_response("/personnel/v1/employment-details", 200, {"employeeNumber": "28190"}, 100.0)

        logger.log_ukg_request("/personnel/v1/person-details", "GET", {"employeeId": "emp-001"})
        logger.log_ukg_response("/personnel/v1/person-details", 200, {"firstName": "John"}, 80.0)

        # Log transformations
        logger.log_transformation(
            "Build Driver Payload",
            {"employeeNumber": "28190", "firstName": "John"},
            {"clientEmployeeId1": "28190", "firstName": "John"},
            "payload_building",
        )

        # Log Motus request
        logger.log_motus_request("/drivers", "POST", {"clientEmployeeId1": "28190"})
        logger.log_motus_response("/drivers", 201, {"id": "123"}, 200.0)

        # Finalize
        logger.finalize({"success": True, "action": "inserted"})

        # Verify complete trace
        trace = logger.get_trace()
        assert len(trace.ukg_calls) == 2
        assert len(trace.transformations) == 1
        assert len(trace.motus_calls) == 1
        assert trace.final_result["success"] is True
