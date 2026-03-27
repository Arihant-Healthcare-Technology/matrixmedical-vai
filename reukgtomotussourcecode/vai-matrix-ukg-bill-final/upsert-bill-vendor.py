#!/usr/bin/env python3
"""
Upsert BILL.com vendors via Accounts Payable API.
Handles vendor creation and updates with lookup by name or external ID.

usage:
  python upsert-bill-vendor.py <vendor_id> [--dry-run]
  python upsert-bill-vendor.py --csv <csv_file> [--dry-run]

environment (.env example):
  BILL_API_BASE=https://gateway.stage.bill.com/connect/v3
  BILL_API_TOKEN=your-api-token
  DEBUG=1
  MAX_RETRIES=2
"""
import os
import sys
import json
import time
from typing import Any, Dict, Optional, List
from pathlib import Path
import requests
from dotenv import load_dotenv

# Add parent directory to path for common module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

# BILL AP API base URL (different from S&E)
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
def bill_list_vendors(page: int = 1, page_size: int = 200) -> requests.Response:
    """List all vendors with pagination."""
    url = f"{BILL_AP_API_BASE}/vendors"
    params = {"page": page, "pageSize": page_size}
    _log(f"GET {url} page={page} pageSize={page_size}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


def bill_get_vendor(vendor_id: str) -> requests.Response:
    """Get vendor by BILL vendor ID."""
    url = f"{BILL_AP_API_BASE}/vendors/{vendor_id}"
    _log(f"GET {url}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), timeout=45)


def bill_create_vendor(payload: Dict[str, Any]) -> requests.Response:
    """Create new vendor in BILL."""
    url = f"{BILL_AP_API_BASE}/vendors"
    _log(f"POST {url}")
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json=payload, timeout=60)


def bill_update_vendor(vendor_id: str, payload: Dict[str, Any]) -> requests.Response:
    """Update existing vendor in BILL (partial update)."""
    url = f"{BILL_AP_API_BASE}/vendors/{vendor_id}"
    _log(f"PATCH {url}")
    _rate_limiter.acquire()
    return requests.patch(url, headers=headers(), json=payload, timeout=60)


def bill_search_vendors(search: str) -> requests.Response:
    """Search vendors by name or email."""
    url = f"{BILL_AP_API_BASE}/vendors"
    params = {"search": search}
    _log(f"GET {url} search={search}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


# ---------- vendor lookup ----------
def _extract_vendors(container: Any) -> List[Dict[str, Any]]:
    """Extract vendors list from varying BILL responses."""
    if isinstance(container, list):
        return container
    if not isinstance(container, dict):
        return []
    for key in ("vendors", "items", "data", "content", "values", "results"):
        val = container.get(key)
        if isinstance(val, list):
            return val
    # Single object
    if container.get("id") or container.get("name"):
        return [container]
    return []


def get_vendor_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Find vendor by exact name match.
    Returns the vendor dict if found, None otherwise.
    """
    # Search by name
    resp = bill_search_vendors(name)
    if resp.status_code == 200:
        data = safe_json(resp)
        vendors = _extract_vendors(data)
        for vendor in vendors:
            if vendor.get("name", "").lower() == name.lower():
                return vendor

    # Fallback: paginate through all vendors
    page = 1
    while True:
        resp = bill_list_vendors(page=page)
        if resp.status_code != 200:
            break
        data = safe_json(resp)
        vendors = _extract_vendors(data)
        if not vendors:
            break
        for vendor in vendors:
            if vendor.get("name", "").lower() == name.lower():
                return vendor
        if len(vendors) < 200:
            break
        page += 1

    _log(f"Vendor with name={name} not found in BILL")
    return None


def get_vendor_by_external_id(external_id: str) -> Optional[Dict[str, Any]]:
    """
    Find vendor by external ID.
    Returns the vendor dict if found, None otherwise.
    """
    # Paginate through all vendors
    page = 1
    while True:
        resp = bill_list_vendors(page=page)
        if resp.status_code != 200:
            break
        data = safe_json(resp)
        vendors = _extract_vendors(data)
        if not vendors:
            break
        for vendor in vendors:
            if vendor.get("externalId") == external_id:
                return vendor
        if len(vendors) < 200:
            break
        page += 1

    _log(f"Vendor with externalId={external_id} not found in BILL")
    return None


# ---------- upsert logic ----------
def upsert_vendor_payload(payload: Dict[str, Any],
                           dry_run: bool = False) -> Dict[str, Any]:
    """
    Upsert a BILL vendor using an already-built payload (dict).

    Lookup order:
    1. By externalId (if present)
    2. By name

    Returns a dict with action/status/id. Raises SystemExit on fatal errors.
    """
    name = payload.get("name", "").strip()
    external_id = payload.get("externalId", "").strip()

    if not name:
        raise SystemExit("Missing required field: name")

    if dry_run:
        result = {"dry_run": True, "action": "validate", "name": name}
        print(json.dumps(result, indent=2))
        return result

    # Try to find existing vendor
    existing_vendor = None

    # Strategy 1: lookup by externalId
    if external_id:
        existing_vendor = get_vendor_by_external_id(external_id)

    # Strategy 2: lookup by name
    if not existing_vendor:
        existing_vendor = get_vendor_by_name(name)

    if existing_vendor:
        # UPDATE path
        vendor_id = existing_vendor.get("id")
        if not vendor_id:
            raise SystemExit(f"Existing vendor found but no id in response for name={name}")

        # Build PATCH payload with changed fields
        patch_payload = {}

        # Compare and update fields
        update_fields = ["name", "shortName", "email", "phone", "paymentMethod", "paymentTermDays"]
        for field in update_fields:
            if field in payload and payload[field] != existing_vendor.get(field):
                patch_payload[field] = payload[field]

        # Address comparison
        if "address" in payload:
            existing_addr = existing_vendor.get("address", {})
            payload_addr = payload["address"]
            addr_changed = False
            for addr_field in ["line1", "line2", "city", "state", "zip", "country"]:
                if payload_addr.get(addr_field) != existing_addr.get(addr_field):
                    addr_changed = True
                    break
            if addr_changed:
                patch_payload["address"] = payload["address"]

        if patch_payload:
            _log(f"PATCH payload: {json.dumps(sanitize_for_logging(patch_payload), indent=2)}")

            for attempt in range(MAX_RETRIES + 1):
                resp = bill_update_vendor(vendor_id, patch_payload)
                if resp.status_code in (200, 204):
                    result = {
                        "action": "update",
                        "status": resp.status_code,
                        "id": vendor_id,
                        "name": name
                    }
                    print(json.dumps(result, indent=2))
                    return result
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    _log(f"PATCH retry {attempt+1} after 5xx {resp.status_code}", level="warn")
                    backoff_sleep(attempt)
                    continue
                fail(resp)
        else:
            _log(f"No changes needed for vendor: {name}")
            return {
                "action": "update",
                "status": 200,
                "id": vendor_id,
                "name": name,
                "note": "no changes needed"
            }

    else:
        # INSERT path
        _log(f"POST payload: {json.dumps(sanitize_for_logging(payload), indent=2)}")

        for attempt in range(MAX_RETRIES + 1):
            resp = bill_create_vendor(payload)
            if resp.status_code in (200, 201):
                body = safe_json(resp)
                vendor_id = body.get("id")
                if not vendor_id:
                    raise SystemExit(f"Vendor created but no id in response for name={name}")
                result = {
                    "action": "insert",
                    "status": resp.status_code,
                    "id": vendor_id,
                    "name": name
                }
                print(json.dumps(result, indent=2))
                return result
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"POST retry {attempt+1} after 5xx {resp.status_code}", level="warn")
                backoff_sleep(attempt)
                continue
            if resp.status_code in (400, 409):
                # Vendor might already exist
                body = safe_json(resp)
                message = ""
                if isinstance(body, dict):
                    message = body.get("message", "")
                if "already exists" in message.lower() or "duplicate" in message.lower():
                    _log(f"POST returned {resp.status_code} (vendor exists), searching by name to update...", level="warn")
                    existing = get_vendor_by_name(name)
                    if existing:
                        _log(f"Found existing vendor by name, updating")
                        return upsert_vendor_payload(payload, dry_run=False)
                fail(resp)
            fail(resp)


# ---------- batch processing ----------
def upsert_vendors_from_file(json_dir: str, dry_run: bool = False) -> Dict[str, str]:
    """
    Upsert vendors from JSON files in a directory.

    Returns mapping: vendor_id -> BILL vendor id
    """
    path = Path(json_dir)
    if not path.exists():
        raise FileNotFoundError(f"Vendor directory not found: {json_dir}")

    mapping = {}
    for json_file in path.glob("vendor_*.json"):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            result = upsert_vendor_payload(payload, dry_run=dry_run)
            external_id = payload.get("externalId", "")
            if external_id and result.get("id"):
                mapping[external_id] = result["id"]

        except Exception as e:
            _log(f"Error processing {json_file}: {e}", level="error")

    return mapping


# ---------- main ----------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Upsert BILL.com vendors")
    parser.add_argument("vendor_id", nargs="?", help="Vendor ID to upsert")
    parser.add_argument("--dir", dest="json_dir", default="data/vendors",
                        help="Directory containing vendor JSON files")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Validate without making API calls")
    parser.add_argument("--all", action="store_true",
                        help="Process all vendors in directory")
    args = parser.parse_args()

    if args.all:
        # Process all vendors
        mapping = upsert_vendors_from_file(args.json_dir, dry_run=args.dry_run)
        print(f"\n[INFO] Processed {len(mapping)} vendors")

        # Save mapping
        if mapping:
            mapping_path = Path(args.json_dir) / "vendor_id_mapping.json"
            with mapping_path.open("w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2)
            print(f"[INFO] Saved mapping to {mapping_path}")

    elif args.vendor_id:
        # Process single vendor
        json_path = Path(args.json_dir) / f"vendor_{args.vendor_id}.json"
        if not json_path.exists():
            print(f"[ERROR] Vendor file not found: {json_path}")
            sys.exit(1)

        with json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        result = upsert_vendor_payload(payload, dry_run=args.dry_run)
        print(f"\n[INFO] Result: {result}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
