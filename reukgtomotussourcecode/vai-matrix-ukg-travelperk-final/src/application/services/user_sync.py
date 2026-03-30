"""User synchronization service."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ...domain.models import TravelPerkUser
from ...domain.exceptions import EmployeeNotFoundError, UserValidationError
from ...infrastructure.adapters.ukg import UKGClient
from ...infrastructure.adapters.travelperk import TravelPerkClient
from ...infrastructure.config.settings import BatchSettings
from .user_builder import UserBuilderService


class UserSyncService:
    """Service for synchronizing users from UKG to TravelPerk."""

    def __init__(
        self,
        ukg_client: UKGClient,
        travelperk_client: TravelPerkClient,
        debug: bool = False,
    ):
        """Initialize user sync service.

        Args:
            ukg_client: UKG API client
            travelperk_client: TravelPerk API client
            debug: Enable debug logging
        """
        self.ukg_client = ukg_client
        self.travelperk_client = travelperk_client
        self.debug = debug
        self.user_builder = UserBuilderService(ukg_client, debug)
        self._person_cache: Dict[str, str] = {}

    def _fetch_person_state(
        self,
        employee_id: str,
        max_retries: int = 5,
    ) -> str:
        """Fetch person's state with caching and retry logic."""
        if employee_id in self._person_cache:
            return self._person_cache[employee_id]

        delay = 0.2
        for attempt in range(1, max_retries + 1):
            try:
                person = self.ukg_client.get_person_details(employee_id)
                state = (person.get("addressState") or "").strip().upper()
                self._person_cache[employee_id] = state
                return state
            except Exception:
                if attempt < max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, 3.2)
                else:
                    self._person_cache[employee_id] = ""
                    return ""

    def _build_supervisor_mapping(
        self,
        supervisor_details: List[Dict[str, Any]],
    ) -> Dict[str, Optional[str]]:
        """Build employeeNumber -> supervisorEmployeeNumber mapping."""
        mapping: Dict[str, Optional[str]] = {}

        for detail in supervisor_details:
            emp_number = str(detail.get("employeeNumber", "")).strip()
            if not emp_number:
                continue

            supervisor_emp_number = detail.get("supervisorEmployeeNumber")
            if supervisor_emp_number:
                mapping[emp_number] = str(supervisor_emp_number).strip()
            else:
                mapping[emp_number] = None

        return mapping

    def _process_employee(
        self,
        employee: Dict[str, Any],
        states_filter: Optional[Set[str]],
        out_path: Path,
        supervisor_id: Optional[str],
        settings: BatchSettings,
    ) -> Tuple[str, str, str, Optional[str]]:
        """Process a single employee.

        Returns:
            Tuple of (employee_number, state, status, travelperk_id)
        """
        emp_number = (employee.get("employeeNumber") or "").strip()
        emp_id = (employee.get("employeeID") or "").strip()

        if not emp_number or not emp_id:
            return ("", "", "skipped", None)

        state = self._fetch_person_state(emp_id)

        # Filter by state
        if states_filter and state not in states_filter:
            if self.debug:
                print(f"[DEBUG] skip emp={emp_number} state={state}")
            return (emp_number, state, "skipped", None)

        try:
            # Build user
            user = self.user_builder.build_user(emp_number, settings.company_id)

            # Set manager if provided
            if supervisor_id:
                user.manager_id = supervisor_id

            # Save locally if requested
            if settings.save_local:
                file_path = out_path / f"travelperk_user_{emp_number}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(user.to_api_payload(), f, indent=2)

            # Upsert to TravelPerk
            if settings.dry_run:
                return (emp_number, state, "dry_run", None)

            result = self.travelperk_client.upsert_user(
                user,
                include_manager=bool(supervisor_id),
            )
            travelperk_id = result.get("id")

            return (emp_number, state, "saved", travelperk_id)

        except (EmployeeNotFoundError, UserValidationError) as error:
            print(f"[WARN] employeeNumber={emp_number} skipped: {error}")
            return (emp_number, state, "skipped", None)
        except Exception as error:
            print(f"[WARN] employeeNumber={emp_number} error: {repr(error)}")
            return (emp_number, state, "error", None)

    def sync_batch(
        self,
        employees: List[Dict[str, Any]],
        settings: BatchSettings,
        states_filter: Optional[Set[str]] = None,
        pre_inserted_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Synchronize batch of employees to TravelPerk.

        Args:
            employees: List of employee employment details
            settings: Batch processing settings
            states_filter: Optional set of states to filter by
            pre_inserted_mapping: Optional mapping of pre-inserted supervisor IDs

        Returns:
            Mapping of employeeNumber -> TravelPerk ID
        """
        out_path = Path(settings.out_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        # Get supervisor mapping
        print("[INFO] Fetching supervisor details from UKG...")
        supervisor_details = self.ukg_client.get_all_supervisor_details()
        supervisor_mapping = self._build_supervisor_mapping(supervisor_details)

        # Split by supervisor status
        users_without_supervisor = [
            emp for emp, sup in supervisor_mapping.items() if sup is None
        ]
        users_with_supervisor = [
            emp for emp, sup in supervisor_mapping.items() if sup is not None
        ]

        print(f"[INFO] Phase 1: {len(users_without_supervisor)} users without supervisor")
        print(f"[INFO] Phase 2: {len(users_with_supervisor)} users with supervisor")

        # Initialize mapping with pre-inserted supervisors
        employee_to_travelperk_id: Dict[str, str] = {}
        if pre_inserted_mapping:
            employee_to_travelperk_id.update(pre_inserted_mapping)
            print(f"[INFO] Using {len(pre_inserted_mapping)} pre-inserted supervisor(s)")

        # Filter employees by phase
        items_phase1 = [
            emp for emp in employees
            if str(emp.get("employeeNumber", "")).strip() in users_without_supervisor
        ]
        items_phase2 = [
            emp for emp in employees
            if str(emp.get("employeeNumber", "")).strip() in users_with_supervisor
        ]

        # Apply limit if specified
        if settings.limit > 0:
            print(f"[INFO] LIMIT mode: processing only {settings.limit} users per phase")
            items_phase1 = items_phase1[:settings.limit]
            items_phase2 = items_phase2[:settings.limit]

        # Phase 1: Insert users without supervisor
        print("[INFO] === PHASE 1: Inserting users without supervisor ===")
        phase1_results = self._process_phase(
            items_phase1,
            states_filter,
            out_path,
            settings,
            supervisor_mapping=None,  # No supervisors in phase 1
            employee_to_travelperk_id=employee_to_travelperk_id,
        )
        employee_to_travelperk_id.update(phase1_results)

        # Phase 2: Insert users with supervisor
        print("[INFO] === PHASE 2: Inserting users with supervisor ===")
        phase2_results = self._process_phase(
            items_phase2,
            states_filter,
            out_path,
            settings,
            supervisor_mapping=supervisor_mapping,
            employee_to_travelperk_id=employee_to_travelperk_id,
        )
        employee_to_travelperk_id.update(phase2_results)

        print(f"[INFO] === FINAL === Mapped {len(employee_to_travelperk_id)} employees")

        return employee_to_travelperk_id

    def _process_phase(
        self,
        employees: List[Dict[str, Any]],
        states_filter: Optional[Set[str]],
        out_path: Path,
        settings: BatchSettings,
        supervisor_mapping: Optional[Dict[str, Optional[str]]],
        employee_to_travelperk_id: Dict[str, str],
    ) -> Dict[str, str]:
        """Process a single phase of employees."""
        total = len(employees)
        saved = skipped = errors = 0
        printed = 0
        result_mapping: Dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=settings.workers) as executor:
            futures = []

            for emp in employees:
                emp_number = str(emp.get("employeeNumber", "")).strip()
                supervisor_id = None

                if supervisor_mapping:
                    supervisor_emp_number = supervisor_mapping.get(emp_number)
                    if supervisor_emp_number:
                        supervisor_id = employee_to_travelperk_id.get(supervisor_emp_number)

                        # Try to find supervisor in TravelPerk if not in local mapping
                        if not supervisor_id:
                            if self.debug:
                                print(f"[DEBUG] Supervisor {supervisor_emp_number} not in mapping")
                            sup_user = self.travelperk_client.get_user_by_external_id(
                                supervisor_emp_number
                            )
                            if sup_user:
                                supervisor_id = sup_user.get("id")
                                if supervisor_id:
                                    employee_to_travelperk_id[supervisor_emp_number] = supervisor_id
                                    print(f"[INFO] Found supervisor {supervisor_emp_number}: id={supervisor_id}")

                futures.append(
                    executor.submit(
                        self._process_employee,
                        emp,
                        states_filter,
                        out_path,
                        supervisor_id,
                        settings,
                    )
                )

            for future in as_completed(futures):
                emp_number, state, status, travelperk_id = future.result()

                if status in ("saved", "dry_run"):
                    saved += 1
                    if travelperk_id:
                        result_mapping[emp_number] = travelperk_id
                elif status == "error":
                    errors += 1
                else:
                    skipped += 1

                printed += 1
                if printed % 100 == 0 or printed == total:
                    print(
                        f"[INFO] Progress: {printed}/{total} | "
                        f"saved={saved} skipped={skipped} errors={errors}"
                    )

        print(f"[INFO] Phase done: saved={saved} skipped={skipped} errors={errors}")
        return result_mapping

    def insert_supervisors(
        self,
        employee_numbers: List[str],
        settings: BatchSettings,
    ) -> Dict[str, str]:
        """Pre-insert supervisors before batch processing.

        Args:
            employee_numbers: List of supervisor employee numbers
            settings: Batch settings

        Returns:
            Mapping of employeeNumber -> TravelPerk ID
        """
        out_path = Path(settings.out_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] === PRE-INSERT: Inserting {len(employee_numbers)} supervisor(s) ===")

        mapping: Dict[str, str] = {}

        for emp_number in employee_numbers:
            emp_number = emp_number.strip()
            if not emp_number:
                continue

            try:
                print(f"[INFO] Inserting supervisor: employeeNumber={emp_number}")
                user = self.user_builder.build_user(emp_number, settings.company_id)

                if settings.save_local:
                    file_path = out_path / f"travelperk_user_{emp_number}.json"
                    with file_path.open("w", encoding="utf-8") as f:
                        json.dump(user.to_api_payload(), f, indent=2)

                if settings.dry_run:
                    print(f"[INFO] Supervisor dry-run: {emp_number}")
                    continue

                result = self.travelperk_client.upsert_user(user, include_manager=False)
                travelperk_id = result.get("id")

                if travelperk_id:
                    mapping[emp_number] = travelperk_id
                    print(f"[INFO] Supervisor inserted: {emp_number} -> {travelperk_id}")

            except Exception as error:
                print(f"[ERROR] Supervisor {emp_number} error: {repr(error)}")

        print(f"[INFO] Pre-insert done: {len(mapping)} supervisor(s) inserted")
        return mapping
