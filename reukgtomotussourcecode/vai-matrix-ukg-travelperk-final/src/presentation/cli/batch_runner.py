"""Batch runner CLI for TravelPerk synchronization."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional, Set, List

from common import configure_logging, get_logger, RedactingFilter

from ...application.services import UserSyncService
from ...infrastructure.adapters.ukg import UKGClient
from ...infrastructure.adapters.travelperk import TravelPerkClient
from ...infrastructure.config.settings import BatchSettings


# Configure logging with correlation support and PII redaction
configure_logging(include_module=True)
logger = get_logger(__name__)

# Add PII redaction filter to all handlers
for handler in logging.root.handlers:
    handler.addFilter(RedactingFilter())


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run TravelPerk batch synchronization")
    parser.add_argument(
        "--company-id",
        dest="company_id",
        help="UKG company ID (e.g., J9A6Y)",
    )
    parser.add_argument(
        "--states",
        dest="states",
        help="Comma-separated US states to filter (e.g., FL,MS,NJ)",
    )
    parser.add_argument(
        "--workers",
        dest="workers",
        type=int,
        help="Thread pool size",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Validate but do not POST/PUT to TravelPerk",
    )
    parser.add_argument(
        "--save-local",
        dest="save_local",
        action="store_true",
        help="Write JSON files to data/batch",
    )
    parser.add_argument(
        "--limit",
        dest="limit",
        type=int,
        help="Limit number of users to process (for testing)",
    )
    parser.add_argument(
        "--insert-supervisor",
        dest="insert_supervisor",
        help="Pre-insert supervisor(s) by employeeNumber (comma-separated)",
    )
    parser.add_argument(
        "--employee-type-codes",
        dest="employee_type_codes",
        help="Filter by employeeTypeCode(s) (comma-separated, e.g., FTC,HRC,TMC)",
    )
    return parser.parse_args()


def parse_states(states_arg: Optional[str]) -> Optional[Set[str]]:
    """Parse states argument to set."""
    if not states_arg:
        return None
    return {s.strip().upper() for s in states_arg.split(",") if s.strip()}


def parse_list(arg: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated list argument."""
    if not arg:
        return None
    return [s.strip() for s in arg.split(",") if s.strip()]


def main() -> None:
    """Main entry point for batch runner."""
    args = parse_args()

    # Apply CLI args to environment
    if args.workers:
        os.environ["WORKERS"] = str(args.workers)
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    if args.save_local:
        os.environ["SAVE_LOCAL"] = "1"
    if args.limit:
        os.environ["LIMIT"] = str(args.limit)

    # Load settings
    batch_settings = BatchSettings.from_env()

    # Override from CLI
    if args.company_id:
        batch_settings.company_id = args.company_id
    if args.states:
        batch_settings.states_filter = args.states
    if args.employee_type_codes:
        batch_settings.employee_type_codes = parse_list(args.employee_type_codes)
    if args.insert_supervisor:
        batch_settings.insert_supervisors = parse_list(args.insert_supervisor)

    # Validate
    if not batch_settings.company_id:
        raise SystemExit(
            "Error: --company-id argument or COMPANY_ID environment variable is required"
        )

    states_filter = parse_states(batch_settings.states_filter)
    debug = os.getenv("DEBUG", "0") == "1"

    # Log configuration
    has_api_key = bool(os.getenv("TRAVELPERK_API_KEY"))
    type_codes_str = ",".join(batch_settings.employee_type_codes or []) or "ALL"
    logger.info(
        f"Configuration: companyID={batch_settings.company_id} | "
        f"states={batch_settings.states_filter or 'ALL'} | "
        f"employeeTypeCodes={type_codes_str} | "
        f"workers={batch_settings.workers} | "
        f"dry_run={batch_settings.dry_run} | "
        f"save_local={batch_settings.save_local} | "
        f"TRAVELPERK_API_KEY={'SET' if has_api_key else 'MISSING'}"
    )

    # Initialize clients
    ukg_client = UKGClient(debug=debug)
    travelperk_client = TravelPerkClient(debug=debug)

    # Initialize service
    sync_service = UserSyncService(ukg_client, travelperk_client, debug=debug)

    # Pre-insert supervisors if specified
    pre_inserted_mapping = {}
    if batch_settings.insert_supervisors:
        pre_inserted_mapping = sync_service.insert_supervisors(
            batch_settings.insert_supervisors,
            batch_settings,
        )
        logger.info(f"Pre-inserted {len(pre_inserted_mapping)} supervisor(s)")

    # Fetch employees from UKG
    employees = ukg_client.get_all_employment_details_by_company(
        batch_settings.company_id,
        employee_type_codes=batch_settings.employee_type_codes,
    )

    # Sync
    mapping = sync_service.sync_batch(
        employees,
        batch_settings,
        states_filter=states_filter,
        pre_inserted_mapping=pre_inserted_mapping,
    )

    # Save mapping
    if mapping:
        out_path = Path(batch_settings.out_dir).resolve()
        mapping_file = out_path / "employee_to_travelperk_id_mapping.json"
        with mapping_file.open("w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        logger.info(f"Saved mapping to {mapping_file}")


if __name__ == "__main__":
    main()
