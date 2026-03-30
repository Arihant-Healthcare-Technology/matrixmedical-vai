"""
Program type definitions.

Defines the Motus program types (FAVR, CPM) and job code mappings.
"""

from enum import Enum
from typing import Dict, Optional


class ProgramType(Enum):
    """Motus program types."""

    FAVR = 21232  # Fixed and Variable Rate
    CPM = 21233   # Cents Per Mile


# Job code to program ID mapping
JOBCODE_TO_PROGRAM: Dict[str, int] = {
    # FAVR (21232)
    "1103": ProgramType.FAVR.value,
    "4165": ProgramType.FAVR.value,
    "4166": ProgramType.FAVR.value,
    "1102": ProgramType.FAVR.value,
    "1106": ProgramType.FAVR.value,
    "4197": ProgramType.FAVR.value,
    "4196": ProgramType.FAVR.value,

    # CPM (21233)
    "4154": ProgramType.CPM.value,
    "4152": ProgramType.CPM.value,
    "2817": ProgramType.CPM.value,
    "4121": ProgramType.CPM.value,
    "2157": ProgramType.CPM.value,
}


def resolve_program_id_from_job_code(
    job_code: Optional[str],
    default: Optional[int] = None
) -> Optional[int]:
    """
    Resolve program ID from job code.

    Args:
        job_code: Primary job code from UKG
        default: Default program ID if not found

    Returns:
        Program ID or default
    """
    if job_code is None:
        return default

    job_str = str(job_code).strip()
    # First try exact match, then without leading zeros
    return JOBCODE_TO_PROGRAM.get(job_str) or JOBCODE_TO_PROGRAM.get(
        job_str.lstrip("0"), default
    )
