"""Build single TravelPerk user CLI."""

import json
import os
import sys
from pathlib import Path

from ...application.services import UserBuilderService
from ...infrastructure.adapters.ukg import UKGClient


def main() -> None:
    """Main entry point for build user CLI."""
    if len(sys.argv) < 3:
        print("usage: python build-travelperk-user.py <employeeNumber> <companyID>")
        sys.exit(1)

    employee_number = sys.argv[1]
    company_id = sys.argv[2]
    debug = os.getenv("DEBUG", "0") == "1"

    # Initialize client and service
    ukg_client = UKGClient(debug=debug)
    builder_service = UserBuilderService(ukg_client, debug=debug)

    # Build user
    user = builder_service.build_user(employee_number, company_id)
    payload = user.to_api_payload()

    # Save to file
    out_path = Path("data") / f"travelperk_user_{employee_number}.json"
    out_path.parent.mkdir(exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(str(out_path.absolute()))


if __name__ == "__main__":
    main()
