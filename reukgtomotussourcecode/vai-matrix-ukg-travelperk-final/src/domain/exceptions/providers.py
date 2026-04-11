"""
Provider-specific API exceptions.

Contains exceptions specific to UKG and TravelPerk APIs.
"""

from typing import Optional, Dict, Any

from .base import ApiError


class UkgApiError(ApiError):
    """Exception for UKG API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"UKG_ERROR_{status_code}" if status_code else "UKG_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )


class TravelPerkApiError(ApiError):
    """Exception for TravelPerk SCIM API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"TRAVELPERK_ERROR_{status_code}" if status_code else "TRAVELPERK_ERROR",
            response_body=response_body,
            correlation_id=correlation_id,
        )
