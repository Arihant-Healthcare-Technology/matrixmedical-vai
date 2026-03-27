#!/usr/bin/env python3
"""
Upsert BILL users via Spend & Expense API.
Handles user creation and updates with local mapping for additional fields.

usage:
  python upsert-bill-entity.py <employeeNumber> [--dry-run]

environment (.env example):
  BILL_API_BASE=https://gateway.stage.bill.com/connect/v3/spend
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
    create_safe_error_context,
)

# Load environment variables from .env file
load_dotenv()

# Initialize secrets manager
_secrets = get_secrets_manager()

# Initialize rate limiter for BILL API (60 calls/min per BILL API limits)
_rate_limiter = get_rate_limiter("bill")

# Initialize logging with correlation support
configure_logging(include_module=True)
_logger = get_logger(__name__)

BILL_API_BASE = _secrets.get_secret("BILL_API_BASE") or os.getenv("BILL_API_BASE", "https://gateway.stage.bill.com/connect/v3/spend")
BILL_API_TOKEN = _secrets.get_secret("BILL_API_TOKEN") or os.getenv("BILL_API_TOKEN", "")
DEBUG = (_secrets.get_secret("DEBUG") or os.getenv("DEBUG", "0")) == "1"
MAX_RETRIES = int(_secrets.get_secret("MAX_RETRIES") or os.getenv("MAX_RETRIES", "2"))

# ---------------- utils & config ----------------

def headers() -> Dict[str, str]:
    if not BILL_API_TOKEN:
        raise SystemExit("Missing BILL_API_TOKEN env var")
    return {
        "apiToken": BILL_API_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _log(msg: str, level: str = "debug") -> None:
    """Log with correlation ID support and PII redaction."""
    # Redact PII from log messages
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

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:500]}

def fail(resp: requests.Response):
    body = safe_json(resp)
    # Redact PII from error response before logging/raising
    safe_body = sanitize_for_logging(body)
    error_msg = f"BILL API error {resp.status_code}: {json.dumps(safe_body)[:1000]}"
    _log(error_msg, level="error")
    raise SystemExit(error_msg)

def backoff_sleep(attempt: int):
    # exponential backoff: 1s, 2s, 4s...
    time.sleep(2 ** attempt)

# ---------------- payload checks ----------------

def validate_payload(p: Dict[str, Any]) -> None:
    """Validate BILL user payload has required fields"""
    required = ["email", "firstName", "lastName", "role"]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise SystemExit(f"Missing required fields in payload: {missing}")
    
    # Validate role
    valid_roles = ["ADMIN", "AUDITOR", "BOOKKEEPER", "MEMBER", "NO_ACCESS"]
    if p.get("role") not in valid_roles:
        raise SystemExit(f"Invalid role: {p.get('role')}. Must be one of: {valid_roles}")

# ---------------- BILL API calls ----------------

def bill_get_user(user_uuid: str) -> requests.Response:
    """Get user by BILL UUID"""
    url = f"{BILL_API_BASE}/users/{user_uuid}"
    _log(f"GET {url}")
    # Acquire rate limiter token before API call (SOW 5.1, 5.2)
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), timeout=45)

def _extract_users(container: Any) -> List[Dict[str, Any]]:
    """Best-effort extraction of users list from varying BILL responses."""
    if isinstance(container, list):
        return container
    if not isinstance(container, dict):
        return []
    for key in ("users", "items", "data", "content", "values", "results"):
        val = container.get(key)
        if isinstance(val, list):
            return val
    # single object
    if container.get("email"):
        return [container]
    # results might hold dicts with nested user object
    if isinstance(container.get("results"), list):
        nested = []
        for entry in container["results"]:
            if isinstance(entry, dict):
                if entry.get("email"):
                    nested.append(entry)
                elif isinstance(entry.get("user"), dict) and entry["user"].get("email"):
                    nested.append(entry["user"])
        if nested:
            return nested
    return []


def bill_get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email (userName in BILL) and ensure uuid is present."""
    url = f"{BILL_API_BASE}/users"

    # Strategy 1: direct filter by email
    for params in (
        {"email": email},
        {"userName": email},
        {"search": email},
    ):
        _log(f"GET {url} with params={sanitize_for_logging(params)} (searching by email)")
        # Acquire rate limiter token before API call
        _rate_limiter.acquire()
        resp = requests.get(url, headers=headers(), params=params, timeout=45)
        if resp.status_code == 200:
            data = safe_json(resp)
            users = _extract_users(data)
            for user in users:
                if user.get("email", "").lower() == email.lower():
                    if not user.get("uuid"):
                        _log(f"Found user for email={email} but without uuid; skipping this entry")
                        continue
                    return user
            if DEBUG:
                _log(f"No match in filtered response; sample keys={list(data)[:10] if isinstance(data, dict) else type(data)}")

    # Strategy 2: paginate (best effort)
    page = 1
    page_size = 200
    while True:
        params = {"page": page, "pageSize": page_size}
        _log(f"GET {url} page={page} pageSize={page_size} (fallback scan)")
        # Acquire rate limiter token before API call
        _rate_limiter.acquire()
        resp = requests.get(url, headers=headers(), params=params, timeout=45)
        if resp.status_code != 200:
            if DEBUG:
                _log(f"Paginated GET status={resp.status_code}, body={json.dumps(safe_json(resp))[:500]}")
            break
        data = safe_json(resp)
        users = _extract_users(data)
        if not users:
            break
        for user in users:
            if user.get("email", "").lower() == email.lower():
                if not user.get("uuid"):
                    _log(f"Found user for email={email} but without uuid; skipping this entry")
                    continue
                return user
        if len(users) < page_size:
            break
        page += 1

    _log(f"User with email={email} not found in BILL")
    return None

def bill_get_current_user() -> Optional[Dict[str, Any]]:
    """Get current user (useful for testing)"""
    url = f"{BILL_API_BASE}/users/current"
    _log(f"GET {url}")
    # Acquire rate limiter token before API call
    _rate_limiter.acquire()
    resp = requests.get(url, headers=headers(), timeout=45)
    if resp.status_code == 200:
        return safe_json(resp)
    return None

def bill_post_user(payload: Dict[str, Any]) -> requests.Response:
    """Create new user in BILL"""
    url = f"{BILL_API_BASE}/users"
    _log(f"POST {url}")
    # Acquire rate limiter token before API call
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json=payload, timeout=60)

def bill_patch_user(user_uuid: str, payload: Dict[str, Any]) -> requests.Response:
    """Update existing user in BILL (partial update)"""
    url = f"{BILL_API_BASE}/users/{user_uuid}"
    _log(f"PATCH {url}")
    # Acquire rate limiter token before API call
    _rate_limiter.acquire()
    return requests.patch(url, headers=headers(), json=payload, timeout=60)

def bill_delete_user(user_uuid: str) -> requests.Response:
    """Delete/retire user in BILL"""
    url = f"{BILL_API_BASE}/users/{user_uuid}"
    _log(f"DELETE {url}")
    # Acquire rate limiter token before API call
    _rate_limiter.acquire()
    return requests.delete(url, headers=headers(), timeout=60)

# ---------------- Upsert (payload in-memory) ----------------

def upsert_user_payload(payload: Dict[str, Any], 
                       dry_run: bool = False) -> Dict[str, Any]:
    """
    Upsert a BILL user using an already-built payload (dict).
    
    Payload should contain:
    - email (required)
    - firstName (required)
    - lastName (required)
    - role (required): ADMIN, AUDITOR, BOOKKEEPER, MEMBER, NO_ACCESS
    - retired (optional): true/false
    
    Returns a dict with action/status/uuid/id. Raises SystemExit on fatal errors.
    """
    validate_payload(payload)
    email = payload.get("email", "").strip()
    
    if dry_run:
        print(json.dumps({"dry_run": True, "action": "validate", "email": email}, indent=2))
        return {"dry_run": True, "action": "validate", "email": email}
    
    # Check if user exists by email
    existing_user = bill_get_user_by_email(email)
    
    if existing_user:
        # UPDATE path - user exists by email
        user_uuid = existing_user.get("uuid")
        if not user_uuid:
            raise SystemExit(f"Existing user found but no uuid in response for email={email}")
        
        # Build PATCH payload with only fields that changed
        patch_payload = {}
        
        # Update firstName if changed
        if "firstName" in payload and payload["firstName"] != existing_user.get("firstName"):
            patch_payload["firstName"] = payload["firstName"]
        
        # Update lastName if changed
        if "lastName" in payload and payload["lastName"] != existing_user.get("lastName"):
            patch_payload["lastName"] = payload["lastName"]
        
        # Update role if changed
        if "role" in payload and payload["role"] != existing_user.get("role"):
            patch_payload["role"] = payload["role"]
        
        # Update retired status if changed
        # NOTE: PATCH with retired may not work (returns 200 but doesn't update)
        # If retired needs to be true, consider using DELETE endpoint instead
        if "retired" in payload:
            current_retired = existing_user.get("retired", False)
            if payload["retired"] != current_retired:
                if payload["retired"]:
                    # If trying to retire, warn that PATCH may not work
                    _log("Attempting to set retired=true. PATCH may not work - consider DELETE instead", level="warn")
                patch_payload["retired"] = payload["retired"]
        
        # Perform PATCH if there are changes
        if patch_payload:
            # Sanitize payload for logging (redact PII)
            _log(f"PATCH payload: {json.dumps(sanitize_for_logging(patch_payload), indent=2)}")
            
            for attempt in range(MAX_RETRIES + 1):
                resp = bill_patch_user(user_uuid, patch_payload)
                if resp.status_code in (200, 204):
                    body = safe_json(resp)
                    result = {
                        "action": "update",
                        "status": resp.status_code,
                        "uuid": user_uuid,
                        "id": existing_user.get("id"),
                        "email": email
                    }
                    print(json.dumps(result, indent=2))
                    return result
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    _log(f"PATCH retry {attempt+1} after 5xx {resp.status_code}")
                    backoff_sleep(attempt)
                    continue
                fail(resp)
        else:
            # No changes needed
            _log(f"No changes needed for email={email}")
            return {
                "action": "update",
                "status": 200,
                "uuid": user_uuid,
                "id": existing_user.get("id"),
                "email": email,
                "note": "no changes needed"
            }
    else:
        # INSERT path - user does not exist
        # Build POST payload with only required/optional fields
        # NOTE: retired cannot be set on creation - BILL always creates with retired: false
        # If user should be retired, use DELETE endpoint instead, or update after creation
        post_payload = {
            "email": payload["email"],
            "firstName": payload["firstName"],
            "lastName": payload["lastName"],
            "role": payload["role"]
        }
        
        # NOTE: Do NOT include retired in POST - BILL ignores it and always creates with retired: false
        # If retired is needed, user must be deleted or updated after creation (if PATCH works)

        # Sanitize payload for logging (redact PII)
        _log(f"POST payload: {json.dumps(sanitize_for_logging(post_payload), indent=2)}")
        
        for attempt in range(MAX_RETRIES + 1):
            resp = bill_post_user(post_payload)
            if resp.status_code in (200, 201):
                body = safe_json(resp)
                user_uuid = body.get("uuid")
                user_id = body.get("id")
                if not user_uuid:
                    raise SystemExit(f"User created but no uuid in response for email={email}")
                result = {
                    "action": "insert",
                    "status": resp.status_code,
                    "uuid": user_uuid,
                    "id": user_id,
                    "email": email
                }
                print(json.dumps(result, indent=2))
                return result
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"POST retry {attempt+1} after 5xx {resp.status_code}")
                backoff_sleep(attempt)
                continue
            if resp.status_code in (400, 409):
                # User already exists (common BILL response)
                body = safe_json(resp)
                message = ""
                if isinstance(body, list) and body:
                    message = body[0].get("message", "")
                elif isinstance(body, dict):
                    message = body.get("message", "")
                if "already exists" in message.lower():
                    _log(f"POST returned {resp.status_code} (user exists), searching by email to update...")
                    existing_by_email = bill_get_user_by_email(email)
                    if existing_by_email:
                        user_uuid = existing_by_email.get("uuid")
                        if not user_uuid:
                            raise SystemExit(f"Existing user found by email but no uuid returned for email={email}")
                        _log(f"Found existing user by email, updating: uuid={user_uuid}")
                        # Retry as update (will build PATCH payload)
                        return upsert_user_payload(payload, dry_run=False)
                    # If API says exists but we cannot locate it, fail to make the issue visible
                    raise SystemExit(f"BILL API reports user exists but lookup by email failed for email={email}")
                fail(resp)
            fail(resp)

# ---------------- Main (for testing) ----------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python upsert-bill-entity.py <employeeNumber> [--dry-run]")
        print("Note: This script expects a payload from build-bill-entity.py")
        sys.exit(1)
    
    employee_number = sys.argv[1].strip()
    dry_run = "--dry-run" in sys.argv
    
    # Import builder to get the payload
    try:
        import importlib.util
        from pathlib import Path
        
        builder_file = Path(__file__).parent / "build-bill-entity.py"
        spec = importlib.util.spec_from_file_location("builder", str(builder_file))
        builder = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(builder)
        
        # Build payload
        payload = builder.build_bill_entity(employee_number)
        
        # Extract only BILL-supported fields
        bill_payload = {
            "email": payload.get("email", ""),
            "firstName": payload.get("firstName", ""),
            "lastName": payload.get("lastName", ""),
            "role": payload.get("role", "MEMBER"),  # Default role
            "retired": not payload.get("active", True)  # Convert active to retired
        }
        
        # Upsert
        result = upsert_user_payload(bill_payload, dry_run=dry_run)
        
    except SystemExit as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {repr(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

