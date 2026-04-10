"""
Batch runner CLI.

Entry point for running Motus batch synchronization.
"""

import argparse
import logging
import os
from typing import Optional, Set

from common.correlation import configure_logging
from src.application.services import DriverSyncService
from src.infrastructure.adapters.motus import MotusClient
from src.infrastructure.adapters.ukg import UKGClient
from src.infrastructure.config.settings import BatchSettings, MotusSettings, UKGSettings

# Configure logging at module startup
configure_logging()
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run Motus batch synchronization")
    parser.add_argument(
        "--company-id",
        dest="company_id",
        help="UKG company ID (e.g., J9A6Y)",
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


# Default JOB_IDS if not set in environment
DEFAULT_JOB_IDS = "1103,4165,4166,1102,1106,4197,4196,2817,4121,2157"

# Hardcoded employee filter for testing (set to None to process all employees)
TEST_EMPLOYEE_NUMBERS: Optional[Set[str]] = {
    "012342", "021295", "023371", "024122", "024126", "025330", "025341", "025702",
    "026979", "027576", "027668", "027850", "028044", "028123", "028140", "028232",
    "028240", "028241", "028244", "028248", "028251", "028252",
}


def get_eligible_job_codes() -> Set[str]:
    """Get eligible job codes from environment or use default."""
    job_ids_env = os.getenv("JOB_IDS", "").strip()

    if not job_ids_env:
        logger.info(
            f"JOB_IDS not set in environment, using default: {DEFAULT_JOB_IDS}"
        )
        job_ids_env = DEFAULT_JOB_IDS
    else:
        logger.info(f"JOB_IDS loaded from environment: {job_ids_env}")

    job_codes = {code.strip() for code in job_ids_env.split(",") if code.strip()}
    logger.info(f"Eligible job codes ({len(job_codes)}): {sorted(job_codes)}")
    return job_codes


def filter_by_eligible_job_codes(
    items: list,
    eligible_job_codes: Set[str],
) -> list:
    """Filter employees by eligible job codes."""
    eligible = []
    for item in items:
        job_code = str(item.get("primaryJobCode", "") or "").strip()
        job_code_normalized = job_code.lstrip("0")
        if job_code in eligible_job_codes or job_code_normalized in eligible_job_codes:
            eligible.append(item)
    return eligible


def filter_by_employee_numbers(
    items: list,
    employee_numbers: Optional[Set[str]],
) -> list:
    """Filter employees by specific employee numbers (for testing)."""
    if not employee_numbers:
        return items  # No filter, return all
    return [
        item for item in items
        if (item.get("employeeNumber") or "").strip() in employee_numbers
    ]


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

    # Validate
    if not batch_settings.company_id:
        raise SystemExit(
            "Error: --company-id argument or COMPANY_ID environment variable is required"
        )

    # Validate API credentials at startup (fail-fast if missing or invalid)
    logger.info("Validating API credentials...")

    ukg_settings = UKGSettings.from_env()
    ukg_settings.validate_or_exit()

    motus_settings = MotusSettings.from_env()

    # Token will be generated lazily by MotusClient on first API call
    # This allows us to log credentials just before the actual Motus call
    if not motus_settings.jwt:
        logger.info("MOTUS_JWT not set. Token will be generated on first Motus API call.")
    else:
        motus_settings.validate_or_exit()
        logger.info("Motus JWT token validated successfully.")

    debug = os.getenv("DEBUG", "0") == "1"

    # Log config
    has_jwt = True  # Already validated above
    logger.info(
        f"Config: companyID={batch_settings.company_id} | "
        f"workers={batch_settings.workers} | "
        f"dry_run={batch_settings.dry_run} | "
        f"probe={batch_settings.probe} | "
        f"save_local={batch_settings.save_local} | "
        f"MOTUS_JWT={'SET' if has_jwt else 'MISSING'}"
    )

    # Get eligible job codes
    eligible_job_codes = get_eligible_job_codes()
    logger.info(f"JOB_IDS (from env): {','.join(sorted(eligible_job_codes))}")

    # Initialize clients with validated settings
    ukg_client = UKGClient(settings=ukg_settings, debug=debug)
    motus_client = MotusClient(settings=motus_settings, debug=debug)

    # Fetch employees from UKG
    employees = ukg_client.get_all_employment_details_by_company(
        batch_settings.company_id
    )

    # Filter by job codes
    employees = filter_by_eligible_job_codes(employees, eligible_job_codes)
    logger.info(f"Eligible employees (by job code): {len(employees)}")

    # Filter by specific employee numbers (for testing)
    if TEST_EMPLOYEE_NUMBERS:
        employees = filter_by_employee_numbers(employees, TEST_EMPLOYEE_NUMBERS)
        logger.info(f"TEST MODE: Filtered to {len(employees)} specific employees")

    # Sync
    sync_service = DriverSyncService(ukg_client, motus_client, debug=debug)
    sync_service.sync_batch(employees, batch_settings)


if __name__ == "__main__":
    main()
