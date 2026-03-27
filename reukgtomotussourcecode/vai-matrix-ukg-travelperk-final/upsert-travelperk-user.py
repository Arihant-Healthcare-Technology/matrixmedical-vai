#!/usr/bin/env python3
"""
Upsert TravelPerk users via SCIM API with supervisor hierarchy handling.
Handles two-phase insertion:
1. Insert users without supervisor (supervisorEmployeeID: null)
2. Insert users with supervisor (using manager.value from phase 1 mapping)

usage:
  python upsert-travelperk-user.py <employeeNumber> [--dry-run]

environment (.env example):
  TRAVELPERK_API_BASE=https://app.sandbox-travelperk.com
  TRAVELPERK_API_KEY=your-api-key
  DEBUG=1
  MAX_RETRIES=2
"""
import os
import sys
import json
import time
from typing import Any, Dict, Optional, List
import requests
from dotenv import load_dotenv

from common import (
    get_secrets_manager,
    get_rate_limiter,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    redact_pii,
)

# Load environment variables from .env file
load_dotenv()

_secrets = get_secrets_manager()

TRAVELPERK_API_BASE = _secrets.get_secret("TRAVELPERK_API_BASE") or "https://app.sandbox-travelperk.com"
TRAVELPERK_API_KEY = _secrets.get_secret("TRAVELPERK_API_KEY") or ""
DEBUG = (_secrets.get_secret("DEBUG") or "0") == "1"
MAX_RETRIES = int(_secrets.get_secret("MAX_RETRIES") or "2")

# -------- Rate Limiting (using common module) --------
_rate_limiter = get_rate_limiter("travelperk")


def handle_rate_limit(resp: requests.Response) -> int:
    """
    Handle 429 Too Many Requests response.
    Returns the number of seconds to wait before retrying.
    """
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            pass
    # Default: 60 seconds if no Retry-After header
    return 60


# ---------------- utils & config ----------------

def headers() -> Dict[str, str]:
    if not TRAVELPERK_API_KEY:
        raise SystemExit("Missing TRAVELPERK_API_KEY env var")
    return {
        "Authorization": f"ApiKey {TRAVELPERK_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _log(msg: str) -> None:
    if DEBUG:
        cid = get_correlation_id()
        cid_prefix = f"[{cid}] " if cid else ""
        msg = redact_pii(msg)
        print(f"[DEBUG] {cid_prefix}{msg}")

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:500]}

def fail(resp: requests.Response):
    body = safe_json(resp)
    raise SystemExit(f"TravelPerk API error {resp.status_code}: {json.dumps(body)[:1000]}")

def backoff_sleep(attempt: int):
    # exponential backoff: 1s, 2s, 4s...
    time.sleep(2 ** attempt)

# ---------------- payload checks ----------------

def validate_payload(p: Dict[str, Any]) -> None:
    required = ["userName", "externalId", "name"]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise SystemExit(f"Missing required fields in payload: {missing}")
    if not p.get("name", {}).get("givenName") or not p.get("name", {}).get("familyName"):
        raise SystemExit("Missing required name.givenName or name.familyName")

# ---------------- TravelPerk API calls ----------------

def travelperk_get_user(user_id: str) -> requests.Response:
    """Get user by TravelPerk ID"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users/{user_id}"
    _log(f"GET {url}")
    return requests.get(url, headers=headers(), timeout=45)

def travelperk_get_user_by_external_id(external_id: str) -> Optional[Dict[str, Any]]:
    """Get user by externalId (employeeNumber)"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users"
    params = {"filter": f'externalId eq "{external_id}"'}
    _log(f"GET {url}?filter=externalId eq \"{external_id}\"")
    resp = requests.get(url, headers=headers(), params=params, timeout=45)
    if resp.status_code == 200:
        data = safe_json(resp)
        resources = data.get("Resources", [])
        if resources:
            return resources[0]
    return None

def travelperk_post_user(payload: Dict[str, Any]) -> requests.Response:
    """Create new user in TravelPerk"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users"
    _log(f"POST {url}")
    return requests.post(url, headers=headers(), json=payload, timeout=60)

def travelperk_put_user(user_id: str, payload: Dict[str, Any]) -> requests.Response:
    """Update existing user in TravelPerk (full update)"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users/{user_id}"
    _log(f"PUT {url}")
    return requests.put(url, headers=headers(), json=payload, timeout=60)

def travelperk_patch_user(user_id: str, payload: Dict[str, Any]) -> requests.Response:
    """Update existing user in TravelPerk (partial update)"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users/{user_id}"
    _log(f"PATCH {url}")
    return requests.patch(url, headers=headers(), json=payload, timeout=60)

def travelperk_get_user_by_user_name(user_name: str) -> Optional[Dict[str, Any]]:
    """Get user by userName (email)"""
    _rate_limiter.acquire()
    url = f"{TRAVELPERK_API_BASE}/api/v2/scim/Users"
    params = {"filter": f'userName eq "{user_name}"'}
    _log(f"GET {url}?filter=userName eq \"{user_name}\"")
    resp = requests.get(url, headers=headers(), params=params, timeout=45)
    if resp.status_code == 200:
        data = safe_json(resp)
        resources = data.get("Resources", [])
        if resources:
            return resources[0]
    return None

# ---------------- Upsert (payload in-memory) ----------------

def upsert_user_payload(payload: Dict[str, Any],
                       supervisor_id: Optional[str] = None,
                       dry_run: bool = False,
                       correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Upsert a TravelPerk user using an already-built payload (dict).
    - If supervisor_id is provided, adds manager.value to payload
    - If correlation_id is provided, uses it for tracing; otherwise auto-generates one
    - Returns a dict with action/status/id/correlation_id. Raises SystemExit on fatal errors.
    """
    # Set up correlation ID for tracing
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        set_correlation_id(generate_correlation_id())

    validate_payload(payload)
    external_id = str(payload["externalId"])

    # Note: supervisor_id will be added to PATCH operations if provided, not to payload
    # This allows us to update manager separately in UPDATE operations

    if dry_run:
        out = {"dry_run": True, "action": "validate", "externalId": external_id, "correlation_id": get_correlation_id()}
        print(json.dumps(out, indent=2))
        return out

    # Check if user exists by externalId
    existing_user = travelperk_get_user_by_external_id(external_id)
    
    if existing_user:
        # UPDATE path - user exists by externalId
        user_id = existing_user.get("id")
        if not user_id:
            raise SystemExit(f"Existing user found but no id in response for externalId={external_id}")
        
        # Build PATCH operations according to SCIM spec
        operations = []
        
        # Update active status
        if "active" in payload:
            operations.append({
                "op": "replace",
                "path": "active",
                "value": payload["active"]
            })
        
        # Update name
        if "name" in payload:
            if "givenName" in payload["name"]:
                operations.append({
                    "op": "replace",
                    "path": "name.givenName",
                    "value": payload["name"]["givenName"]
                })
            if "familyName" in payload["name"]:
                operations.append({
                    "op": "replace",
                    "path": "name.familyName",
                    "value": payload["name"]["familyName"]
                })
        
        # Update costCenter (enterprise extension)
        enterprise_ext = payload.get("urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {})
        if "costCenter" in enterprise_ext:
            operations.append({
                "op": "replace",
                "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:costCenter",
                "value": enterprise_ext["costCenter"]
            })
        
        # Update manager (enterprise extension)
        if supervisor_id:
            operations.append({
                "op": "replace",
                "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:manager",
                "value": {"value": supervisor_id}
            })
        
        # Note: endDate is not supported by TravelPerk schema
        # Use active: false for terminated users instead
        
        # Build PATCH payload according to SCIM spec
        if operations:
            patch_payload = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": operations
            }
            _log(f"PATCH payload: {json.dumps(patch_payload, indent=2)}")
            
            for attempt in range(MAX_RETRIES + 1):
                resp = travelperk_patch_user(user_id, patch_payload)
                if resp.status_code in (200, 204):
                    body = safe_json(resp)
                    result = {"action": "update", "status": resp.status_code, "id": user_id, "externalId": external_id, "correlation_id": get_correlation_id()}
                    print(json.dumps(result, indent=2))
                    return result
                if resp.status_code == 429:
                    wait_time = handle_rate_limit(resp)
                    _log(f"Rate limited (429), waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    _log(f"PATCH retry {attempt+1} after 5xx {resp.status_code}")
                    backoff_sleep(attempt)
                    continue
                fail(resp)
        else:
            # No operations to perform - this shouldn't happen if we have changes
            _log(f"WARN: No operations generated for externalId={external_id}. Payload keys: {list(payload.keys())}")
            # Return success but note that no changes were made
            return {"action": "update", "status": 200, "id": user_id, "externalId": external_id, "note": "no changes needed", "correlation_id": get_correlation_id()}
    else:
        # INSERT path
        for attempt in range(MAX_RETRIES + 1):
            resp = travelperk_post_user(payload)
            if resp.status_code in (200, 201):
                body = safe_json(resp)
                user_id = body.get("id")
                if not user_id:
                    raise SystemExit(f"User created but no id in response for externalId={external_id}")
                result = {"action": "insert", "status": resp.status_code, "id": user_id, "externalId": external_id, "correlation_id": get_correlation_id()}
                print(json.dumps(result, indent=2))
                return result
            if resp.status_code == 429:
                wait_time = handle_rate_limit(resp)
                _log(f"Rate limited (429), waiting {wait_time}s before retry")
                time.sleep(wait_time)
                continue
            if resp.status_code == 409:
                # User already exists (probably by userName), try to find and update
                _log(f"POST returned 409 (conflict), trying to find user by userName...")
                user_name = payload.get("userName")
                if user_name:
                    existing_by_name = travelperk_get_user_by_user_name(user_name)
                    if existing_by_name:
                        user_id = existing_by_name.get("id")
                        if user_id:
                            _log(f"Found existing user by userName, updating: id={user_id}")
                            # Build PATCH operations (same logic as above)
                            operations = []
                            
                            if "active" in payload:
                                operations.append({
                                    "op": "replace",
                                    "path": "active",
                                    "value": payload["active"]
                                })
                            
                            if "name" in payload:
                                if "givenName" in payload["name"]:
                                    operations.append({
                                        "op": "replace",
                                        "path": "name.givenName",
                                        "value": payload["name"]["givenName"]
                                    })
                                if "familyName" in payload["name"]:
                                    operations.append({
                                        "op": "replace",
                                        "path": "name.familyName",
                                        "value": payload["name"]["familyName"]
                                    })
                            
                            enterprise_ext = payload.get("urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {})
                            if "costCenter" in enterprise_ext:
                                operations.append({
                                    "op": "replace",
                                    "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:costCenter",
                                    "value": enterprise_ext["costCenter"]
                                })
                            
                            # Note: endDate is not supported by TravelPerk schema
                            # Use active: false for terminated users instead
                            
                            if operations:
                                patch_payload = {
                                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                                    "Operations": operations
                                }
                                
                                resp = travelperk_patch_user(user_id, patch_payload)
                                if resp.status_code in (200, 204):
                                    body = safe_json(resp)
                                    result = {"action": "update", "status": resp.status_code, "id": user_id, "externalId": external_id, "correlation_id": get_correlation_id()}
                                    print(json.dumps(result, indent=2))
                                    return result
                            else:
                                # No operations needed
                                result = {"action": "update", "status": 200, "id": user_id, "externalId": external_id, "note": "no changes", "correlation_id": get_correlation_id()}
                                print(json.dumps(result, indent=2))
                                return result
                # If we couldn't resolve the conflict, fail
                fail(resp)
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"POST retry {attempt+1} after 5xx {resp.status_code}")
                backoff_sleep(attempt)
                continue
            fail(resp)

    return {"action": "unknown", "correlation_id": get_correlation_id()}

# ---------------- Supervisor hierarchy functions ----------------

def get_all_supervisor_details() -> List[Dict[str, Any]]:
    """
    Get all employee-supervisor-details from UKG.
    Returns list of supervisor detail records.
    """
    # Import builder to use its get_data function
    import importlib.util
    from pathlib import Path
    
    HERE = Path(__file__).resolve().parent
    BUILDER_FILE = HERE / "build-travelperk-user.py"
    
    if not BUILDER_FILE.exists():
        raise SystemExit(f"Builder file not found: {BUILDER_FILE}")
    
    spec = importlib.util.spec_from_file_location("builder", str(BUILDER_FILE))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    
    get_data = mod.get_data
    
    # Get all supervisor details
    params = {"per_Page": 2147483647}
    data = get_data("/personnel/v1/employee-supervisor-details", params)
    
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get("items", []) if isinstance(data.get("items"), list) else [data]
    return []

def build_supervisor_mapping(supervisor_details: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """
    Build mapping: employeeNumber -> supervisorEmployeeNumber
    Returns dict like {"000943": "003291", "003291": None, ...}
    """
    mapping: Dict[str, Optional[str]] = {}
    
    for detail in supervisor_details:
        emp_number = str(detail.get("employeeNumber", "")).strip()
        if not emp_number:
            continue
        
        supervisor_emp_number = detail.get("supervisorEmployeeNumber")
        if supervisor_emp_number:
            mapping[emp_number] = str(supervisor_emp_number).strip()
        else:
            # supervisorEmployeeID is null, so no supervisor
            mapping[emp_number] = None
    
    return mapping

def get_users_without_supervisor(supervisor_mapping: Dict[str, Optional[str]]) -> List[str]:
    """Get list of employeeNumbers that have no supervisor"""
    return [emp_num for emp_num, supervisor in supervisor_mapping.items() if supervisor is None]

def get_users_with_supervisor(supervisor_mapping: Dict[str, Optional[str]]) -> List[str]:
    """Get list of employeeNumbers that have a supervisor"""
    return [emp_num for emp_num, supervisor in supervisor_mapping.items() if supervisor is not None]

# ---------------- CLI legacy (file-based) ----------------

def load_user_payload(employee_number: str) -> Dict[str, Any]:
    """Load user payload from JSON file"""
    path = os.path.abspath(f"data/travelperk_user_{employee_number}.json")
    if not os.path.exists(path):
        raise SystemExit(f"User payload not found: {path}. Run the builder first.")
    data = json.load(open(path, "r"))
    return data if isinstance(data, dict) else (data[0] if isinstance(data, list) else {})

def upsert_user(employee_number: str, 
                supervisor_id: Optional[str] = None,
                dry_run: bool = False) -> Dict[str, Any]:
    """Upsert user from file with optional supervisor"""
    payload = load_user_payload(employee_number)
    return upsert_user_payload(payload, supervisor_id=supervisor_id, dry_run=dry_run)

def main():
    if len(sys.argv) < 2:
        print("usage: python upsert-travelperk-user.py <employeeNumber> [--dry-run]")
        sys.exit(1)
    employee_number = sys.argv[1]
    dry = "--dry-run" in sys.argv
    upsert_user(employee_number, dry_run=dry)

if __name__ == "__main__":
    main()

