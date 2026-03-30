"""Tests for configuration constants."""

import pytest

from src.infrastructure.config.constants import (
    ProgramType,
    JOBCODE_TO_PROGRAM,
    DEFAULT_UKG_TIMEOUT,
    DEFAULT_MOTUS_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_INITIAL_RETRY_DELAY,
    DEFAULT_MAX_RETRY_DELAY,
    DEFAULT_WORKERS,
    UKG_MAX_PAGE_SIZE,
)


class TestProgramType:
    """Test cases for ProgramType enum."""

    def test_favr_value(self):
        """Test FAVR program ID."""
        assert ProgramType.FAVR.value == 21232

    def test_cpm_value(self):
        """Test CPM program ID."""
        assert ProgramType.CPM.value == 21233

    def test_enum_members(self):
        """Test all enum members exist."""
        assert hasattr(ProgramType, "FAVR")
        assert hasattr(ProgramType, "CPM")

    def test_from_value(self):
        """Test creating from value."""
        assert ProgramType(21232) == ProgramType.FAVR
        assert ProgramType(21233) == ProgramType.CPM

    def test_invalid_value(self):
        """Test invalid value raises error."""
        with pytest.raises(ValueError):
            ProgramType(99999)


class TestJobCodeToProgram:
    """Test cases for JOBCODE_TO_PROGRAM mapping."""

    def test_mapping_is_dict(self):
        """Test mapping is a dictionary."""
        assert isinstance(JOBCODE_TO_PROGRAM, dict)

    def test_mapping_not_empty(self):
        """Test mapping is not empty."""
        assert len(JOBCODE_TO_PROGRAM) > 0

    def test_favr_job_codes(self):
        """Test FAVR job codes map to correct program."""
        favr_codes = ["1103", "4165", "4166", "1102", "1106", "4197", "4196"]

        for code in favr_codes:
            assert JOBCODE_TO_PROGRAM.get(code) == ProgramType.FAVR.value

    def test_cpm_job_codes(self):
        """Test CPM job codes map to correct program."""
        cpm_codes = ["4154", "4152", "2817", "4121", "2157"]

        for code in cpm_codes:
            assert JOBCODE_TO_PROGRAM.get(code) == ProgramType.CPM.value

    def test_unknown_job_code(self):
        """Test unknown job code returns None."""
        assert JOBCODE_TO_PROGRAM.get("99999") is None

    def test_all_values_are_valid_program_ids(self):
        """Test all values in mapping are valid program IDs."""
        valid_ids = {ProgramType.FAVR.value, ProgramType.CPM.value}

        for code, program_id in JOBCODE_TO_PROGRAM.items():
            assert program_id in valid_ids, f"Job code {code} has invalid program ID"

    def test_job_codes_are_strings(self):
        """Test all job codes are strings."""
        for code in JOBCODE_TO_PROGRAM.keys():
            assert isinstance(code, str)


class TestDefaultConstants:
    """Test cases for default constants."""

    def test_default_ukg_timeout(self):
        """Test default UKG timeout value."""
        assert DEFAULT_UKG_TIMEOUT == 45.0
        assert isinstance(DEFAULT_UKG_TIMEOUT, float)

    def test_default_motus_timeout(self):
        """Test default Motus timeout value."""
        assert DEFAULT_MOTUS_TIMEOUT == 45.0
        assert isinstance(DEFAULT_MOTUS_TIMEOUT, float)

    def test_default_max_retries(self):
        """Test default max retries value."""
        assert DEFAULT_MAX_RETRIES == 3
        assert isinstance(DEFAULT_MAX_RETRIES, int)

    def test_default_initial_retry_delay(self):
        """Test default initial retry delay value."""
        assert DEFAULT_INITIAL_RETRY_DELAY == 0.2
        assert isinstance(DEFAULT_INITIAL_RETRY_DELAY, float)

    def test_default_max_retry_delay(self):
        """Test default max retry delay value."""
        assert DEFAULT_MAX_RETRY_DELAY == 3.2
        assert isinstance(DEFAULT_MAX_RETRY_DELAY, float)

    def test_default_workers(self):
        """Test default workers value."""
        assert DEFAULT_WORKERS == 12
        assert isinstance(DEFAULT_WORKERS, int)

    def test_ukg_max_page_size(self):
        """Test UKG max page size value."""
        assert UKG_MAX_PAGE_SIZE == 2147483647  # Max int32
        assert isinstance(UKG_MAX_PAGE_SIZE, int)

    def test_retry_delay_progression(self):
        """Test retry delay values are reasonable for exponential backoff."""
        # Initial delay should be less than max
        assert DEFAULT_INITIAL_RETRY_DELAY < DEFAULT_MAX_RETRY_DELAY

        # Initial delay should be small
        assert DEFAULT_INITIAL_RETRY_DELAY <= 1.0

        # Max delay should be reasonable (not too long)
        assert DEFAULT_MAX_RETRY_DELAY <= 60.0

    def test_workers_is_positive(self):
        """Test default workers is a positive number."""
        assert DEFAULT_WORKERS > 0

    def test_timeouts_are_positive(self):
        """Test timeout values are positive."""
        assert DEFAULT_UKG_TIMEOUT > 0
        assert DEFAULT_MOTUS_TIMEOUT > 0
