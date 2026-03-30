"""
Batch runner CLI.

Entry point for running Motus batch synchronization.
"""

import argparse
import os
from typing import Optional, Set

from src.application.services import DriverSyncService
from src.infrastructure.adapters.motus import MotusClient
from src.infrastructure.adapters.ukg import UKGClient
from src.infrastructure.config.settings import BatchSettings, MotusSettings, UKGSettings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run Motus batch synchronization")
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
        help="Validate but do not POST/PUT to Motus",
    )
    parser.add_argument(
        "--save-local",
        dest="save_local",
        action="store_true",
        help="Write JSON files to data/batch",
    )
    parser.add_argument(
        "--probe",
        dest="probe",
        action="store_true",
        help="On dry-run, GET Motus to report would_insert/update",
    )
    return parser.parse_args()


def parse_states(states_arg: Optional[str]) -> Optional[Set[str]]:
    """Parse states argument to set."""
    if not states_arg:
        return None
    return {s.strip().upper() for s in states_arg.split(",") if s.strip()}


def get_eligible_job_codes() -> Set[str]:
    """Get eligible job codes from environment."""
    job_ids_env = os.getenv("JOB_IDS", "").strip()
    if not job_ids_env:
        raise SystemExit(
            "Error: JOB_IDS environment variable is required "
            "(comma-separated list, e.g., JOB_IDS=1103,4165,4166)"
        )
    return {code.strip() for code in job_ids_env.split(",") if code.strip()}


def filter_by_eligible_job_codes(
    items: list,
    eligible_job_codes: Set[str],
    debug: bool = False,
) -> list:
    """Filter employees by eligible job codes."""
    eligible = []
    for item in items:
        job_code = str(item.get("primaryJobCode", "") or "").strip()
        job_code_normalized = job_code.lstrip("0")
        if job_code in eligible_job_codes or job_code_normalized in eligible_job_codes:
            eligible.append(item)
        elif debug:
            print(
                f"[DEBUG] Skipping employee {item.get('employeeNumber')} - "
                f"ineligible job code: {job_code}"
            )
    return eligible


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
    if args.probe:
        os.environ["PROBE"] = "1"

    # Load settings
    batch_settings = BatchSettings.from_env()

    # Override from CLI
    if args.company_id:
        batch_settings.company_id = args.company_id
    if args.states:
        batch_settings.states_filter = args.states

    # Validate
    if not batch_settings.company_id:
        raise SystemExit(
            "Error: --company-id argument or COMPANY_ID environment variable is required"
        )

    states_filter = parse_states(batch_settings.states_filter)
    debug = os.getenv("DEBUG", "0") == "1"

    # Print config
    has_jwt = bool(os.getenv("MOTUS_JWT"))
    print(
        f"[CFG] companyID={batch_settings.company_id} | "
        f"states={batch_settings.states_filter or 'ALL'} | "
        f"workers={batch_settings.workers} | "
        f"dry_run={batch_settings.dry_run} | "
        f"probe={batch_settings.probe} | "
        f"save_local={batch_settings.save_local} | "
        f"MOTUS_JWT={'SET' if has_jwt else 'MISSING'}"
    )

    # Get eligible job codes
    eligible_job_codes = get_eligible_job_codes()
    print(f"[CFG] JOB_IDS (from env): {','.join(sorted(eligible_job_codes))}")

    # Initialize clients
    ukg_client = UKGClient(debug=debug)
    motus_client = MotusClient(debug=debug)

    # Fetch employees from UKG
    employees = ukg_client.get_all_employment_details_by_company(
        batch_settings.company_id
    )
    print(f"[INFO] Total employees from UKG: {len(employees)}")

    # Filter by job codes
    employees = filter_by_eligible_job_codes(employees, eligible_job_codes, debug)
    print(f"[INFO] Eligible employees (by job code): {len(employees)}")

    # Sync
    sync_service = DriverSyncService(ukg_client, motus_client, debug=debug)
    sync_service.sync_batch(employees, batch_settings, states_filter)


if __name__ == "__main__":
    main()
