import os, json, importlib.util, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def parse_cli():
    p = argparse.ArgumentParser(description="Run TravelPerk batch")
    p.add_argument("--company-id", dest="company_id", help="UKG companyID (e.g., J9A6Y)")
    p.add_argument("--states", dest="states", help="Comma-separated US states (e.g., FL,MS,NJ)")
    p.add_argument("--workers", dest="workers", type=int, help="Thread pool size")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="Validate but do not POST/PUT to TravelPerk")
    p.add_argument("--save-local", dest="save_local", action="store_true", help="Always write JSON files to data/batch")
    p.add_argument("--limit", dest="limit", type=int, help="Limit number of users to process (for testing, e.g., --limit 1 or --limit 10)")
    p.add_argument("--insert-supervisor", dest="insert_supervisor", help="Insert supervisor(s) by employeeNumber before processing batch. Comma-separated list (e.g., 004295,009299)")
    p.add_argument("--employee-type-codes", dest="employee_type_codes", help="Filter by employeeTypeCode(s). Comma-separated list (e.g., FTC,HRC,TMC). If not specified, processes all types.")
    return p.parse_args()

HERE = Path(__file__).resolve().parent
BUILDER_FILE = HERE / "build-travelperk-user.py"
UPSERT_FILE = HERE / "upsert-travelperk-user.py"

def load_builder():
    if not BUILDER_FILE.exists():
        raise SystemExit(f"Builder file not found: {BUILDER_FILE}")
    spec = importlib.util.spec_from_file_location("builder", str(BUILDER_FILE))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

def load_upserter():
    if not UPSERT_FILE.exists():
        raise SystemExit(f"Upserter file not found: {UPSERT_FILE}")
    spec = importlib.util.spec_from_file_location("upserter", str(UPSERT_FILE))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

builder = load_builder()
upserter = load_upserter()
get_data = builder.get_data
DEBUG = getattr(builder, "DEBUG", False)

def _normalize_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", []) if isinstance(data.get("items"), list) else [data]
    return []

def get_employee_employment_details_by_company(company_id: str, employee_type_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get employee employment details by company ID.
    Uses companyId (lowercase 'd') as per UKG API requirements.
    
    Args:
        company_id: UKG company ID
        employee_type_codes: Optional list of employeeTypeCode values to filter (e.g., ['FTC', 'HRC', 'TMC'])
                            If None, returns all employees.
    """
    # Use companyId (lowercase 'd') as specified
    # Add per_Page to get all records (not just first 100)
    params = {"companyId": company_id, "per_Page": 2147483647}
    data = get_data("/personnel/v1/employee-employment-details", params)
    items = _normalize_list(data)
    
    # Filter by employeeTypeCode if specified
    if employee_type_codes:
        # Normalize to uppercase for comparison
        type_codes_set = {code.strip().upper() for code in employee_type_codes if code.strip()}
        original_count = len(items)
        items = [
            item for item in items 
            if item.get("employeeTypeCode", "").strip().upper() in type_codes_set
        ]
        print(f"[INFO] companyId={company_id} -> total records retrieved: {original_count} | filtered by employeeTypeCode={list(type_codes_set)}: {len(items)}")
    else:
        print(f"[INFO] companyId={company_id} -> total records retrieved: {len(items)}")
    
    return items

def parse_states_arg(states_arg: Optional[str]) -> Optional[Set[str]]:
    if not states_arg:
        return None
    return {s.strip().upper() for s in states_arg.split(",") if s.strip()}

def _fetch_person_state(emp_id: str,
                        cache: dict[str, str],
                        max_retries: int = 5) -> str:
    if emp_id in cache:
        return cache[emp_id]

    delay = 0.2  # seconds (200ms)
    for attempt in range(1, max_retries + 1):
        try:
            p = builder.get_person_details(emp_id)
            state = (p.get("addressState") or "").strip().upper()
            cache[emp_id] = state
            return state
        except Exception as e:
            # heurística de backoff ante errores transitorios (429/5xx)
            if attempt < max_retries:
                time.sleep(delay)
                delay = min(delay * 2, 3.2)  # cap 3.2s
            else:
                cache[emp_id] = ""
                return ""

def _process_employee(it: Dict[str, Any],
                      states_filter: Optional[Set[str]],
                      out_path: Path,
                      cache: Dict[str, str],
                      supervisor_id: Optional[str] = None,
                      dry_run: bool = False) -> tuple[str, str, str, Optional[str]]:

    emp_number = (it.get("employeeNumber") or "").strip()
    emp_id     = (it.get("employeeID") or "").strip()
    if not emp_number or not emp_id:
        return ("", "", "skipped", None)

    state = _fetch_person_state(emp_id, cache)

    # filtro por estado antes de construir
    if states_filter and state not in states_filter:
        if DEBUG:
            print(f"[DEBUG] skip emp={emp_number} state={state}")
        return (emp_number, state, "skipped", None)

    try:
        user_payload = builder.build_travelperk_user(emp_number)

        # Guardar archivo local si se solicita
        if os.getenv("SAVE_LOCAL", "0") == "1":
            file_path = out_path / f"travelperk_user_{emp_number}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(user_payload, f, indent=2)

        # Upsert a TravelPerk
        result = upserter.upsert_user_payload(user_payload, supervisor_id=supervisor_id, dry_run=dry_run)
        travelperk_id = result.get("id")

        return (emp_number, state, "saved" if not dry_run else "dry_run", travelperk_id)

    except SystemExit as se:
        print(f"[WARN] employeeNumber={emp_number} skipped: {se}")
        return (emp_number, state, "skipped", None)
    except Exception as e:
        print(f"[WARN] employeeNumber={emp_number} error: {repr(e)}")
        return (emp_number, state, "error", None)


def insert_supervisors_by_employee_numbers(employee_numbers: List[str],
                                          out_dir: str = "data/batch",
                                          dry_run: bool = False) -> Dict[str, str]:
    """
    Insert specific supervisors by employeeNumber before processing batch.
    Useful for validation: insert a supervisor first, then test with users that have that supervisor.
    
    Returns mapping: employeeNumber -> TravelPerk id
    """
    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    
    builder = load_builder()
    upserter = load_upserter()
    person_cache: dict[str, str] = {}
    mapping: Dict[str, str] = {}
    
    print(f"[INFO] === PRE-INSERT: Inserting {len(employee_numbers)} supervisor(s) ===")
    
    for emp_number in employee_numbers:
        emp_number = emp_number.strip()
        if not emp_number:
            continue
        
        try:
            print(f"[INFO] Inserting supervisor: employeeNumber={emp_number}")
            user_payload = builder.build_travelperk_user(emp_number)
            
            # Guardar archivo local si se solicita
            if os.getenv("SAVE_LOCAL", "0") == "1":
                file_path = out_path / f"travelperk_user_{emp_number}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(user_payload, f, indent=2)
            
            # Upsert a TravelPerk (sin supervisor, ya que estamos insertando supervisores)
            result = upserter.upsert_user_payload(user_payload, supervisor_id=None, dry_run=dry_run)
            travelperk_id = result.get("id")
            
            if travelperk_id:
                mapping[emp_number] = travelperk_id
                print(f"[INFO] Supervisor inserted: employeeNumber={emp_number} -> TravelPerk ID={travelperk_id}")
            else:
                print(f"[WARN] Supervisor not inserted (dry-run or error): employeeNumber={emp_number}")
                
        except SystemExit as se:
            print(f"[WARN] Supervisor employeeNumber={emp_number} skipped: {se}")
        except Exception as e:
            print(f"[ERROR] Supervisor employeeNumber={emp_number} error: {repr(e)}")
    
    print(f"[INFO] Pre-insert done: {len(mapping)} supervisor(s) inserted")
    return mapping


def build_and_upsert_users(items: List[Dict[str, Any]],
                           out_dir: str = "data/batch",
                           states_filter: Optional[Set[str]] = None,
                           dry_run: bool = False,
                           pre_inserted_mapping: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Build and upsert users in two phases:
    1. Insert users without supervisor (supervisorEmployeeID: null)
    2. Insert users with supervisor (using manager.value from phase 1 mapping)
    
    Returns mapping: employeeNumber -> TravelPerk id
    """
    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    workers = int(os.getenv("WORKERS", "12"))
    person_cache: dict[str, str] = {}
    
    # Get supervisor mapping
    print("[INFO] Fetching supervisor details from UKG...")
    supervisor_details = upserter.get_all_supervisor_details()
    supervisor_mapping = upserter.build_supervisor_mapping(supervisor_details)
    
    # Phase 1: Users without supervisor
    users_without_supervisor = upserter.get_users_without_supervisor(supervisor_mapping)
    users_with_supervisor = upserter.get_users_with_supervisor(supervisor_mapping)
    
    print(f"[INFO] Phase 1: {len(users_without_supervisor)} users without supervisor")
    print(f"[INFO] Phase 2: {len(users_with_supervisor)} users with supervisor")
    
    # Mapping: employeeNumber -> TravelPerk id
    # Start with pre-inserted supervisors if provided
    employee_to_travelperk_id: Dict[str, str] = {}
    if pre_inserted_mapping:
        employee_to_travelperk_id.update(pre_inserted_mapping)
        print(f"[INFO] Using {len(pre_inserted_mapping)} pre-inserted supervisor(s) in mapping")
    
    # Filter items by phase
    items_phase1 = [it for it in items if str(it.get("employeeNumber", "")).strip() in users_without_supervisor]
    items_phase2 = [it for it in items if str(it.get("employeeNumber", "")).strip() in users_with_supervisor]
    
    # Apply limit if specified (for testing)
    limit = int(os.getenv("LIMIT", "0"))
    if limit > 0:
        print(f"[INFO] LIMIT mode: processing only {limit} users per phase")
        items_phase1 = items_phase1[:limit]
        items_phase2 = items_phase2[:limit]
    
    # Phase 1: Insert users without supervisor
    print("[INFO] === PHASE 1: Inserting users without supervisor ===")
    total_phase1 = len(items_phase1)
    saved_phase1 = skipped_phase1 = errors_phase1 = 0
    printed_phase1 = 0
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_employee, it, states_filter, out_path, person_cache, None, dry_run)
                   for it in items_phase1]
        
        for fut in as_completed(futures):
            emp_number, state, status, travelperk_id = fut.result()
            if status == "saved" or status == "dry_run":
                saved_phase1 += 1
                if travelperk_id:
                    employee_to_travelperk_id[emp_number] = travelperk_id
            elif status == "error":
                errors_phase1 += 1
            else:
                skipped_phase1 += 1
            
            printed_phase1 += 1
            if printed_phase1 % 100 == 0 or printed_phase1 == total_phase1:
                print(f"[INFO] Phase 1 progress: {printed_phase1}/{total_phase1} | saved={saved_phase1} skipped={skipped_phase1} errors={errors_phase1}")
    
    print(f"[INFO] Phase 1 done: saved={saved_phase1} skipped={skipped_phase1} errors={errors_phase1}")
    print(f"[INFO] Mapped {len(employee_to_travelperk_id)} employees to TravelPerk IDs")
    
    # Phase 2: Insert users with supervisor
    print("[INFO] === PHASE 2: Inserting users with supervisor ===")
    total_phase2 = len(items_phase2)
    saved_phase2 = skipped_phase2 = errors_phase2 = 0
    printed_phase2 = 0
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for it in items_phase2:
            emp_number = str(it.get("employeeNumber", "")).strip()
            supervisor_emp_number = supervisor_mapping.get(emp_number)
            supervisor_id = employee_to_travelperk_id.get(supervisor_emp_number) if supervisor_emp_number else None
            
            # If supervisor not in local mapping, try to find it in TravelPerk
            if not supervisor_id and supervisor_emp_number:
                if DEBUG:
                    print(f"[DEBUG] Supervisor {supervisor_emp_number} not in local mapping, searching in TravelPerk...")
                supervisor_user = upserter.travelperk_get_user_by_external_id(supervisor_emp_number)
                if supervisor_user:
                    supervisor_id = supervisor_user.get("id")
                    if supervisor_id:
                        # Add to mapping for future reference
                        employee_to_travelperk_id[supervisor_emp_number] = supervisor_id
                        print(f"[INFO] Found supervisor {supervisor_emp_number} in TravelPerk: id={supervisor_id}")
                    else:
                        print(f"[WARN] employeeNumber={emp_number} supervisor={supervisor_emp_number} found in TravelPerk but no id in response")
                else:
                    print(f"[WARN] employeeNumber={emp_number} supervisor={supervisor_emp_number} not found in TravelPerk, skipping manager assignment")
            
            futures.append(ex.submit(_process_employee, it, states_filter, out_path, person_cache, supervisor_id, dry_run))
        
        for fut in as_completed(futures):
            emp_number, state, status, travelperk_id = fut.result()
            if status == "saved" or status == "dry_run":
                saved_phase2 += 1
                if travelperk_id:
                    employee_to_travelperk_id[emp_number] = travelperk_id
            elif status == "error":
                errors_phase2 += 1
            else:
                skipped_phase2 += 1
            
            printed_phase2 += 1
            if printed_phase2 % 100 == 0 or printed_phase2 == total_phase2:
                print(f"[INFO] Phase 2 progress: {printed_phase2}/{total_phase2} | saved={saved_phase2} skipped={skipped_phase2} errors={errors_phase2}")
    
    print(f"[INFO] Phase 2 done: saved={saved_phase2} skipped={skipped_phase2} errors={errors_phase2}")
    
    total_saved = saved_phase1 + saved_phase2
    total_skipped = skipped_phase1 + skipped_phase2
    total_errors = errors_phase1 + errors_phase2
    total = total_phase1 + total_phase2
    
    print(f"[INFO] === FINAL === total={total} | saved={total_saved} | skipped={total_skipped} | errors={total_errors} | out_dir={out_path}")
    
    return employee_to_travelperk_id

if __name__ == "__main__":
    args = parse_cli()

    # ENV fallback
    company_id = (args.company_id or os.getenv("COMPANY_ID") or "J9A6Y").strip()
    states_env = (args.states or os.getenv("STATES", "")).strip()
    states_filter = parse_states_arg(states_env)
    
    # Parse employee type codes filter
    employee_type_codes = None
    if args.employee_type_codes:
        employee_type_codes = [code.strip() for code in args.employee_type_codes.split(",") if code.strip()]
    elif os.getenv("EMPLOYEE_TYPE_CODES"):
        employee_type_codes = [code.strip() for code in os.getenv("EMPLOYEE_TYPE_CODES").split(",") if code.strip()]

    out_dir = os.getenv("OUT_DIR", "data/batch")
    if args.workers:
        os.environ["WORKERS"] = str(args.workers)
    if args.limit:
        os.environ["LIMIT"] = str(args.limit)

    # DRY_RUN y SAVE_LOCAL vía flags con fallback a ENV
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    if args.save_local:
        os.environ["SAVE_LOCAL"] = "1"

    dry_run = os.getenv("DRY_RUN", "0") == "1"
    has_api_key = bool(os.getenv("TRAVELPERK_API_KEY"))

    # sanity log
    type_codes_str = ",".join(employee_type_codes) if employee_type_codes else "ALL"
    print(f"[CFG] companyID={company_id} | states={states_env or 'ALL'} | employeeTypeCodes={type_codes_str} | workers={os.getenv('WORKERS','12')} | dry_run={dry_run} | save_local={os.getenv('SAVE_LOCAL','0')} | TRAVELPERK_API_KEY={'SET' if has_api_key else 'MISSING'}")

    # Pre-insert supervisors if specified
    pre_inserted_mapping: Dict[str, str] = {}
    if args.insert_supervisor:
        supervisor_numbers = [s.strip() for s in args.insert_supervisor.split(",") if s.strip()]
        if supervisor_numbers:
            pre_inserted_mapping = insert_supervisors_by_employee_numbers(
                supervisor_numbers, 
                out_dir=out_dir, 
                dry_run=dry_run
            )
            print(f"[INFO] Pre-inserted {len(pre_inserted_mapping)} supervisor(s) into mapping")
    
    items = get_employee_employment_details_by_company(company_id, employee_type_codes=employee_type_codes)
    mapping = build_and_upsert_users(
        items, 
        out_dir, 
        states_filter=states_filter, 
        dry_run=dry_run,
        pre_inserted_mapping=pre_inserted_mapping
    )
    
    # Save mapping to file
    if mapping:
        out_path = (HERE / out_dir).resolve()
        mapping_file = out_path / "employee_to_travelperk_id_mapping.json"
        with mapping_file.open("w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        print(f"[INFO] Saved mapping to {mapping_file}")

