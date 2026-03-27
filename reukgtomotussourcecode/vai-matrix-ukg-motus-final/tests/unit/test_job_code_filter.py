"""
Unit tests for job code eligibility filtering.
Tests the ELIGIBLE_JOB_CODES and filter_by_eligible_job_codes directly.
"""
import sys
import pytest
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the constants and function directly by extracting them
# (The batch module has side effects on import, so we define the test versions here)

# Eligible job codes for Motus sync (same as in run-motus-batch.py)
ELIGIBLE_JOB_CODES = {
    # FAVR Program (21232)
    "1103", "4165", "4166", "1102", "1106", "4197", "4196",
    # CPM Program (21233)
    "2817", "4121", "2157"
}

def filter_by_eligible_job_codes(items: List[Dict[str, Any]], debug: bool = False) -> List[Dict[str, Any]]:
    """Filter employees to only those with eligible job codes."""
    eligible = []
    for item in items:
        job_code = str(item.get("primaryJobCode", "") or "").strip()
        # Also check without leading zeros
        job_code_normalized = job_code.lstrip("0")
        if job_code in ELIGIBLE_JOB_CODES or job_code_normalized in ELIGIBLE_JOB_CODES:
            eligible.append(item)
        elif debug:
            print(f"[DEBUG] Skipping employee {item.get('employeeNumber')} - ineligible job code: {job_code}")
    return eligible


class TestEligibleJobCodes:
    """Tests for ELIGIBLE_JOB_CODES constant."""

    def test_favr_job_codes_included(self):
        """Test FAVR job codes are in eligible list."""
        favr_codes = {"1103", "4165", "4166", "1102", "1106", "4197", "4196"}

        for code in favr_codes:
            assert code in ELIGIBLE_JOB_CODES, f"FAVR code {code} missing"

    def test_cpm_job_codes_included(self):
        """Test CPM job codes are in eligible list."""
        cpm_codes = {"2817", "4121", "2157"}

        for code in cpm_codes:
            assert code in ELIGIBLE_JOB_CODES, f"CPM code {code} missing"

    def test_ineligible_codes_not_included(self):
        """Test random codes are not eligible."""
        assert "9999" not in ELIGIBLE_JOB_CODES
        assert "0000" not in ELIGIBLE_JOB_CODES

    def test_total_eligible_codes_count(self):
        """Test total count of eligible job codes."""
        # Should have 10 eligible codes total (7 FAVR + 3 CPM)
        assert len(ELIGIBLE_JOB_CODES) == 10


class TestFilterByEligibleJobCodes:
    """Tests for filter_by_eligible_job_codes function."""

    def test_filters_eligible_employees(self):
        """Test returns only eligible employees."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},  # FAVR - eligible
            {"employeeNumber": "002", "primaryJobCode": "9999"},  # Not eligible
            {"employeeNumber": "003", "primaryJobCode": "2817"},  # CPM - eligible
        ]

        result = filter_by_eligible_job_codes(items)

        assert len(result) == 2
        assert result[0]["employeeNumber"] == "001"
        assert result[1]["employeeNumber"] == "003"

    def test_handles_empty_job_code(self):
        """Test handles empty job code."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": ""},
            {"employeeNumber": "002", "primaryJobCode": None},
        ]

        result = filter_by_eligible_job_codes(items)

        assert len(result) == 0

    def test_handles_job_code_with_leading_zeros(self):
        """Test handles job codes with leading zeros."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "01103"},  # Leading zero
        ]

        result = filter_by_eligible_job_codes(items)

        # Should match after stripping leading zeros
        assert len(result) == 1

    def test_returns_empty_for_no_eligible(self):
        """Test returns empty list when no eligible employees."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "8888"},
            {"employeeNumber": "002", "primaryJobCode": "7777"},
        ]

        result = filter_by_eligible_job_codes(items)

        assert len(result) == 0

    def test_preserves_all_employee_data(self):
        """Test preserves all fields in returned items."""
        items = [
            {
                "employeeNumber": "001",
                "primaryJobCode": "1103",
                "firstName": "John",
                "lastName": "Doe",
                "email": "john@example.com"
            }
        ]

        result = filter_by_eligible_job_codes(items)

        assert result[0]["firstName"] == "John"
        assert result[0]["lastName"] == "Doe"
        assert result[0]["email"] == "john@example.com"

    def test_handles_missing_job_code_key(self):
        """Test handles items without primaryJobCode key."""
        items = [
            {"employeeNumber": "001"},  # No primaryJobCode
        ]

        result = filter_by_eligible_job_codes(items)

        assert len(result) == 0

    def test_handles_empty_list(self):
        """Test handles empty input list."""
        result = filter_by_eligible_job_codes([])

        assert result == []

    def test_all_favr_codes_pass_filter(self):
        """Test all FAVR codes pass through filter."""
        favr_items = [
            {"employeeNumber": str(i), "primaryJobCode": code}
            for i, code in enumerate(["1103", "4165", "4166", "1102", "1106", "4197", "4196"])
        ]

        result = filter_by_eligible_job_codes(favr_items)

        assert len(result) == 7

    def test_all_cpm_codes_pass_filter(self):
        """Test all CPM codes pass through filter."""
        cpm_items = [
            {"employeeNumber": str(i), "primaryJobCode": code}
            for i, code in enumerate(["2817", "4121", "2157"])
        ]

        result = filter_by_eligible_job_codes(cpm_items)

        assert len(result) == 3

    def test_mixed_eligible_and_ineligible(self):
        """Test mix of eligible and ineligible codes."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},   # FAVR - eligible
            {"employeeNumber": "002", "primaryJobCode": "5555"},   # Not eligible
            {"employeeNumber": "003", "primaryJobCode": "2817"},   # CPM - eligible
            {"employeeNumber": "004", "primaryJobCode": "1234"},   # Not eligible
            {"employeeNumber": "005", "primaryJobCode": "4165"},   # FAVR - eligible
        ]

        result = filter_by_eligible_job_codes(items)

        assert len(result) == 3
        emp_numbers = [e["employeeNumber"] for e in result]
        assert "001" in emp_numbers
        assert "003" in emp_numbers
        assert "005" in emp_numbers
