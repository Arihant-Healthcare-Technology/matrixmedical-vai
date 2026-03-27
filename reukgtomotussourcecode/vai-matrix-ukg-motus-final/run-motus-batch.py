#!/usr/bin/env python3
import os, json, importlib.util, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import argparse

# -------- simple .env loader --------
def load_dotenv_simple(path: str = ".env") -> None:
    if not os.path.exists(path): return
    for line in open(path, "r", encoding="utf-8").read().splitlines():
        if not line.strip() or line.strip().startswith("#"): continue
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

load_dotenv_simple(os.getenv("ENV_PATH", ".env"))

def parse_cli():
    p = argparse.ArgumentParser(description="Run Motus batch")
    p.add_argument("--company-id", dest="company_id", help="UKG companyID (e.g., J9A6Y)")
    p.add_argument("--states", dest="states", help="Comma-separated US states (e.g., FL,MS,NJ)")
    p.add_argument("--workers", dest="workers", type=int, help="Thread pool size")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="Validate but do not POST/PUT to Motus")
    p.add_argument("--save-local", dest="save_local", action="store_true", help="Write JSON files to data/batch")
    p.add_argument("--probe", dest="probe", action="store_true", help="On dry-run, GET Motus to report would_insert/update")
    return p.parse_args()

HERE = Path(__file__).resolve().parent
BUILDER_FILE = HERE / "build-motus-driver.py"
UPSERT_FILE  = HERE / "upsert-motus-driver.py"

def load_builder():
    if not BUILDER_FILE.exists():
        raise SystemExit(f"Builder file not found: {BUILDER_FILE}")
    spec = importlib.util.spec_from_file_location("builder", str(BUILDER_FILE))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

builder = load_builder()
get_data = builder.get_data
DEBUG = getattr(builder, "DEBUG", False)

def load_upserter():
    if not UPSERT_FILE.exists():
        raise SystemExit(f"Upserter file not found: {UPSERT_FILE}")
    spec = importlib.util.spec_from_file_location("upserter", str(UPSERT_FILE))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod

upserter = load_upserter()

def _normalize_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", []) if isinstance(data.get("items"), list) else [data]
    return []

# -------- Eligible Job Codes --------
ELIGIBLE_JOB_CODES = {
    # FAVR Program (21232)
    "1103", "4165", "4166", "1102", "1106", "4197", "4196",
    # CPM Program (21233)
    "2817", "4121", "2157"
}

def filter_by_eligible_job_codes(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter employees to only those with eligible job codes."""
    eligible = []
    for item in items:
        job_code = str(item.get("primaryJobCode", "") or "").strip()
        # Also check without leading zeros
        job_code_normalized = job_code.lstrip("0")
        if job_code in ELIGIBLE_JOB_CODES or job_code_normalized in ELIGIBLE_JOB_CODES:
            eligible.append(item)
        elif DEBUG:
            print(f"[DEBUG] Skipping employee {item.get('employeeNumber')} - ineligible job code: {job_code}")
    return eligible

def get_employee_employment_details_by_company(company_id: str) -> List[Dict[str, Any]]:
    params = {"companyID": company_id, "per_Page": 2147483647}
    data = get_data("/personnel/v1/employee-employment-details", params)
    items = _normalize_list(data)
    print(f"[INFO] companyID={company_id} -> total records retrieved: {len(items)}")
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

    delay = 0.2
    for attempt in range(1, max_retries + 1):
        try:
            p = builder.get_person_details(emp_id)
            state = (p.get("addressState") or "").strip().upper()
            cache[emp_id] = state
            return state
        except Exception:
            if attempt < max_retries:
                time.sleep(delay)
                delay = min(delay * 2, 3.2)
            else:
                cache[emp_id] = ""
                return ""

def _process_employee(it: Dict[str, Any],
                      states_filter: Optional[Set[str]],
                      out_path: Path,
                      cache: Dict[str, str],
                      default_company_id: str = "J9A6Y") -> tuple[str, str, str]:

    emp_number = (it.get("employeeNumber") or "").strip()
    emp_id     = (it.get("employeeID") or "").strip()
    company_id = (it.get("companyID") or it.get("companyId") or default_company_id).strip()
    if not emp_number or not emp_id:
        return ("", "", "skipped")

    state = _fetch_person_state(emp_id, cache)

    if states_filter and state not in states_filter:
        if DEBUG:
            print(f"[DEBUG] skip emp={emp_number} state={state}")
        return (emp_number, state, "skipped")

    try:
        driver = builder.build_motus_driver(emp_number, company_id)

        dry = os.getenv("DRY_RUN", "0") == "1"
        res = upserter.upsert_driver_payload(driver, dry_run=dry)

        if os.getenv("SAVE_LOCAL", "0") == "1":
            file_path = out_path / f"motus_driver_{emp_number}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump([driver], f, indent=2)

        return (emp_number, state, "saved" if not dry else "dry_run")

    except SystemExit as se:
        print(f"[WARN] employeeNumber={emp_number} skipped: {se}")
        return (emp_number, state, "skipped")
    except Exception as e:
        print(f"[WARN] employeeNumber={emp_number} error: {repr(e)}")
        return (emp_number, state, "error")

def build_and_save_drivers(items: List[Dict[str, Any]],
                           out_dir: str = "data/batch",
                           states_filter: Optional[Set[str]] = None,
                           company_id: str = "J9A6Y") -> None:
    out_path = (HERE / out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    workers = int(os.getenv("WORKERS", "12"))
    person_cache: dict[str, str] = {}

    total = len(items)
    saved = skipped = errors = 0
    printed = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_employee, it, states_filter, out_path, person_cache, company_id)
                   for it in items]

        for fut in as_completed(futures):
            emp_number, state, status = fut.result()
            if status == "saved":
                saved += 1
            elif status == "error":
                errors += 1
            else:
                skipped += 1

            printed += 1
            if printed % 100 == 0 or printed == total:
                print(f"[INFO] progress: {printed}/{total} | saved={saved} skipped={skipped} errors={errors}")

    print(f"[INFO] done: total={total} | saved={saved} | skipped={skipped} | errors={errors} | out_dir={out_path}")

if __name__ == "__main__":
    args = parse_cli()

    # ENV fallback
    company_id = (args.company_id or os.getenv("COMPANY_ID") or "J9A6Y").strip()
    states_env = (args.states or os.getenv("STATES", "")).strip()
    states_filter = parse_states_arg(states_env)

    out_dir = os.getenv("OUT_DIR", "data/batch")
    if args.workers:
        os.environ["WORKERS"] = str(args.workers)

    # DRY_RUN / SAVE_LOCAL / PROBE por flags con fallback a ENV
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    if args.save_local:
        os.environ["SAVE_LOCAL"] = "1"
    if args.probe:
        os.environ["PROBE"] = "1"

    has_jwt = bool(os.getenv("MOTUS_JWT"))
    print(f"[CFG] companyID={company_id} | states={states_env or 'ALL'} | workers={os.getenv('WORKERS','12')} | dry_run={os.getenv('DRY_RUN','0')} | probe={os.getenv('PROBE','0')} | save_local={os.getenv('SAVE_LOCAL','0')} | MOTUS_JWT={'SET' if has_jwt else 'MISSING'}")

    # Fetch all employees from UKG
    items = get_employee_employment_details_by_company(company_id)
    print(f"[INFO] Total employees from UKG: {len(items)}")

    # Filter by eligible job codes
    items = filter_by_eligible_job_codes(items)
    print(f"[INFO] Eligible employees (by job code): {len(items)}")

    build_and_save_drivers(items, out_dir, states_filter=states_filter, company_id=company_id)
