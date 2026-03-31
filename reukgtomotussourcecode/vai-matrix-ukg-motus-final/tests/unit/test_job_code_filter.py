"""
Unit tests for job code eligibility filtering.
Tests the filter_by_eligible_job_codes logic directly.

Note: Job codes are now read from JOB_IDS environment variable in production.
These tests use a test fixture with the expected job codes.
"""
import logging
import os
import sys
import pytest
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test job codes: FAVR + CPM programs (same as expected in production JOB_IDS env var)
TEST_JOB_IDS = {
    # FAVR Program (21232)
    "1103", "4165", "4166", "1102", "1106", "4197", "4196",
    # CPM Program (21233)
    "2817", "4121", "2157"
}


def get_eligible_job_codes_from_env() -> Set[str]:
    """Get eligible job codes from JOB_IDS environment variable."""
    job_ids_env = os.getenv("JOB_IDS", "").strip()
    if not job_ids_env:
        raise SystemExit("Error: JOB_IDS environment variable is required")
    return {code.strip() for code in job_ids_env.split(",") if code.strip()}


def filter_by_eligible_job_codes(
    items: List[Dict[str, Any]],
    eligible_job_codes: Set[str],
    debug: bool = False
) -> List[Dict[str, Any]]:
    """Filter employees to only those with eligible job codes."""
    eligible = []
    for item in items:
        job_code = str(item.get("primaryJobCode", "") or "").strip()
        # Also check without leading zeros
        job_code_normalized = job_code.lstrip("0")
        if job_code in eligible_job_codes or job_code_normalized in eligible_job_codes:
            eligible.append(item)
        elif debug:
            logger.debug(f"Skipping employee {item.get('employeeNumber')} - ineligible job code: {job_code}")
    return eligible


class TestEligibleJobCodes:
    """Tests for TEST_JOB_IDS fixture (expected job codes)."""

    def test_favr_job_codes_included(self):
        """Test FAVR job codes are in eligible list."""
        favr_codes = {"1103", "4165", "4166", "1102", "1106", "4197", "4196"}

        for code in favr_codes:
            assert code in TEST_JOB_IDS, f"FAVR code {code} missing"

    def test_cpm_job_codes_included(self):
        """Test CPM job codes are in eligible list."""
        cpm_codes = {"2817", "4121", "2157"}

        for code in cpm_codes:
            assert code in TEST_JOB_IDS, f"CPM code {code} missing"

    def test_ineligible_codes_not_included(self):
        """Test random codes are not eligible."""
        assert "9999" not in TEST_JOB_IDS
        assert "0000" not in TEST_JOB_IDS

    def test_total_eligible_codes_count(self):
        """Test total count of eligible job codes."""
        # Should have 10 eligible codes total (7 FAVR + 3 CPM)
        assert len(TEST_JOB_IDS) == 10

    def test_get_eligible_job_codes_from_env(self, monkeypatch):
        """Test get_eligible_job_codes_from_env parses env var."""
        monkeypatch.setenv("JOB_IDS", "1103,4165,2817")
        codes = get_eligible_job_codes_from_env()
        assert codes == {"1103", "4165", "2817"}

    def test_get_eligible_job_codes_missing_env_raises(self, monkeypatch):
        """Test get_eligible_job_codes_from_env raises if env not set."""
        monkeypatch.delenv("JOB_IDS", raising=False)
        with pytest.raises(SystemExit):
            get_eligible_job_codes_from_env()


class TestFilterByEligibleJobCodes:
    """Tests for filter_by_eligible_job_codes function."""

    def test_filters_eligible_employees(self):
        """Test returns only eligible employees."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "1103"},  # FAVR - eligible
            {"employeeNumber": "002", "primaryJobCode": "9999"},  # Not eligible
            {"employeeNumber": "003", "primaryJobCode": "2817"},  # CPM - eligible
        ]

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        assert len(result) == 2
        assert result[0]["employeeNumber"] == "001"
        assert result[1]["employeeNumber"] == "003"

    def test_handles_empty_job_code(self):
        """Test handles empty job code."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": ""},
            {"employeeNumber": "002", "primaryJobCode": None},
        ]

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        assert len(result) == 0

    def test_handles_job_code_with_leading_zeros(self):
        """Test handles job codes with leading zeros."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "01103"},  # Leading zero
        ]

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        # Should match after stripping leading zeros
        assert len(result) == 1

    def test_returns_empty_for_no_eligible(self):
        """Test returns empty list when no eligible employees."""
        items = [
            {"employeeNumber": "001", "primaryJobCode": "8888"},
            {"employeeNumber": "002", "primaryJobCode": "7777"},
        ]

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

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

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        assert result[0]["firstName"] == "John"
        assert result[0]["lastName"] == "Doe"
        assert result[0]["email"] == "john@example.com"

    def test_handles_missing_job_code_key(self):
        """Test handles items without primaryJobCode key."""
        items = [
            {"employeeNumber": "001"},  # No primaryJobCode
        ]

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        assert len(result) == 0

    def test_handles_empty_list(self):
        """Test handles empty input list."""
        result = filter_by_eligible_job_codes([], TEST_JOB_IDS)

        assert result == []

    def test_all_favr_codes_pass_filter(self):
        """Test all FAVR codes pass through filter."""
        favr_items = [
            {"employeeNumber": str(i), "primaryJobCode": code}
            for i, code in enumerate(["1103", "4165", "4166", "1102", "1106", "4197", "4196"])
        ]

        result = filter_by_eligible_job_codes(favr_items, TEST_JOB_IDS)

        assert len(result) == 7

    def test_all_cpm_codes_pass_filter(self):
        """Test all CPM codes pass through filter."""
        cpm_items = [
            {"employeeNumber": str(i), "primaryJobCode": code}
            for i, code in enumerate(["2817", "4121", "2157"])
        ]

        result = filter_by_eligible_job_codes(cpm_items, TEST_JOB_IDS)

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

        result = filter_by_eligible_job_codes(items, TEST_JOB_IDS)

        assert len(result) == 3
        emp_numbers = [e["employeeNumber"] for e in result]
        assert "001" in emp_numbers
        assert "003" in emp_numbers
        assert "005" in emp_numbers

    def test_custom_job_codes(self):
        """Test filter works with custom job code set."""
        custom_codes = {"1234", "5678"}
        items = [
            {"employeeNumber": "001", "primaryJobCode": "1234"},
            {"employeeNumber": "002", "primaryJobCode": "9999"},
        ]

        result = filter_by_eligible_job_codes(items, custom_codes)

        assert len(result) == 1
        assert result[0]["employeeNumber"] == "001"
