#!/usr/bin/env python3
"""
Upsert BILL.com bills via Accounts Payable API.
Handles bill creation and updates with lookup by invoice number.

usage:
  python upsert-bill-invoice.py <invoice_number> [--dry-run]
  python upsert-bill-invoice.py --all [--dry-run]

environment (.env example):
  BILL_API_BASE=https://gateway.stage.bill.com/connect/v3
  BILL_API_TOKEN=your-api-token
  DEBUG=1
  MAX_RETRIES=2

DEPRECATED: This script is deprecated and will be removed in a future version.
            Use 'ukg-bill upsert invoice' CLI command instead.
            Run 'ukg-bill --help' for available commands.
"""
import warnings

warnings.warn(
    "upsert-bill-invoice.py is deprecated and will be removed in a future version. "
    "Use 'ukg-bill upsert invoice' CLI command instead. "
    "Run 'ukg-bill --help' for available commands.",
    DeprecationWarning,
    stacklevel=2
)

import os
import sys
import json
import time
from typing import Any, Dict, Optional, List
from pathlib import Path
import requests
from dotenv import load_dotenv

from common import (
    # Secrets
    get_secrets_manager,
    # Rate Limiting (SOW 5.1, 5.2)
    get_rate_limiter,
    # Correlation IDs (SOW 7.2)
    get_correlation_id,
    get_logger,
    configure_logging,
    # PII Redaction (SOW 7.4, 7.5, 9.4)
    redact_pii,
    sanitize_for_logging,
)

# Load environment variables from .env file
load_dotenv()

# Initialize secrets manager
_secrets = get_secrets_manager()

# Initialize rate limiter for BILL API (60 calls/min)
_rate_limiter = get_rate_limiter("bill")

# Initialize logging with correlation support
configure_logging(include_module=True)
_logger = get_logger(__name__)

# BILL AP API base URL
BILL_AP_API_BASE = _secrets.get_secret("BILL_AP_API_BASE") or os.getenv("BILL_AP_API_BASE", "https://gateway.stage.bill.com/connect/v3")
BILL_API_TOKEN = _secrets.get_secret("BILL_API_TOKEN") or os.getenv("BILL_API_TOKEN", "")
DEBUG = (_secrets.get_secret("DEBUG") or os.getenv("DEBUG", "0")) == "1"
MAX_RETRIES = int(_secrets.get_secret("MAX_RETRIES") or os.getenv("MAX_RETRIES", "2"))


# ---------- utils ----------
def _log(msg: str, level: str = "debug") -> None:
    """Log with correlation ID support and PII redaction."""
    safe_msg = redact_pii(msg)
    correlation_id = get_correlation_id()

    if level == "debug" and DEBUG:
        _logger.debug(f"[{correlation_id}] {safe_msg}")
    elif level == "info":
        _logger.info(f"[{correlation_id}] {safe_msg}")
    elif level == "warn":
        _logger.warning(f"[{correlation_id}] {safe_msg}")
    elif level == "error":
        _logger.error(f"[{correlation_id}] {safe_msg}")


def headers() -> Dict[str, str]:
    if not BILL_API_TOKEN:
        raise SystemExit("Missing BILL_API_TOKEN env var")
    return {
        "apiToken": BILL_API_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:500]}


def fail(resp: requests.Response):
    body = safe_json(resp)
    safe_body = sanitize_for_logging(body)
    error_msg = f"BILL API error {resp.status_code}: {json.dumps(safe_body)[:1000]}"
    _log(error_msg, level="error")
    raise SystemExit(error_msg)


def backoff_sleep(attempt: int):
    time.sleep(2 ** attempt)


# ---------- BILL AP API calls ----------
def bill_list_bills(page: int = 1, page_size: int = 200,
                     vendor_id: str = None, status: str = None) -> requests.Response:
    """List all bills with pagination and optional filters."""
    url = f"{BILL_AP_API_BASE}/bills"
    params = {"page": page, "pageSize": page_size}
    if vendor_id:
        params["vendorId"] = vendor_id
    if status:
        params["status"] = status
    _log(f"GET {url} page={page} pageSize={page_size}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


def bill_get_bill(bill_id: str) -> requests.Response:
    """Get bill by BILL ID."""
    url = f"{BILL_AP_API_BASE}/bills/{bill_id}"
    _log(f"GET {url}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), timeout=45)


def bill_create_bill(payload: Dict[str, Any]) -> requests.Response:
    """Create new bill in BILL."""
    url = f"{BILL_AP_API_BASE}/bills"
    _log(f"POST {url}")
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json=payload, timeout=60)


def bill_update_bill(bill_id: str, payload: Dict[str, Any]) -> requests.Response:
    """Update existing bill in BILL (partial update)."""
    url = f"{BILL_AP_API_BASE}/bills/{bill_id}"
    _log(f"PATCH {url}")
    _rate_limiter.acquire()
    return requests.patch(url, headers=headers(), json=payload, timeout=60)


def bill_search_bills(invoice_number: str = None, vendor_id: str = None) -> requests.Response:
    """Search bills by invoice number or vendor."""
    url = f"{BILL_AP_API_BASE}/bills"
    params = {}
    if invoice_number:
        params["invoiceNumber"] = invoice_number
    if vendor_id:
        params["vendorId"] = vendor_id
    _log(f"GET {url} params={params}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


# ---------- bill lookup ----------
def _extract_bills(container: Any) -> List[Dict[str, Any]]:
    """Extract bills list from varying BILL responses."""
    if isinstance(container, list):
        return container
    if not isinstance(container, dict):
        return []
    for key in ("bills", "items", "data", "content", "values", "results"):
        val = container.get(key)
        if isinstance(val, list):
            return val
    # Single object
    if container.get("id") or container.get("vendorId"):
        return [container]
    return []


def get_bill_by_invoice_number(invoice_number: str, vendor_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Find bill by invoice number (and optionally vendor ID).
    Returns the bill dict if found, None otherwise.
    """
    # Search by invoice number
    resp = bill_search_bills(invoice_number=invoice_number, vendor_id=vendor_id)
    if resp.status_code == 200:
        data = safe_json(resp)
        bills = _extract_bills(data)
        for bill in bills:
            invoice = bill.get("invoice", {})
            if invoice.get("number", "").lower() == invoice_number.lower():
                if vendor_id and bill.get("vendorId") != vendor_id:
                    continue
                return bill

    # Fallback: paginate through bills for this vendor
    if vendor_id:
        page = 1
        while True:
            resp = bill_list_bills(page=page, vendor_id=vendor_id)
            if resp.status_code != 200:
                break
            data = safe_json(resp)
            bills = _extract_bills(data)
            if not bills:
                break
            for bill in bills:
                invoice = bill.get("invoice", {})
                if invoice.get("number", "").lower() == invoice_number.lower():
                    return bill
            if len(bills) < 200:
                break
            page += 1

    _log(f"Bill with invoiceNumber={invoice_number} not found in BILL")
    return None


def get_bill_by_external_id(external_id: str) -> Optional[Dict[str, Any]]:
    """
    Find bill by external ID.
    Returns the bill dict if found, None otherwise.
    """
    page = 1
    while True:
        resp = bill_list_bills(page=page)
        if resp.status_code != 200:
            break
        data = safe_json(resp)
        bills = _extract_bills(data)
        if not bills:
            break
        for bill in bills:
            if bill.get("externalId") == external_id:
                return bill
        if len(bills) < 200:
            break
        page += 1

    _log(f"Bill with externalId={external_id} not found in BILL")
    return None


# ---------- upsert logic ----------
def upsert_bill_payload(payload: Dict[str, Any],
                         dry_run: bool = False) -> Dict[str, Any]:
    """
    Upsert a BILL bill using an already-built payload (dict).

    Lookup order:
    1. By externalId (invoice number)
    2. By invoice.number + vendorId

    Returns a dict with action/status/id. Raises SystemExit on fatal errors.
    """
    invoice = payload.get("invoice", {})
    invoice_number = invoice.get("number", "").strip()
    vendor_id = payload.get("vendorId", "").strip()
    external_id = payload.get("externalId", "").strip()

    if not invoice_number:
        raise SystemExit("Missing required field: invoice.number")
    if not vendor_id:
        raise SystemExit("Missing required field: vendorId")

    if dry_run:
        result = {"dry_run": True, "action": "validate", "invoiceNumber": invoice_number}
        print(json.dumps(result, indent=2))
        return result

    # Try to find existing bill
    existing_bill = None

    # Strategy 1: lookup by externalId
    if external_id:
        existing_bill = get_bill_by_external_id(external_id)

    # Strategy 2: lookup by invoice number + vendor
    if not existing_bill:
        existing_bill = get_bill_by_invoice_number(invoice_number, vendor_id)

    if existing_bill:
        # UPDATE path
        bill_id = existing_bill.get("id")
        if not bill_id:
            raise SystemExit(f"Existing bill found but no id in response for invoice={invoice_number}")

        # Check if bill can be updated (not paid or voided)
        status = existing_bill.get("status", "").lower()
        if status in ("paid", "voided", "partial"):
            _log(f"Bill {invoice_number} has status={status}, cannot update", level="warn")
            return {
                "action": "skip",
                "status": 200,
                "id": bill_id,
                "invoiceNumber": invoice_number,
                "note": f"Bill has status={status}, cannot update"
            }

        # Build PATCH payload with changed fields
        patch_payload = {}

        # Compare due date
        if payload.get("dueDate") != existing_bill.get("dueDate"):
            patch_payload["dueDate"] = payload["dueDate"]

        # Compare line items (simple comparison by total)
        new_total = sum(item.get("amount", 0) for item in payload.get("billLineItems", []))
        existing_total = sum(item.get("amount", 0) for item in existing_bill.get("billLineItems", []))
        if abs(new_total - existing_total) > 0.01:
            patch_payload["billLineItems"] = payload["billLineItems"]

        if patch_payload:
            _log(f"PATCH payload: {json.dumps(sanitize_for_logging(patch_payload), indent=2)}")

            for attempt in range(MAX_RETRIES + 1):
                resp = bill_update_bill(bill_id, patch_payload)
                if resp.status_code in (200, 204):
                    result = {
                        "action": "update",
                        "status": resp.status_code,
                        "id": bill_id,
                        "invoiceNumber": invoice_number
                    }
                    print(json.dumps(result, indent=2))
                    return result
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    _log(f"PATCH retry {attempt+1} after 5xx {resp.status_code}", level="warn")
                    backoff_sleep(attempt)
                    continue
                fail(resp)
        else:
            _log(f"No changes needed for bill: {invoice_number}")
            return {
                "action": "update",
                "status": 200,
                "id": bill_id,
                "invoiceNumber": invoice_number,
                "note": "no changes needed"
            }

    else:
        # INSERT path
        _log(f"POST payload: {json.dumps(sanitize_for_logging(payload), indent=2)}")

        for attempt in range(MAX_RETRIES + 1):
            resp = bill_create_bill(payload)
            if resp.status_code in (200, 201):
                body = safe_json(resp)
                bill_id = body.get("id")
                if not bill_id:
                    raise SystemExit(f"Bill created but no id in response for invoice={invoice_number}")
                result = {
                    "action": "insert",
                    "status": resp.status_code,
                    "id": bill_id,
                    "invoiceNumber": invoice_number
                }
                print(json.dumps(result, indent=2))
                return result
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"POST retry {attempt+1} after 5xx {resp.status_code}", level="warn")
                backoff_sleep(attempt)
                continue
            if resp.status_code in (400, 409):
                # Bill might already exist
                body = safe_json(resp)
                message = ""
                if isinstance(body, dict):
                    message = body.get("message", "")
                if "already exists" in message.lower() or "duplicate" in message.lower():
                    _log(f"POST returned {resp.status_code} (bill exists), searching to update...", level="warn")
                    existing = get_bill_by_invoice_number(invoice_number, vendor_id)
                    if existing:
                        return upsert_bill_payload(payload, dry_run=False)
                fail(resp)
            fail(resp)


# ---------- batch processing ----------
def upsert_bills_from_directory(json_dir: str, dry_run: bool = False) -> Dict[str, str]:
    """
    Upsert bills from JSON files in a directory.

    Returns mapping: invoice_number -> BILL bill id
    """
    path = Path(json_dir)
    if not path.exists():
        raise FileNotFoundError(f"Bills directory not found: {json_dir}")

    mapping = {}
    for json_file in path.glob("bill_*.json"):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            result = upsert_bill_payload(payload, dry_run=dry_run)
            invoice_number = payload.get("invoice", {}).get("number", "")
            if invoice_number and result.get("id"):
                mapping[invoice_number] = result["id"]

        except Exception as e:
            _log(f"Error processing {json_file}: {e}", level="error")

    return mapping


# ---------- main ----------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Upsert BILL.com bills")
    parser.add_argument("invoice_number", nargs="?", help="Invoice number to upsert")
    parser.add_argument("--dir", dest="json_dir", default="data/bills",
                        help="Directory containing bill JSON files")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Validate without making API calls")
    parser.add_argument("--all", action="store_true",
                        help="Process all bills in directory")
    args = parser.parse_args()

    if args.all:
        # Process all bills
        mapping = upsert_bills_from_directory(args.json_dir, dry_run=args.dry_run)
        print(f"\n[INFO] Processed {len(mapping)} bills")

        # Save mapping
        if mapping:
            mapping_path = Path(args.json_dir) / "bill_id_mapping.json"
            with mapping_path.open("w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2)
            print(f"[INFO] Saved mapping to {mapping_path}")

    elif args.invoice_number:
        # Process single bill
        safe_name = args.invoice_number.replace("/", "_").replace("\\", "_")
        json_path = Path(args.json_dir) / f"bill_{safe_name}.json"
        if not json_path.exists():
            print(f"[ERROR] Bill file not found: {json_path}")
            sys.exit(1)

        with json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        result = upsert_bill_payload(payload, dry_run=args.dry_run)
        print(f"\n[INFO] Result: {result}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
