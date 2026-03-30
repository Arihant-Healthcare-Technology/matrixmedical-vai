"""Upsert single TravelPerk user CLI."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ...domain.models import TravelPerkUser, UserName
from ...infrastructure.adapters.travelperk import TravelPerkClient


def load_user_payload(employee_number: str) -> Dict[str, Any]:
    """Load user payload from JSON file."""
    path = Path("data") / f"travelperk_user_{employee_number}.json"
    if not path.exists():
        raise SystemExit(f"User payload not found: {path}. Run the builder first.")

    with path.open("r") as f:
        data = json.load(f)

    return data if isinstance(data, dict) else (data[0] if isinstance(data, list) else {})


def payload_to_user(payload: Dict[str, Any]) -> TravelPerkUser:
    """Convert payload dict to TravelPerkUser."""
    name = payload.get("name", {})
    enterprise_ext = payload.get(
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {}
    )

    return TravelPerkUser(
        external_id=str(payload.get("externalId", "")),
        user_name=payload.get("userName", ""),
        name=UserName(
            given_name=name.get("givenName", ""),
            family_name=name.get("familyName", ""),
        ),
        active=payload.get("active", True),
        cost_center=enterprise_ext.get("costCenter"),
    )


def main() -> None:
    """Main entry point for upsert user CLI."""
    if len(sys.argv) < 2:
        print("usage: python upsert-travelperk-user.py <employeeNumber> [--dry-run]")
        sys.exit(1)

    employee_number = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    debug = os.getenv("DEBUG", "0") == "1"

    # Load payload
    payload = load_user_payload(employee_number)

    if dry_run:
        result = {
            "dry_run": True,
            "action": "validate",
            "externalId": employee_number,
        }
        print(json.dumps(result, indent=2))
        return

    # Convert to user and upsert
    user = payload_to_user(payload)

    # Validate
    errors = user.validate()
    if errors:
        raise SystemExit(f"Validation failed: {'; '.join(errors)}")

    # Initialize client
    travelperk_client = TravelPerkClient(debug=debug)

    # Upsert
    result = travelperk_client.upsert_user(user)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
