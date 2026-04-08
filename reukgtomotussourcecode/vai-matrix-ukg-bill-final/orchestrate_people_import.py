#!/usr/bin/env python3
"""
Simple orchestrator to:
1) Run run-bill-batch.py to generate a People CSV
2) Run scraping/run-bill-user-scrape.py to import that CSV into BILL UI

Usage examples:
  # Test with 1 user
  python orchestrate_people_import.py --company-id J9A6Y --limit 1 --url https://app-dev-bdc-stg.divvy.co/companies

  # Test with 5 users
  python orchestrate_people_import.py --company-id J9A6Y --limit 5 --url https://app-dev-bdc-stg.divvy.co/companies

Optional flags:
  --employee-number N     Process a single UKG employeeNumber instead of company-wide
  --dry-run-batch         Pass --dry-run to run-bill-batch (prevents any API writes to BILL)
  --workers N             Control worker threads for batch build

DEPRECATED: This script is deprecated and will be removed in a future version.
            Use 'ukg-bill import' CLI command instead.
            Run 'ukg-bill --help' for available commands.
"""
import warnings

warnings.warn(
    "orchestrate_people_import.py is deprecated and will be removed in a future version. "
    "Use 'ukg-bill import' CLI command instead. "
    "Run 'ukg-bill --help' for available commands.",
    DeprecationWarning,
    stacklevel=2
)

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent


def find_latest_csv(data_dir: Path) -> Optional[Path]:
    candidates = list(data_dir.glob("people-*.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_batch(company_id: Optional[str], limit: Optional[int], employee_number: Optional[str], workers: Optional[int], dry_run_batch: bool, python_exec: str) -> None:
    cmd = [python_exec, str(HERE / "run-bill-batch.py")]
    if employee_number:
        cmd += ["--employee-number", str(employee_number)]
    else:
        if not company_id:
            raise SystemExit("--company-id or --employee-number is required")
        cmd += ["--company-id", str(company_id)]
    if limit:
        cmd += ["--limit", str(limit)]
    if workers:
        cmd += ["--workers", str(workers)]
    if dry_run_batch:
        cmd += ["--dry-run"]

    print(f"[ORCH] Running batch with interpreter: {python_exec}")
    print(f"[ORCH] Command: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(HERE))


def run_scraper(url: str, csv_path: Path, python_exec: str) -> None:
    scraper = HERE / "scraping" / "run-bill-user-scrape.py"
    if not scraper.exists():
        raise SystemExit(f"Scraper not found: {scraper}")
    cmd = [python_exec, str(scraper), url, str(csv_path)]
    print(f"[ORCH] Running scraper with interpreter: {python_exec}")
    print(f"[ORCH] Command: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(scraper.parent))


def main():
    ap = argparse.ArgumentParser(description="Orchestrate UKG->CSV->BILL import flow")
    ap.add_argument("--company-id", help="UKG companyID (e.g., J9A6Y)")
    ap.add_argument("--employee-number", help="Single UKG employeeNumber (bypasses company-id)")
    ap.add_argument("--limit", type=int, default=1, help="Limit number of users to export in CSV (default: 1)")
    ap.add_argument("--workers", type=int, help="Worker threads for batch build")
    ap.add_argument("--url", required=True, help="BILL companies URL (e.g., https://app-dev-bdc-stg.divvy.co/companies)")
    ap.add_argument("--dry-run-batch", action="store_true", help="Pass --dry-run to run-bill-batch")
    ap.add_argument("--python-batch", dest="python_batch", default=sys.executable, help="Python interpreter to run run-bill-batch.py (default: current)")
    ap.add_argument("--python-scrape", dest="python_scrape", default=sys.executable, help="Python interpreter to run scraping (default: current)")
    args = ap.parse_args()

    print(f"[ORCH] Using interpreters -> batch: {args.python_batch} | scrape: {args.python_scrape}")

    # 1) Run batch to generate CSV
    run_batch(args.company_id, args.limit, args.employee_number, args.workers, args.dry_run_batch, args.python_batch)

    # 2) Locate latest CSV
    data_dir = HERE / "data"
    latest = find_latest_csv(data_dir)
    if not latest:
        raise SystemExit(f"No CSV generated in {data_dir}")
    print(f"[ORCH] Latest CSV detected: {latest}")

    # 3) Run scraper to import CSV
    run_scraper(args.url, latest, args.python_scrape)


if __name__ == "__main__":
    main()
