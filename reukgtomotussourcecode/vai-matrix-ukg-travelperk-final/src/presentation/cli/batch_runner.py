"""Batch runner CLI for TravelPerk synchronization."""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, List

from common import (
    configure_logging,
    get_logger,
    RedactingFilter,
    correlation_context,
    generate_correlation_id,
)

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
    # Generate correlation ID for the entire batch job
    correlation_id = generate_correlation_id("tp-batch")
    job_start_time = time.time()
    job_start_datetime = datetime.now()

    try:
        with correlation_context(correlation_id):
            # Log job start
            logger.info("=" * 80)
            logger.info("TRAVELPERK BATCH SYNCHRONIZATION - JOB STARTED")
            logger.info("=" * 80)
            logger.info(f"Job ID: {correlation_id}")
            logger.info(f"Start Time: {job_start_datetime.isoformat()}")
            logger.info(f"Python Version: {sys.version.split()[0]}")
            logger.info("-" * 80)

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
                logger.error("Missing required company ID")
                raise SystemExit(
                    "Error: --company-id argument or COMPANY_ID environment variable is required"
                )

            states_filter = parse_states(batch_settings.states_filter)
            debug = os.getenv("DEBUG", "0") == "1"

            # Log configuration
            has_api_key = bool(os.getenv("TRAVELPERK_API_KEY"))
            has_ukg_key = bool(os.getenv("UKG_CUSTOMER_API_KEY"))
            type_codes_str = ",".join(batch_settings.employee_type_codes or []) or "ALL"

            logger.info("CONFIGURATION:")
            logger.info(f"  Company ID: {batch_settings.company_id}")
            logger.info(f"  States Filter: {batch_settings.states_filter or 'ALL'}")
            logger.info(f"  Employee Type Codes: {type_codes_str}")
            logger.info(f"  Workers: {batch_settings.workers}")
            logger.info(f"  Dry Run: {batch_settings.dry_run}")
            logger.info(f"  Save Local: {batch_settings.save_local}")
            logger.info(f"  Limit: {batch_settings.limit or 'None'}")
            logger.info(f"  Output Directory: {batch_settings.out_dir}")
            logger.info(f"  UKG_CUSTOMER_API_KEY: {'SET' if has_ukg_key else 'MISSING'}")
            logger.info(f"  TRAVELPERK_API_KEY: {'SET' if has_api_key else 'MISSING'}")
            logger.info("-" * 80)

            # Initialize clients
            logger.info("Initializing API clients...")
            ukg_client = UKGClient(debug=debug)
            travelperk_client = TravelPerkClient(debug=debug)
            logger.info("API clients initialized successfully")

            # Initialize service
            sync_service = UserSyncService(ukg_client, travelperk_client, debug=debug)

            # Pre-insert supervisors if specified
            pre_inserted_mapping = {}
            if batch_settings.insert_supervisors:
                logger.info("-" * 80)
                logger.info(f"PRE-INSERT SUPERVISORS: {len(batch_settings.insert_supervisors)} supervisor(s) to insert")
                pre_insert_start = time.time()
                pre_inserted_mapping = sync_service.insert_supervisors(
                    batch_settings.insert_supervisors,
                    batch_settings,
                )
                pre_insert_elapsed = time.time() - pre_insert_start
                logger.info(f"Pre-insert completed: {len(pre_inserted_mapping)} supervisor(s) in {pre_insert_elapsed:.2f}s")

            # Fetch employees from UKG
            logger.info("-" * 80)
            logger.info("FETCHING EMPLOYEES FROM UKG...")
            fetch_start = time.time()
            employees = ukg_client.get_all_employment_details_by_company(
                batch_settings.company_id,
                employee_type_codes=batch_settings.employee_type_codes,
            )
            fetch_elapsed = time.time() - fetch_start
            logger.info(f"UKG fetch completed: {len(employees)} employees in {fetch_elapsed:.2f}s")

            # Sync
            logger.info("-" * 80)
            logger.info("STARTING TWO-PHASE SYNCHRONIZATION...")
            sync_start = time.time()
            mapping = sync_service.sync_batch(
                employees,
                batch_settings,
                states_filter=states_filter,
                pre_inserted_mapping=pre_inserted_mapping,
            )
            sync_elapsed = time.time() - sync_start
            logger.info(f"Synchronization completed in {sync_elapsed:.2f}s")

            # Save mapping
            if mapping:
                out_path = Path(batch_settings.out_dir).resolve()
                mapping_file = out_path / "employee_to_travelperk_id_mapping.json"
                with mapping_file.open("w", encoding="utf-8") as f:
                    json.dump(mapping, f, indent=2)
                logger.info(f"Saved mapping to {mapping_file}")

            # Job completion summary
            job_end_time = time.time()
            job_duration = job_end_time - job_start_time
            job_end_datetime = datetime.now()

            logger.info("=" * 80)
            logger.info("TRAVELPERK BATCH SYNCHRONIZATION - JOB COMPLETED")
            logger.info("=" * 80)
            logger.info(f"Job ID: {correlation_id}")
            logger.info(f"Start Time: {job_start_datetime.isoformat()}")
            logger.info(f"End Time: {job_end_datetime.isoformat()}")
            logger.info(f"Total Duration: {job_duration:.2f}s ({job_duration/60:.2f}m)")
            logger.info("-" * 80)
            logger.info("SUMMARY:")
            logger.info(f"  Employees Fetched from UKG: {len(employees)}")
            logger.info(f"  Employees Mapped to TravelPerk: {len(mapping)}")
            logger.info(f"  Pre-inserted Supervisors: {len(pre_inserted_mapping)}")
            if batch_settings.dry_run:
                logger.info("  Mode: DRY RUN (no changes made to TravelPerk)")
            logger.info("=" * 80)

    except SystemExit:
        # Re-raise SystemExit without additional logging (already handled)
        raise
    except Exception as e:
        # Log job failure with full context
        job_duration = time.time() - job_start_time
        job_end_datetime = datetime.now()

        logger.error("=" * 80)
        logger.error("TRAVELPERK BATCH SYNCHRONIZATION - JOB FAILED")
        logger.error("=" * 80)
        logger.error(f"Job ID: {correlation_id}")
        logger.error(f"Start Time: {job_start_datetime.isoformat()}")
        logger.error(f"Failure Time: {job_end_datetime.isoformat()}")
        logger.error(f"Duration before failure: {job_duration:.2f}s")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {e}")
        logger.error("-" * 80)
        logger.exception("Stack trace:")
        logger.error("=" * 80)

        raise SystemExit(1)


if __name__ == "__main__":
    main()
