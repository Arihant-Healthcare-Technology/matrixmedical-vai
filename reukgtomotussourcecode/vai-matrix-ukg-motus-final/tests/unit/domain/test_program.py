"""
Tests for program type definitions and job code resolution.
"""
import pytest

from src.domain.models.program import (
    ProgramType,
    JOBCODE_TO_PROGRAM,
    resolve_program_id_from_job_code,
)


class TestProgramTypeEnum:
    """Tests for ProgramType enum."""

    def test_favr_value_is_21232(self):
        """Test FAVR program ID is 21232."""
        assert ProgramType.FAVR.value == 21232

    def test_cpm_value_is_21233(self):
        """Test CPM program ID is 21233."""
        assert ProgramType.CPM.value == 21233

    def test_program_type_is_enum(self):
        """Test ProgramType is an Enum."""
        from enum import Enum
        assert issubclass(ProgramType, Enum)

    def test_program_types_are_unique(self):
        """Test all program type values are unique."""
        values = [p.value for p in ProgramType]
        assert len(values) == len(set(values))


class TestJobcodeToProgram:
    """Tests for JOBCODE_TO_PROGRAM mapping."""

    def test_favr_job_codes_map_correctly(self):
        """Test all FAVR job codes map to FAVR program ID."""
        favr_codes = ["1103", "4165", "4166", "1102", "1106", "4197", "4196"]
        for code in favr_codes:
            assert JOBCODE_TO_PROGRAM.get(code) == ProgramType.FAVR.value, \
                f"Job code {code} should map to FAVR"

    def test_cpm_job_codes_map_correctly(self):
        """Test all CPM job codes map to CPM program ID."""
        cpm_codes = ["4154", "4152", "2817", "4121", "2157"]
        for code in cpm_codes:
            assert JOBCODE_TO_PROGRAM.get(code) == ProgramType.CPM.value, \
                f"Job code {code} should map to CPM"

    def test_mapping_has_expected_count(self):
        """Test JOBCODE_TO_PROGRAM has expected number of entries."""
        assert len(JOBCODE_TO_PROGRAM) == 12

    def test_no_duplicate_job_codes(self):
        """Test no duplicate job codes in mapping."""
        codes = list(JOBCODE_TO_PROGRAM.keys())
        assert len(codes) == len(set(codes))

    def test_all_values_are_valid_program_ids(self):
        """Test all values in mapping are valid program IDs."""
        valid_ids = {p.value for p in ProgramType}
        for job_code, program_id in JOBCODE_TO_PROGRAM.items():
            assert program_id in valid_ids, \
                f"Job code {job_code} maps to invalid program ID {program_id}"


class TestResolveProgramIdFromJobCode:
    """Tests for resolve_program_id_from_job_code function."""

    # FAVR job code tests
    def test_resolve_favr_job_code_1103(self):
        """Test resolving FAVR job code 1103."""
        result = resolve_program_id_from_job_code("1103")
        assert result == ProgramType.FAVR.value

    def test_resolve_favr_job_code_4165(self):
        """Test resolving FAVR job code 4165."""
        result = resolve_program_id_from_job_code("4165")
        assert result == ProgramType.FAVR.value

    def test_resolve_favr_job_code_4166(self):
        """Test resolving FAVR job code 4166."""
        result = resolve_program_id_from_job_code("4166")
        assert result == ProgramType.FAVR.value

    # CPM job code tests
    def test_resolve_cpm_job_code_4154(self):
        """Test resolving CPM job code 4154."""
        result = resolve_program_id_from_job_code("4154")
        assert result == ProgramType.CPM.value

    def test_resolve_cpm_job_code_4152(self):
        """Test resolving CPM job code 4152."""
        result = resolve_program_id_from_job_code("4152")
        assert result == ProgramType.CPM.value

    def test_resolve_cpm_job_code_2817(self):
        """Test resolving CPM job code 2817."""
        result = resolve_program_id_from_job_code("2817")
        assert result == ProgramType.CPM.value

    # Edge cases
    def test_resolve_with_leading_zeros(self):
        """Test resolving job code with leading zeros."""
        # "01103" should resolve to "1103"
        result = resolve_program_id_from_job_code("01103")
        assert result == ProgramType.FAVR.value

    def test_resolve_with_whitespace(self):
        """Test resolving job code with whitespace."""
        result = resolve_program_id_from_job_code("  4154  ")
        assert result == ProgramType.CPM.value

    def test_resolve_unknown_returns_none(self):
        """Test resolving unknown job code returns None."""
        result = resolve_program_id_from_job_code("9999")
        assert result is None

    def test_resolve_unknown_with_default(self):
        """Test resolving unknown job code with default value."""
        result = resolve_program_id_from_job_code("9999", default=ProgramType.CPM.value)
        assert result == ProgramType.CPM.value

    def test_resolve_none_input(self):
        """Test resolving None job code returns None."""
        result = resolve_program_id_from_job_code(None)
        assert result is None

    def test_resolve_none_input_with_default(self):
        """Test resolving None job code with default value."""
        result = resolve_program_id_from_job_code(None, default=21233)
        assert result == 21233

    def test_resolve_empty_string(self):
        """Test resolving empty string returns None."""
        result = resolve_program_id_from_job_code("")
        assert result is None

    def test_resolve_integer_input(self):
        """Test resolving integer job code (converted to string)."""
        result = resolve_program_id_from_job_code(4154)
        assert result == ProgramType.CPM.value

    def test_resolve_all_favr_codes(self):
        """Test resolving all FAVR job codes."""
        favr_codes = ["1103", "4165", "4166", "1102", "1106", "4197", "4196"]
        for code in favr_codes:
            result = resolve_program_id_from_job_code(code)
            assert result == ProgramType.FAVR.value, \
                f"Job code {code} should resolve to FAVR"

    def test_resolve_all_cpm_codes(self):
        """Test resolving all CPM job codes."""
        cpm_codes = ["4154", "4152", "2817", "4121", "2157"]
        for code in cpm_codes:
            result = resolve_program_id_from_job_code(code)
            assert result == ProgramType.CPM.value, \
                f"Job code {code} should resolve to CPM"


class TestProgramTypeIntegration:
    """Integration tests for program type resolution."""

    def test_all_mapped_codes_resolve_correctly(self):
        """Test all mapped job codes resolve to expected program IDs."""
        for job_code, expected_program_id in JOBCODE_TO_PROGRAM.items():
            result = resolve_program_id_from_job_code(job_code)
            assert result == expected_program_id, \
                f"Job code {job_code} should resolve to {expected_program_id}"

    def test_program_type_values_match_mapping_values(self):
        """Test ProgramType values match values in JOBCODE_TO_PROGRAM."""
        mapping_values = set(JOBCODE_TO_PROGRAM.values())
        program_values = {p.value for p in ProgramType}
        assert mapping_values == program_values
