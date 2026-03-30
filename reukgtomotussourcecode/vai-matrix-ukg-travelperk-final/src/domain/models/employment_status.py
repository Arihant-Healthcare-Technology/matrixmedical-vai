"""Employment status enumeration."""

from enum import Enum


class EmploymentStatus(Enum):
    """Employee status codes from UKG."""

    ACTIVE = "A"
    TERMINATED = "T"
    LEAVE = "L"
    INACTIVE = "I"

    @classmethod
    def from_code(cls, code: str) -> "EmploymentStatus":
        """Get status from code string."""
        code = code.strip().upper() if code else ""
        for status in cls:
            if status.value == code:
                return status
        return cls.INACTIVE

    @property
    def is_active(self) -> bool:
        """Check if status represents an active employee."""
        return self == EmploymentStatus.ACTIVE
