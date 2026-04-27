"""
User synchronization service.

Orchestrates the two-phase sync process from UKG to TravelPerk.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ...domain.models import TravelPerkUser
from ...domain.exceptions import EmployeeNotFoundError, UserValidationError
from ...infrastructure.adapters.ukg import UKGClient
from ...infrastructure.adapters.travelperk import TravelPerkClient
from ...infrastructure.config.settings import BatchSettings
from .user_builder import UserBuilderService
from .supervisor_mapping import SupervisorMappingService, SupervisorInfo
from .state_filter import StateFilterService
from .batch_processor import BatchProcessor, BatchResult


logger = logging.getLogger(__name__)


class UserSyncService:
    """Service for synchronizing users from UKG to TravelPerk."""

    def __init__(
        self,
        ukg_client: UKGClient,
        travelperk_client: TravelPerkClient,
        debug: bool = False,
    ):
        """
        Initialize user sync service.

        Args:
            ukg_client: UKG API client
            travelperk_client: TravelPerk API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.travelperk_client = travelperk_client
        self.debug = debug

        # Initialize sub-services
        self.user_builder = UserBuilderService(ukg_client, debug)
        self.supervisor_service = SupervisorMappingService(
            ukg_client, travelperk_client, debug
        )
        self.state_filter = StateFilterService(ukg_client, debug)

    def _process_employee(
        self,
        employee: Dict[str, Any],
        states_filter: Optional[Set[str]],
        out_path: Path,
        supervisor_id: Optional[str],
        supervisor_name: Optional[str],
        supervisor_email: Optional[str],
        settings: BatchSettings,
    ) -> Tuple[str, str, str, Optional[str]]:
        """
        Process a single employee.

        Returns:
            Tuple of (employee_number, state, status, travelperk_id)
        """
        emp_number = (employee.get("employeeNumber") or "").strip()
        emp_id = (employee.get("employeeID") or "").strip()

        if not emp_number or not emp_id:
            logger.debug(f"Skipping employee with missing number or ID")
            return ("", "", "skipped", None)

        try:
            state = self.state_filter.fetch_person_state(emp_id)
        except Exception as error:
            logger.error(
                f"Employee {emp_number} failed fetching state: {type(error).__name__}: {error}"
            )
            return (emp_number, "", "error", None)

        # Filter by state
        if states_filter and state not in states_filter:
            if self.debug:
                logger.debug(f"Employee {emp_number} skipped: state={state} not in filter")
            return (emp_number, state, "skipped", None)

        try:
            # Build user
            if self.debug:
                logger.debug(f"Building user payload for employee {emp_number}")
            user = self.user_builder.build_user(emp_number, settings.company_id)

            # Set manager if provided
            if supervisor_id:
                user.manager_id = supervisor_id
                if supervisor_name:
                    user.manager_display_name = supervisor_name
                if supervisor_email:
                    user.line_manager_email = supervisor_email
                if self.debug:
                    logger.debug(
                        f"Employee {emp_number}: assigned manager ID {supervisor_id}, "
                        f"displayName={supervisor_name}, lineManagerEmail={supervisor_email}"
                    )

            # Save locally if requested
            if settings.save_local:
                file_path = out_path / f"travelperk_user_{emp_number}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(user.to_api_payload(), f, indent=2)
                if self.debug:
                    logger.debug(f"Employee {emp_number}: saved payload to {file_path}")

            # Upsert to TravelPerk
            if settings.dry_run:
                if self.debug:
                    logger.debug(f"Employee {emp_number}: dry-run mode, skipping API call")
                return (emp_number, state, "dry_run", None)

            result = self.travelperk_client.upsert_user(
                user,
                include_manager=bool(supervisor_id),
            )
            travelperk_id = result.get("id")
            action = result.get("action", "unknown")

            if self.debug:
                logger.debug(
                    f"Employee {emp_number}: {action} -> TravelPerk ID {travelperk_id}"
                )

            return (emp_number, state, "saved", travelperk_id)

        except (EmployeeNotFoundError, UserValidationError) as error:
            logger.warning(
                f"Employee {emp_number} skipped due to validation: {error}"
            )
            return (emp_number, state, "skipped", None)
        except Exception as error:
            logger.error(
                f"Employee {emp_number} failed with error: {type(error).__name__}: {error}"
            )
            return (emp_number, state, "error", None)

    def sync_batch(
        self,
        employees: List[Dict[str, Any]],
        settings: BatchSettings,
        states_filter: Optional[Set[str]] = None,
        pre_inserted_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Synchronize batch of employees to TravelPerk.

        Uses two-phase approach:
        1. Insert users without supervisors (build ID mapping)
        2. Insert users with supervisors (using ID mapping)

        Args:
            employees: List of employee employment details
            settings: Batch processing settings
            states_filter: Optional set of states to filter by
            pre_inserted_mapping: Optional mapping of pre-inserted supervisor IDs

        Returns:
            Mapping of employeeNumber -> TravelPerk ID
        """
        sync_start_time = time.time()

        out_path = Path(settings.out_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {out_path}")

        # Get supervisor mapping
        logger.info("Fetching supervisor mapping from UKG...")
        supervisor_fetch_start = time.time()
        supervisor_mapping = self.supervisor_service.fetch_supervisor_mapping()
        supervisor_fetch_elapsed = time.time() - supervisor_fetch_start
        logger.info(
            f"Supervisor mapping fetched: {len(supervisor_mapping)} relationships "
            f"in {supervisor_fetch_elapsed:.2f}s"
        )

        # Split by supervisor status
        users_without_supervisor, users_with_supervisor = (
            self.supervisor_service.split_by_supervisor_status(supervisor_mapping)
        )
        logger.info(
            f"Employee split: {len(users_without_supervisor)} without supervisor, "
            f"{len(users_with_supervisor)} with supervisor"
        )

        # Initialize mapping with pre-inserted supervisors
        employee_to_travelperk_id: Dict[str, str] = {}
        if pre_inserted_mapping:
            employee_to_travelperk_id.update(pre_inserted_mapping)
            logger.info(
                f"Using {len(pre_inserted_mapping)} pre-inserted supervisor(s)"
            )

        # Filter employees by phase
        items_phase1 = [
            emp
            for emp in employees
            if str(emp.get("employeeNumber", "")).strip() in users_without_supervisor
        ]
        items_phase2 = [
            emp
            for emp in employees
            if str(emp.get("employeeNumber", "")).strip() in users_with_supervisor
        ]

        # Apply limit if specified
        if settings.limit > 0:
            logger.info(f"LIMIT mode: processing only {settings.limit} users per phase")
            items_phase1 = items_phase1[: settings.limit]
            items_phase2 = items_phase2[: settings.limit]

        # Track phase results for summary
        phase1_stats = {"saved": 0, "skipped": 0, "errors": 0}
        phase2_stats = {"saved": 0, "skipped": 0, "errors": 0}

        # Phase 1: Insert users without supervisor
        logger.info("=" * 60)
        logger.info("PHASE 1: Inserting users WITHOUT supervisor")
        logger.info(f"  Total users to process: {len(items_phase1)}")
        logger.info(f"  Workers: {settings.workers}")
        logger.info("=" * 60)

        phase1_start = time.time()
        phase1_result = self._process_phase(
            items_phase1,
            states_filter,
            out_path,
            settings,
            supervisor_mapping=None,
            employee_to_travelperk_id=employee_to_travelperk_id,
        )
        phase1_elapsed = time.time() - phase1_start
        employee_to_travelperk_id.update(phase1_result)

        logger.info("-" * 60)
        logger.info(f"PHASE 1 COMPLETED in {phase1_elapsed:.2f}s")
        logger.info(f"  Users mapped: {len(phase1_result)}")
        logger.info(f"  Throughput: {len(items_phase1) / phase1_elapsed:.1f} users/sec" if phase1_elapsed > 0 else "  Throughput: N/A")
        logger.info("-" * 60)

        # Phase 2: Insert users with supervisor
        logger.info("=" * 60)
        logger.info("PHASE 2: Inserting users WITH supervisor")
        logger.info(f"  Total users to process: {len(items_phase2)}")
        logger.info(f"  Available supervisor mappings: {len(employee_to_travelperk_id)}")
        logger.info(f"  Workers: {settings.workers}")
        logger.info("=" * 60)

        phase2_start = time.time()
        phase2_result = self._process_phase(
            items_phase2,
            states_filter,
            out_path,
            settings,
            supervisor_mapping=supervisor_mapping,
            employee_to_travelperk_id=employee_to_travelperk_id,
        )
        phase2_elapsed = time.time() - phase2_start
        employee_to_travelperk_id.update(phase2_result)

        logger.info("-" * 60)
        logger.info(f"PHASE 2 COMPLETED in {phase2_elapsed:.2f}s")
        logger.info(f"  Users mapped: {len(phase2_result)}")
        logger.info(f"  Throughput: {len(items_phase2) / phase2_elapsed:.1f} users/sec" if phase2_elapsed > 0 else "  Throughput: N/A")
        logger.info("-" * 60)

        # Final summary
        total_elapsed = time.time() - sync_start_time
        total_processed = len(items_phase1) + len(items_phase2)

        logger.info("=" * 60)
        logger.info("SYNCHRONIZATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Total employees processed: {total_processed}")
        logger.info(f"  Phase 1 (without supervisor): {len(items_phase1)} -> {len(phase1_result)} mapped")
        logger.info(f"  Phase 2 (with supervisor): {len(items_phase2)} -> {len(phase2_result)} mapped")
        logger.info(f"  Total employees mapped: {len(employee_to_travelperk_id)}")
        logger.info(f"  Total sync duration: {total_elapsed:.2f}s")
        logger.info(f"  Overall throughput: {total_processed / total_elapsed:.1f} users/sec" if total_elapsed > 0 else "  Overall throughput: N/A")
        logger.info("=" * 60)

        return employee_to_travelperk_id

    def _process_phase(
        self,
        employees: List[Dict[str, Any]],
        states_filter: Optional[Set[str]],
        out_path: Path,
        settings: BatchSettings,
        supervisor_mapping: Optional[Dict[str, Optional[SupervisorInfo]]],
        employee_to_travelperk_id: Dict[str, str],
    ) -> Dict[str, str]:
        """Process a single phase of employees."""
        batch_processor = BatchProcessor(
            workers=settings.workers,
            progress_interval=100,
            debug=self.debug,
        )

        result_mapping: Dict[str, str] = {}

        def process_single(emp: Dict[str, Any]) -> Tuple[str, str, str, Optional[str]]:
            emp_number = str(emp.get("employeeNumber", "")).strip()
            supervisor_id = None
            supervisor_name = None
            supervisor_email = None

            if supervisor_mapping:
                supervisor_info = supervisor_mapping.get(emp_number)
                if supervisor_info:
                    # Extract supervisor details from SupervisorInfo
                    supervisor_name = supervisor_info.full_name
                    supervisor_email = supervisor_info.email

                    # Resolve supervisor's TravelPerk ID (may call TravelPerk API)
                    resolution_error = False
                    try:
                        supervisor_id = self.supervisor_service.resolve_supervisor_id(
                            supervisor_info.employee_number, employee_to_travelperk_id
                        )
                    except Exception as error:
                        logger.warning(
                            f"Employee {emp_number}: failed to resolve supervisor {supervisor_info.employee_number}: "
                            f"{type(error).__name__}: {error} - continuing without manager"
                        )
                        supervisor_id = None
                        resolution_error = True

                    if supervisor_id:
                        logger.info(
                            f"Employee {emp_number}: supervisor {supervisor_info.employee_number} "
                            f"({supervisor_name or 'N/A'}, {supervisor_email or 'N/A'}) "
                            f"resolved to TravelPerk ID {supervisor_id}"
                        )
                    elif not resolution_error:
                        # Only log if we didn't already log an error above
                        logger.warning(
                            f"Employee {emp_number}: supervisor {supervisor_info.employee_number} "
                            f"({supervisor_name or 'N/A'}) could NOT be resolved - manager will not be set"
                        )

            return self._process_employee(
                emp,
                states_filter,
                out_path,
                supervisor_id,
                supervisor_name,
                supervisor_email,
                settings,
            )

        phase_name = "Phase 1" if supervisor_mapping is None else "Phase 2"
        result = batch_processor.process_batch(
            employees, process_single, phase_name=phase_name
        )

        return result.id_mapping

    def insert_supervisors(
        self,
        employee_numbers: List[str],
        settings: BatchSettings,
    ) -> Dict[str, str]:
        """
        Pre-insert supervisors before batch processing.

        Args:
            employee_numbers: List of supervisor employee numbers
            settings: Batch settings

        Returns:
            Mapping of employeeNumber -> TravelPerk ID
        """
        out_path = Path(settings.out_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"=== PRE-INSERT: Inserting {len(employee_numbers)} supervisor(s) ===")

        mapping: Dict[str, str] = {}

        for emp_number in employee_numbers:
            emp_number = emp_number.strip()
            if not emp_number:
                continue

            try:
                logger.info(f"Inserting supervisor: employeeNumber={emp_number}")
                user = self.user_builder.build_user(emp_number, settings.company_id)

                if settings.save_local:
                    file_path = out_path / f"travelperk_user_{emp_number}.json"
                    with file_path.open("w", encoding="utf-8") as f:
                        json.dump(user.to_api_payload(), f, indent=2)

                if settings.dry_run:
                    logger.info(f"Supervisor dry-run: {emp_number}")
                    continue

                result = self.travelperk_client.upsert_user(user, include_manager=False)
                travelperk_id = result.get("id")

                if travelperk_id:
                    mapping[emp_number] = travelperk_id
                    logger.info(f"Supervisor inserted: {emp_number} -> {travelperk_id}")

            except Exception as error:
                logger.error(f"Supervisor {emp_number} error: {repr(error)}")

        logger.info(f"Pre-insert done: {len(mapping)} supervisor(s) inserted")
        return mapping
