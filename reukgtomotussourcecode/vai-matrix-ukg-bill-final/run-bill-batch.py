import os, json, importlib.util, time, sys, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import argparse
import requests
from dotenv import load_dotenv
import csv
from datetime import datetime

from src.infrastructure.adapters.bill.mappers import format_cost_center

from common import (
    # Correlation IDs & Logging (SOW 7.2)
    RunContext,
    configure_logging,
    get_logger,
    # Notifications (SOW 4.6)
    get_notifier,
    # Report Generation (SOW 4.7, 7.3)
    ReportGenerator,
    # Rate Limiting (SOW 5.1, 5.2)
    get_rate_limiter,
    # PII Redaction (SOW 7.4, 7.5, 9.4)
    RedactingFilter,
    redact_pii,
)

# Load environment variables from .env file
load_dotenv()

# Initialize logging with correlation support
configure_logging(include_module=True)
_logger = get_logger(__name__)

# Add redaction filter to all handlers
for handler in logging.root.handlers:
    handler.addFilter(RedactingFilter())

def parse_cli():
    p = argparse.ArgumentParser(description="Run BILL batch")
    p.add_argument("--company-id", dest="company_id", help="UKG companyID (e.g., J9A6Y)")
    p.add_argument("--states", dest="states", help="Comma-separated US states (e.g., FL,MS,NJ)")
    p.add_argument("--workers", dest="workers", type=int, help="Thread pool size")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="Validate but do not POST/PUT to BILL")
    p.add_argument("--save-local", dest="save_local", action="store_true", help="Always write JSON files to data/batch")
    p.add_argument("--limit", dest="limit", type=int, help="Limit number of entities to process (for testing, e.g., --limit 1 or --limit 10)")
    p.add_argument("--employee-type-codes", dest="employee_type_codes", help="Filter by employeeTypeCode(s). Comma-separated list (e.g., FTC,HRC,TMC). If not specified, processes all types.")
    p.add_argument("--employee-number", dest="employee_number", help="Process only this UKG employeeNumber (bypasses company-id)")
    return p.parse_args()

HERE = Path(__file__).resolve().parent
BUILDER_FILE = HERE / "build-bill-entity.py"
UPSERT_FILE = HERE / "upsert-bill-entity.py"

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

def extract_supervisor_employee_id(it: Dict[str, Any], person: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Try to extract a supervisor/manager employeeId from the employment details item
    or the person details, considering multiple possible key names.
    """
    keys = [
        "supervisorEmployeeId", "supervisorEmployeeID", "managerEmployeeId", "managerEmployeeID",
        "reportsToEmployeeId", "reportsToEmployeeID", "supervisorId", "supervisorID", "reportsToId"
    ]
    for k in keys:
        val = it.get(k)
        if val:
            return str(val)
    if person:
        for k in keys:
            val = person.get(k)
            if val:
                return str(val)
    return None

def extract_supervisor_employee_number(it: Dict[str, Any], person: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Try to extract a supervisor/manager employeeNumber from common fields if present.
    """
    keys = [
        "supervisorEmployeeNumber", "supervisorNumber", "managerEmployeeNumber", "reportsToEmployeeNumber",
        "reportsToNumber", "managerNumber"
    ]
    for k in keys:
        val = it.get(k)
        if val:
            return str(val)
    if person:
        for k in keys:
            val = person.get(k)
            if val:
                return str(val)
    return None

def extract_supervisor_email_direct(it: Dict[str, Any], person: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Try direct email fields for supervisor if the payload includes them.
    """
    keys = [
        "supervisorEmail", "managerEmail", "reportsToEmail", "supervisorEmailAddress", "managerEmailAddress"
    ]
    for k in keys:
        val = it.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    if person:
        for k in keys:
            val = person.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None

def resolve_supervisor_email(it: Dict[str, Any], person: Dict[str, Any],
                              person_cache: Dict[str, Dict[str, Any]]) -> str:
    """
    Resolve supervisor email using several strategies with fallbacks and caching.
    """
    # 1) Direct email present
    direct = extract_supervisor_email_direct(it, person)
    if direct:
        return direct

    # 2) supervisor employeeId -> person-details
    sup_emp_id = extract_supervisor_employee_id(it, person)
    if sup_emp_id:
        try:
            if sup_emp_id not in person_cache:
                person_cache[sup_emp_id] = builder.get_person_details(str(sup_emp_id))
            sup_person = person_cache.get(sup_emp_id, {})
            email = (sup_person.get("emailAddress") or "").strip()
            if email:
                return email
        except Exception:
            pass

    # 3) supervisor employeeNumber -> employment -> employeeID -> person-details
    sup_emp_number = extract_supervisor_employee_number(it, person)
    if sup_emp_number:
        try:
            sup_employment = builder.get_employee_employment_details(str(sup_emp_number))
            sup_id = sup_employment.get("employeeID") or sup_employment.get("employeeId")
            if sup_id:
                if sup_id not in person_cache:
                    person_cache[sup_id] = builder.get_person_details(str(sup_id))
                sup_person = person_cache.get(sup_id, {})
                email = (sup_person.get("emailAddress") or "").strip()
                if email:
                    return email
        except Exception:
            pass

    return ""

def export_people_csv(items: List[Dict[str, Any]], out_dir: str = "data") -> Path:
    """
    Export a CSV matching people.csv header with required fields and Manager = supervisor email when available.
    Returns the path to the generated CSV file.
    """
    # Choose header template with priority:
    # 1) basic-import-structure.csv (no asterisks, preferred)
    # 2) import-people-template.csv
    # 3) people.csv (legacy)
    candidates = [
        HERE / "basic-import-structure.csv",
        HERE / "import-people-template.csv",
        HERE / "people.csv",
    ]
    header_file = None
    for c in candidates:
        p = c.resolve()
        if p.exists():
            header_file = p
            break
    if not header_file:
        raise SystemExit("Header template not found: basic-import-structure.csv | import-people-template.csv | people.csv")

    with header_file.open("r", encoding="utf-8") as f:
        header_line = f.readline().strip()
    columns = [c.strip() for c in header_line.split(",")]

    # Canonicalize column names (strip '*', lowercase) to support headers with/without '*'
    def _canon(name: str) -> str:
        return name.replace("*", "").strip().lower()
    required_canon = {"first name", "last name", "email address", "role"}

    # Always output header without asterisks
    columns_out = [c.replace("*", "").strip() for c in columns]

    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = out_path / f"people-{ts}.csv"

    # Role default: prefer BILL_CSV_ROLE, else BILL_DEFAULT_ROLE, else 'Member'
    default_role = os.getenv("BILL_CSV_ROLE") or os.getenv("BILL_DEFAULT_ROLE") or "Member"

    with out_file.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(columns_out)

        # Cache person-details by employeeId to reduce API calls
        person_cache: Dict[str, Dict[str, Any]] = {}

        for it in items:
            emp_id = it.get("employeeID") or it.get("employeeId")
            if not emp_id:
                # Cannot enrich without person-details; skip row creation
                continue
            try:
                if str(emp_id) not in person_cache:
                    person_cache[str(emp_id)] = builder.get_person_details(str(emp_id))
                person = person_cache[str(emp_id)]
            except Exception:
                person = {}

            # Person fields
            first_name = (person.get("firstName") or "").strip()
            last_name = (person.get("lastName") or "").strip()
            email = (person.get("emailAddress") or "").strip()
            middle = (person.get("middleName") or "").strip()
            middle_initial = middle[:1]

            # Supervisor email resolution with fallbacks and caching
            supervisor_email = resolve_supervisor_email(it, person, person_cache)

            # Extract budget assignment from direct_labor field
            direct_labor = bool(it.get("directLabor") or it.get("isDirectLabor", False))
            budget_assignment = "Direct" if direct_labor else "Indirect"

            # Extract and format cost center
            cost_center = (
                it.get("costCenter") or it.get("costCenterCode") or
                it.get("primaryProjectCode") or ""
            )
            cost_center_desc = (
                it.get("costCenterDescription") or it.get("primaryProjectDescription") or ""
            )
            formatted_cost_center = format_cost_center(cost_center, cost_center_desc)

            # Build row mapping using canonical keys (no '*', lowercase)
            row_data: Dict[str, str] = {
                "first name": first_name,
                "middle initial": middle_initial,
                "last name": last_name,
                "email address": email,
                "role": default_role,
                "physical card status": "",
                "membership status": "",
                "date added": "",
                "budget count": budget_assignment,
                "manager": supervisor_email,
                "cost center": formatted_cost_center,
            }

            # Ensure required fields present; skip if missing
            if not all(row_data.get(k, "").strip() for k in required_canon):
                continue

            # Emit row in exact column order, mapping actual header names via canonical keys
            row = [row_data.get(_canon(col), "") for col in columns_out]
            writer.writerow(row)

    print(f"[INFO] Exported people CSV -> {out_file}")
    return out_file

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
    for attempt in range(max_retries):
        try:
            person = builder.get_person_details(emp_id)
            state = person.get("addressState", "").strip().upper()
            cache[emp_id] = state
            return state
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                if DEBUG:
                    print(f"[WARN] Failed to fetch state for employeeId={emp_id}: {e}")
                return ""

def _process_employee(it: Dict[str, Any],
                     states_filter: Optional[Set[str]],
                     out_path: Path,
                     person_cache: dict[str, str],
                     dry_run: bool) -> tuple[str, str, str, Optional[str]]:
    """
    Process a single employee: build BILL entity payload and optionally save locally.
    
    Returns: (employee_number, state, status, bill_id)
    - status: "saved", "skipped", "error", or "dry_run"
    - bill_id: None for now (will be populated when upsert is implemented)
    """
    emp_number = str(it.get("employeeNumber", "")).strip()
    if not emp_number:
        return ("", "", "skipped", None)
    
    state = ""
    try:
        # Check state filter if specified
        if states_filter:
            emp_id = it.get("employeeID")
            if emp_id:
                state = _fetch_person_state(emp_id, person_cache)
                if state and state not in states_filter:
                    return (emp_number, state, "skipped", None)
        
        # Build BILL entity payload
        entity_payload = builder.build_bill_entity(emp_number)
        
        # Save locally (always save in dry-run mode, or if --save-local is set)
        if dry_run or os.getenv("SAVE_LOCAL", "0") == "1" or os.getenv("SAVE_LOCAL") == "1":
            file_path = out_path / f"bill_entity_{emp_number}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(entity_payload, f, indent=2)
        
        # Extract BILL API payload (only fields that BILL supports)
        bill_payload = {
            "email": entity_payload.get("email", ""),
            "firstName": entity_payload.get("firstName", ""),
            "lastName": entity_payload.get("lastName", ""),
            "role": entity_payload.get("role", "MEMBER"),
            "retired": entity_payload.get("retired", False)
        }
        
        # Upsert to BILL API
        result = upserter.upsert_user_payload(bill_payload, dry_run=dry_run)
        bill_uuid = result.get("uuid")
        bill_id = result.get("id")
        
        if dry_run:
            print(f"[DRY-RUN] employeeNumber={emp_number} -> payload built (not sent to BILL)")
            return (emp_number, state, "dry_run", bill_uuid)
        else:
            action = result.get("action", "unknown")
            if bill_uuid:
                print(f"[INFO] employeeNumber={emp_number} -> {action} | billUuid={bill_uuid}")
            else:
                print(f"[INFO] employeeNumber={emp_number} -> {action} (no uuid returned)")
            return (emp_number, state, "saved", bill_uuid)
            
    except SystemExit as se:
        print(f"[WARN] employeeNumber={emp_number} skipped: {se}")
        return (emp_number, state, "skipped", None)
    except Exception as e:
        print(f"[WARN] employeeNumber={emp_number} error: {repr(e)}")
        return (emp_number, state, "error", None)


def build_entities(items: List[Dict[str, Any]],
                   out_dir: str = "data/batch",
                   states_filter: Optional[Set[str]] = None,
                   dry_run: bool = False) -> Dict[str, str]:
    """
    Build BILL entity payloads from UKG employee data and upsert to BILL API.
    
    Returns mapping: employeeNumber -> BILL uuid
    """
    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    workers = int(os.getenv("WORKERS", "12"))
    person_cache: dict[str, str] = {}
    
    # Mapping: employeeNumber -> BILL uuid
    employee_to_bill_uuid: Dict[str, str] = {}
    
    # Apply limit if specified (for testing)
    limit = int(os.getenv("LIMIT", "0"))
    if limit > 0:
        print(f"[INFO] LIMIT mode: processing only {limit} entities")
        items = items[:limit]
    
    total = len(items)
    saved = skipped = errors = 0
    printed = 0
    
    print(f"[INFO] === Processing {total} entities ===")
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_employee, it, states_filter, out_path, person_cache, dry_run)
                   for it in items]
        
        for fut in as_completed(futures):
            emp_number, state, status, bill_uuid = fut.result()
            if status == "saved" or status == "dry_run":
                saved += 1
                if bill_uuid:
                    employee_to_bill_uuid[emp_number] = bill_uuid
            elif status == "error":
                errors += 1
            else:
                skipped += 1
            
            printed += 1
            if printed % 100 == 0 or printed == total:
                print(f"[INFO] Progress: {printed}/{total} | saved={saved} skipped={skipped} errors={errors}")
    
    print(f"[INFO] === FINAL === total={total} | saved={saved} | skipped={skipped} | errors={errors} | out_dir={out_dir}")
    
    # Save mapping: employeeNumber -> BILL uuid
    if employee_to_bill_uuid:
        mapping_path = out_path / "employee_to_bill_uuid_mapping.json"
        with mapping_path.open("w", encoding="utf-8") as f:
            json.dump(employee_to_bill_uuid, f, indent=2)
        print(f"[INFO] Saved mapping to {mapping_path}")
    
    return employee_to_bill_uuid


def run_batch():
    """Main batch processing with RunContext, notifications, and reporting."""
    args = parse_cli()

    # Configuration
    company_id = args.company_id or os.getenv("UKG_COMPANY_ID", "")
    employee_number_arg = (args.employee_number or "").strip()
    if not company_id and not employee_number_arg:
        print("[ERROR] Provide --company-id (or UKG_COMPANY_ID in .env) or use --employee-number to process a single user")
        exit(1)

    states_filter = parse_states_arg(args.states)
    dry_run = args.dry_run
    save_local = args.save_local or os.getenv("SAVE_LOCAL", "0") == "1"

    if args.workers:
        os.environ["WORKERS"] = str(args.workers)
    if args.limit:
        os.environ["LIMIT"] = str(args.limit)
    if save_local:
        os.environ["SAVE_LOCAL"] = "1"

    employee_type_codes = None
    if args.employee_type_codes:
        employee_type_codes = [code.strip() for code in args.employee_type_codes.split(",") if code.strip()]

    # Initialize notifier (optional - may fail if not configured)
    notifier = None
    try:
        notifier = get_notifier()
        _logger.info("Email notifications enabled")
    except Exception as e:
        _logger.warning(f"Notifications disabled: {e}")

    # Initialize report generator
    report_gen = ReportGenerator(output_dir="data/reports")

    print(f"[CFG] companyID={company_id or 'N/A'} | employeeNumber={employee_number_arg or 'ALL'} | states={states_filter or 'ALL'} | workers={os.getenv('WORKERS', '12')} | dry_run={dry_run} | save_local={save_local}")

    # Wrap batch in RunContext for correlation ID and stats tracking
    with RunContext(project="bill", company_id=company_id) as ctx:
        _logger.info(f"Starting BILL S&E batch processing")
        _logger.info(f"Correlation ID: {ctx.correlation_id}")
        _logger.info(f"Run ID: {ctx.run_id}")

        try:
            # Get employees from UKG
            if employee_number_arg:
                try:
                    single_item = builder.get_employee_employment_details(employee_number_arg)
                except Exception as e:
                    _logger.error(f"Failed to fetch employment details for employeeNumber={employee_number_arg}: {e}")
                    ctx.record_error(employee_number_arg, str(e))
                    raise
                items = [single_item] if single_item else []
            else:
                items = get_employee_employment_details_by_company(company_id, employee_type_codes)

            if not items:
                _logger.warning("No employees found")
                return

            # Export people CSV (always export when users are fetched)
            try:
                # Respect LIMIT for CSV export to avoid exporting all records when testing
                _limit = int(os.getenv("LIMIT", "0"))
                items_for_export = items[:_limit] if _limit > 0 else items
                export_people_csv(items_for_export, out_dir="data")
            except SystemExit as e:
                _logger.warning(f"CSV export skipped: {e}")
            except Exception as e:
                _logger.warning(f"CSV export error: {repr(e)}")

            # Build BILL entity payloads with stats tracking
            mapping = build_entities_with_context(
                items,
                ctx,
                out_dir="data/batch",
                states_filter=states_filter,
                dry_run=dry_run
            )

            _logger.info(f"Done. Mapped {len(mapping)} employees to BILL UUIDs")

        except Exception as e:
            _logger.error(f"Batch execution failed: {e}")
            ctx.record_error("batch", str(e))

            # Send critical alert
            if notifier:
                notifier.send_critical_alert(
                    title="BILL S&E Batch Failed",
                    error=e,
                    context={
                        "correlation_id": ctx.correlation_id,
                        "company_id": company_id,
                    }
                )
            raise

        # Generate reports
        _logger.info("Generating reports...")
        run_data = ctx.to_dict()

        report_paths = report_gen.generate_run_report(run_data)
        _logger.info(f"Reports generated: {report_paths}")

        # Generate validation report
        validation = report_gen.generate_validation_report(
            run_data,
            target_success_rate=99.0
        )
        _logger.info(f"Validation: passed={validation['passed']}, success_rate={validation['success_rate']:.2f}%")

        # Send notification
        if notifier:
            _logger.info("Sending run summary notification...")
            notifier.send_run_summary(run_data)

        # Print summary
        print("\n" + "=" * 60)
        print("RUN SUMMARY - BILL S&E")
        print("=" * 60)
        print(f"Correlation ID: {ctx.correlation_id}")
        print(f"Run ID: {ctx.run_id}")
        print(f"Duration: {ctx.duration_seconds:.2f} seconds")
        print(f"Success Rate: {ctx.success_rate:.1f}%")
        print("-" * 60)
        print(f"Total Processed: {ctx.stats['total_processed']}")
        print(f"Created/Updated: {ctx.stats['created']}")
        print(f"Skipped: {ctx.stats['skipped']}")
        print(f"Errors: {ctx.stats['errors']}")
        print("-" * 60)
        print(f"Reports: {report_paths}")
        print(f"Validation Passed: {validation['passed']}")
        print("=" * 60)

        return ctx.success_rate >= 99.0


def build_entities_with_context(items: List[Dict[str, Any]],
                                 ctx: RunContext,
                                 out_dir: str = "data/batch",
                                 states_filter: Optional[Set[str]] = None,
                                 dry_run: bool = False) -> Dict[str, str]:
    """
    Build BILL entity payloads with RunContext for stats tracking.
    """
    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    workers = int(os.getenv("WORKERS", "12"))
    person_cache: dict[str, str] = {}

    # Mapping: employeeNumber -> BILL uuid
    employee_to_bill_uuid: Dict[str, str] = {}

    # Apply limit if specified (for testing)
    limit = int(os.getenv("LIMIT", "0"))
    if limit > 0:
        _logger.info(f"LIMIT mode: processing only {limit} entities")
        items = items[:limit]

    total = len(items)
    saved = skipped = errors = 0
    printed = 0

    _logger.info(f"=== Processing {total} entities ===")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_employee, it, states_filter, out_path, person_cache, dry_run)
                   for it in items]

        for fut in as_completed(futures):
            emp_number, state, status, bill_uuid = fut.result()
            if status == "saved" or status == "dry_run":
                saved += 1
                ctx.stats['created'] += 1
                if bill_uuid:
                    employee_to_bill_uuid[emp_number] = bill_uuid
            elif status == "error":
                errors += 1
                ctx.stats['errors'] += 1
                ctx.record_error(emp_number, "Processing error")
            else:
                skipped += 1
                ctx.stats['skipped'] += 1

            ctx.stats['total_processed'] += 1
            printed += 1
            if printed % 100 == 0 or printed == total:
                _logger.info(f"Progress: {printed}/{total} | saved={saved} skipped={skipped} errors={errors}")

    _logger.info(f"=== FINAL === total={total} | saved={saved} | skipped={skipped} | errors={errors} | out_dir={out_dir}")

    # Save mapping: employeeNumber -> BILL uuid
    if employee_to_bill_uuid:
        mapping_path = out_path / "employee_to_bill_uuid_mapping.json"
        with mapping_path.open("w", encoding="utf-8") as f:
            json.dump(employee_to_bill_uuid, f, indent=2)
        _logger.info(f"Saved mapping to {mapping_path}")

    return employee_to_bill_uuid


if __name__ == "__main__":
    try:
        success = run_batch()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        sys.exit(1)

