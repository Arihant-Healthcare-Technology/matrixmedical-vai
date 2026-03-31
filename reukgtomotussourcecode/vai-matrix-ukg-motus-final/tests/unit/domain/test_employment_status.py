"""
Tests for employment status determination logic.
"""
import pytest

from src.domain.models.employment_status import (
    EmploymentStatus,
    TERMINATED_STATUS_CODES,
    LEAVE_STATUS_CODES,
    ACTIVE_STATUS_CODES,
    determine_employment_status,
    determine_employment_status_from_dict,
)


class TestEmploymentStatusEnum:
    """Tests for EmploymentStatus enum."""

    def test_active_status_value(self):
        """Test ACTIVE status has correct value."""
        assert EmploymentStatus.ACTIVE.value == "Active"

    def test_leave_status_value(self):
        """Test LEAVE status has correct value."""
        assert EmploymentStatus.LEAVE.value == "Leave"

    def test_terminated_status_value(self):
        """Test TERMINATED status has correct value."""
        assert EmploymentStatus.TERMINATED.value == "Terminated"

    def test_unknown_status_value(self):
        """Test UNKNOWN status has correct value."""
        assert EmploymentStatus.UNKNOWN.value == "Unknown"

    def test_all_statuses_are_unique(self):
        """Test all status values are unique."""
        values = [s.value for s in EmploymentStatus]
        assert len(values) == len(set(values))


class TestStatusCodeConstants:
    """Tests for status code constant sets."""

    def test_terminated_codes_include_t(self):
        """Test TERMINATED_STATUS_CODES includes 'T'."""
        assert "T" in TERMINATED_STATUS_CODES

    def test_terminated_codes_include_term(self):
        """Test TERMINATED_STATUS_CODES includes 'TERM'."""
        assert "TERM" in TERMINATED_STATUS_CODES

    def test_leave_codes_include_l(self):
        """Test LEAVE_STATUS_CODES includes 'L'."""
        assert "L" in LEAVE_STATUS_CODES

    def test_leave_codes_include_loa(self):
        """Test LEAVE_STATUS_CODES includes 'LOA'."""
        assert "LOA" in LEAVE_STATUS_CODES

    def test_active_codes_include_a(self):
        """Test ACTIVE_STATUS_CODES includes 'A'."""
        assert "A" in ACTIVE_STATUS_CODES

    def test_no_overlap_between_sets(self):
        """Test status code sets don't overlap."""
        assert TERMINATED_STATUS_CODES.isdisjoint(LEAVE_STATUS_CODES)
        assert TERMINATED_STATUS_CODES.isdisjoint(ACTIVE_STATUS_CODES)
        assert LEAVE_STATUS_CODES.isdisjoint(ACTIVE_STATUS_CODES)


class TestDetermineEmploymentStatus:
    """Tests for determine_employment_status function."""

    # Termination tests
    def test_terminated_with_termination_date(self):
        """Test employee with termination date returns TERMINATED."""
        result = determine_employment_status(
            status_code="A",
            termination_date="2024-03-01T00:00:00Z",
        )
        assert result == EmploymentStatus.TERMINATED

    def test_terminated_with_status_code_t(self):
        """Test employee with status code 'T' returns TERMINATED."""
        result = determine_employment_status(status_code="T")
        assert result == EmploymentStatus.TERMINATED

    def test_terminated_with_status_code_term(self):
        """Test employee with status code 'TERM' returns TERMINATED."""
        result = determine_employment_status(status_code="TERM")
        assert result == EmploymentStatus.TERMINATED

    def test_terminated_with_status_code_terminated(self):
        """Test employee with status code 'TERMINATED' returns TERMINATED."""
        result = determine_employment_status(status_code="TERMINATED")
        assert result == EmploymentStatus.TERMINATED

    def test_terminated_with_status_code_i(self):
        """Test employee with status code 'I' (Inactive) returns TERMINATED."""
        result = determine_employment_status(status_code="I")
        assert result == EmploymentStatus.TERMINATED

    def test_termination_date_overrides_active_status(self):
        """Test termination date takes priority over active status code."""
        result = determine_employment_status(
            status_code="A",
            termination_date="2024-03-01",
        )
        assert result == EmploymentStatus.TERMINATED

    def test_termination_date_overrides_leave_dates(self):
        """Test termination date takes priority over leave dates."""
        result = determine_employment_status(
            status_code="A",
            leave_start_date="2024-01-01",
            termination_date="2024-03-01",
        )
        assert result == EmploymentStatus.TERMINATED

    # Leave tests
    def test_leave_with_start_date_no_end_date(self):
        """Test employee on indefinite leave returns LEAVE."""
        result = determine_employment_status(
            status_code="A",
            leave_start_date="2024-02-01T00:00:00Z",
            leave_end_date=None,
        )
        assert result == EmploymentStatus.LEAVE

    def test_leave_with_status_code_l(self):
        """Test employee with status code 'L' returns LEAVE."""
        result = determine_employment_status(status_code="L")
        assert result == EmploymentStatus.LEAVE

    def test_leave_with_status_code_loa(self):
        """Test employee with status code 'LOA' returns LEAVE."""
        result = determine_employment_status(status_code="LOA")
        assert result == EmploymentStatus.LEAVE

    def test_leave_start_date_overrides_active_status(self):
        """Test leave start date (without end) overrides active status code."""
        result = determine_employment_status(
            status_code="A",
            leave_start_date="2024-02-01",
        )
        assert result == EmploymentStatus.LEAVE

    # Active tests
    def test_active_with_status_code_a(self):
        """Test employee with status code 'A' returns ACTIVE."""
        result = determine_employment_status(status_code="A")
        assert result == EmploymentStatus.ACTIVE

    def test_active_with_status_code_active(self):
        """Test employee with status code 'ACTIVE' returns ACTIVE."""
        result = determine_employment_status(status_code="ACTIVE")
        assert result == EmploymentStatus.ACTIVE

    def test_active_with_completed_leave(self):
        """Test employee with completed leave (has end date) returns ACTIVE."""
        result = determine_employment_status(
            status_code="A",
            leave_start_date="2024-01-01",
            leave_end_date="2024-02-01",
        )
        assert result == EmploymentStatus.ACTIVE

    def test_active_no_dates_with_status_code(self):
        """Test employee with no dates but status code returns ACTIVE."""
        result = determine_employment_status(status_code="F")
        assert result == EmploymentStatus.ACTIVE

    def test_active_default_no_data(self):
        """Test employee with no data defaults to ACTIVE."""
        result = determine_employment_status()
        assert result == EmploymentStatus.ACTIVE

    # Case sensitivity tests
    def test_status_code_case_insensitive_lowercase(self):
        """Test status code is case insensitive (lowercase)."""
        result = determine_employment_status(status_code="t")
        assert result == EmploymentStatus.TERMINATED

    def test_status_code_case_insensitive_mixed(self):
        """Test status code is case insensitive (mixed case)."""
        result = determine_employment_status(status_code="Term")
        assert result == EmploymentStatus.TERMINATED

    # Edge cases
    def test_empty_string_status_code(self):
        """Test empty string status code defaults to ACTIVE."""
        result = determine_employment_status(status_code="")
        assert result == EmploymentStatus.ACTIVE

    def test_whitespace_status_code(self):
        """Test whitespace status code defaults to ACTIVE."""
        result = determine_employment_status(status_code="   ")
        assert result == EmploymentStatus.ACTIVE

    def test_none_status_code(self):
        """Test None status code defaults to ACTIVE."""
        result = determine_employment_status(status_code=None)
        assert result == EmploymentStatus.ACTIVE


class TestDetermineEmploymentStatusFromDict:
    """Tests for determine_employment_status_from_dict function."""

    def test_parses_dict_correctly_active(self):
        """Test correctly parses dict for active employee."""
        data = {
            "employeeStatusCode": "A",
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
            "dateOfTermination": None,
        }
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.ACTIVE

    def test_parses_dict_correctly_terminated(self):
        """Test correctly parses dict for terminated employee."""
        data = {
            "employeeStatusCode": "A",
            "employeeStatusStartDate": None,
            "employeeStatusExpectedEndDate": None,
            "dateOfTermination": "2024-03-01T00:00:00Z",
        }
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.TERMINATED

    def test_parses_dict_correctly_leave(self):
        """Test correctly parses dict for employee on leave."""
        data = {
            "employeeStatusCode": "A",
            "employeeStatusStartDate": "2024-02-01T00:00:00Z",
            "employeeStatusExpectedEndDate": None,
            "dateOfTermination": None,
        }
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.LEAVE

    def test_handles_missing_keys(self):
        """Test handles dict with missing keys."""
        data = {"employeeStatusCode": "A"}
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.ACTIVE

    def test_handles_empty_dict(self):
        """Test handles empty dict."""
        result = determine_employment_status_from_dict({})
        assert result == EmploymentStatus.ACTIVE

    def test_handles_terminated_status_code_in_dict(self):
        """Test handles terminated status code in dict."""
        data = {"employeeStatusCode": "T"}
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.TERMINATED

    def test_handles_leave_status_code_in_dict(self):
        """Test handles leave status code in dict."""
        data = {"employeeStatusCode": "LOA"}
        result = determine_employment_status_from_dict(data)
        assert result == EmploymentStatus.LEAVE
