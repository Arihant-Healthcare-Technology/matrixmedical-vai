"""
Constants for Motus integration.

Provides configuration constants and mappings.
"""

from enum import Enum
from typing import Dict


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

# Default values
DEFAULT_UKG_TIMEOUT = 45.0
DEFAULT_MOTUS_TIMEOUT = 45.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_RETRY_DELAY = 0.2
DEFAULT_MAX_RETRY_DELAY = 3.2
DEFAULT_WORKERS = 12
UKG_MAX_PAGE_SIZE = 2147483647
