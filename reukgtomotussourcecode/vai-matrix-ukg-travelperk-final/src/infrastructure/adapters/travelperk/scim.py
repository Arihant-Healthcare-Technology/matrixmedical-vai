"""
SCIM protocol utilities for TravelPerk.

Provides SCIM-specific functionality for user management.
"""

from typing import Any, Dict, List, Optional


class SCIMSchemas:
    """SCIM schema URIs."""

    CORE_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
    ENTERPRISE_USER = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
    TRAVELPERK_USER = "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"
    PATCH_OP = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


class SCIMOperations:
    """SCIM operation types."""

    ADD = "add"
    REPLACE = "replace"
    REMOVE = "remove"


def build_patch_operation(
    op: str,
    path: str,
    value: Any,
) -> Dict[str, Any]:
    """
    Build a single SCIM PATCH operation.

    Args:
        op: Operation type (add, replace, remove)
        path: Attribute path
        value: New value

    Returns:
        SCIM operation dict
    """
    return {
        "op": op,
        "path": path,
        "value": value,
    }


def build_patch_payload(
    operations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build SCIM PATCH request payload.

    Args:
        operations: List of SCIM operations

    Returns:
        Complete PATCH payload
    """
    return {
        "schemas": [SCIMSchemas.PATCH_OP],
        "Operations": operations,
    }


def extract_resources(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract Resources array from SCIM response.

    Args:
        response_data: SCIM list response

    Returns:
        List of resource objects
    """
    return response_data.get("Resources", [])


def get_user_id(user_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract user ID from SCIM user object.

    Args:
        user_data: SCIM user object

    Returns:
        User ID or None
    """
    return user_data.get("id")


def get_external_id(user_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract external ID from SCIM user object.

    Args:
        user_data: SCIM user object

    Returns:
        External ID or None
    """
    return user_data.get("externalId")
