"""
TravelPerk API endpoint definitions.

Centralizes all TravelPerk SCIM API endpoint paths.
"""


class TravelPerkEndpoints:
    """TravelPerk SCIM API endpoint definitions."""

    # SCIM User endpoints
    SCIM_USERS = "/api/v2/scim/Users"

    @classmethod
    def user_by_id(cls, user_id: str) -> str:
        """Get endpoint for specific user by ID."""
        return f"{cls.SCIM_USERS}/{user_id}"

    @classmethod
    def filter_by_external_id(cls, external_id: str) -> dict:
        """Get filter params for external ID lookup."""
        return {"filter": f'externalId eq "{external_id}"'}

    @classmethod
    def filter_by_user_name(cls, user_name: str) -> dict:
        """Get filter params for userName (email) lookup."""
        return {"filter": f'userName eq "{user_name}"'}
