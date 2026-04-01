"""
Driver sync service.

Orchestrates synchronization of drivers between UKG and Motus.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from common.correlation import correlation_context, get_correlation_id
from src.domain.exceptions import EmployeeNotFoundError, ProgramNotFoundError
from src.domain.models import MotusDriver
from src.infrastructure.adapters.motus import MotusClient
from src.infrastructure.adapters.ukg import UKGClient
from src.infrastructure.config.settings import BatchSettings

from .driver_builder import DriverBuilderService

logger = logging.getLogger(__name__)


class DriverSyncService:
    """Service for synchronizing drivers between UKG and Motus."""

    def __init__(
        self,
        ukg_client: UKGClient,
        motus_client: MotusClient,
        debug: bool = False,
    ):
        """
        Initialize driver sync service.

        Args:
            ukg_client: UKG API client
            motus_client: Motus API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.motus_client = motus_client
        self.builder = DriverBuilderService(ukg_client, debug=debug)
        self.debug = debug

    def _log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            logger.debug(message)

    def get_person_state(
        self,
        employee_id: str,
        cache: Dict[str, str],
        max_retries: int = 5,
    ) -> str:
        """
        Get person's state with caching and retry.

        Args:
            employee_id: Employee ID
            cache: State cache
            max_retries: Maximum retry attempts

        Returns:
            State code or empty string
        """
        if employee_id in cache:
            return cache[employee_id]

        delay = 0.2
        for attempt in range(1, max_retries + 1):
            try:
                person = self.ukg_client.get_person_details(employee_id)
                state = (person.get("addressState") or "").strip().upper()
                cache[employee_id] = state
                return state
            except Exception:
                if attempt < max_retries:
                    import time
                    time.sleep(delay)
                    delay = min(delay * 2, 3.2)
                else:
                    cache[employee_id] = ""
                    return ""

    def sync_employee(
        self,
        employee_record: Dict[str, Any],
        company_id: str,
        states_filter: Optional[Set[str]],
        state_cache: Dict[str, str],
        dry_run: bool = False,
        probe: bool = False,
        out_dir: Optional[Path] = None,
    ) -> Tuple[str, str, str]:
        """
        Sync a single employee to Motus.

        Args:
            employee_record: Employee record from UKG
            company_id: Company ID
            states_filter: Optional set of states to filter by
            state_cache: Cache for state lookups
            dry_run: If True, don't make changes
            probe: If True, check existence in Motus
            out_dir: Optional output directory for JSON files

        Returns:
            Tuple of (employee_number, state, status)
        """
        employee_number = (employee_record.get("employeeNumber") or "").strip()
        employee_id = (employee_record.get("employeeID") or "").strip()

        if not employee_number or not employee_id:
            return ("", "", "skipped")

        # Create correlation ID context for this employee
        with correlation_context(prefix=f"emp-{employee_number}"):
            correlation_id = get_correlation_id()

            # Get state and filter
            state = self.get_person_state(employee_id, state_cache)

            if states_filter and state not in states_filter:
                self._log(f"skip emp={employee_number} state={state}")
                logger.info(
                    f"[{correlation_id}] SYNC SKIPPED | "
                    f"Employee: {employee_number} | State: {state} (filtered)"
                )
                return (employee_number, state, "skipped")

            logger.info(
                f"[{correlation_id}] SYNC START | "
                f"Employee: {employee_number} | State: {state}"
            )

            try:
                # Build driver
                driver = self.builder.build_driver(employee_number, company_id)

                # Upsert driver
                result = self.motus_client.upsert_driver(
                    driver, dry_run=dry_run, probe=probe
                )

                # Save to file if requested
                if out_dir:
                    file_path = out_dir / f"motus_driver_{employee_number}.json"
                    with file_path.open("w", encoding="utf-8") as f:
                        json.dump([driver.to_api_payload()], f, indent=2)

                action = result.get("action", "unknown")

                if dry_run:
                    logger.info(
                        f"[{correlation_id}] SYNC COMPLETE (DRY_RUN) | "
                        f"Employee: {employee_number}"
                    )
                    return (employee_number, state, "dry_run")

                logger.info(
                    f"[{correlation_id}] SYNC COMPLETE | "
                    f"Employee: {employee_number} | Action: {action}"
                )
                return (employee_number, state, action)

            except (EmployeeNotFoundError, ProgramNotFoundError) as e:
                logger.warning(
                    f"[{correlation_id}] SYNC SKIPPED | "
                    f"Employee: {employee_number} | Reason: {e}"
                )
                return (employee_number, state, "skipped")
            except Exception as e:
                logger.error(
                    f"[{correlation_id}] SYNC ERROR | "
                    f"Employee: {employee_number} | Error: {repr(e)}"
                )
                return (employee_number, state, "error")

    def sync_batch(
        self,
        employees: List[Dict[str, Any]],
        settings: BatchSettings,
        states_filter: Optional[Set[str]] = None,
    ) -> Dict[str, int]:
        """
        Sync a batch of employees to Motus.

        Args:
            employees: List of employee records
            settings: Batch settings
            states_filter: Optional set of states to filter by

        Returns:
            Statistics dict with counts
        """
        # Create correlation context for the entire batch
        with correlation_context(prefix="batch"):
            batch_correlation_id = get_correlation_id()

            out_dir = Path(settings.out_dir).resolve() if settings.save_local else None
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)

            state_cache: Dict[str, str] = {}
            total = len(employees)
            stats = {"saved": 0, "skipped": 0, "errors": 0, "total": total}
            processed = 0

            logger.info(
                f"[{batch_correlation_id}] BATCH START | "
                f"Total employees: {total} | Company: {settings.company_id}"
            )

            with ThreadPoolExecutor(max_workers=settings.workers) as executor:
                futures = [
                    executor.submit(
                        self.sync_employee,
                        emp,
                        settings.company_id,
                        states_filter,
                        state_cache,
                        settings.dry_run,
                        settings.probe,
                        out_dir,
                    )
                    for emp in employees
                ]

                for future in as_completed(futures):
                    employee_number, state, status = future.result()

                    if status in ("saved", "insert", "update"):
                        stats["saved"] += 1
                    elif status == "error":
                        stats["errors"] += 1
                    else:
                        stats["skipped"] += 1

                    processed += 1
                    if processed % 100 == 0 or processed == total:
                        logger.info(
                            f"[{batch_correlation_id}] BATCH PROGRESS | "
                            f"{processed}/{total} | "
                            f"saved={stats['saved']} skipped={stats['skipped']} "
                            f"errors={stats['errors']}"
                        )

            logger.info(
                f"[{batch_correlation_id}] BATCH COMPLETE | "
                f"total={total} | saved={stats['saved']} | "
                f"skipped={stats['skipped']} | errors={stats['errors']}"
            )

            return stats
