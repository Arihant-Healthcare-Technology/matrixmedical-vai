#!/usr/bin/env python3
"""
DEPRECATED: This file has been replaced by src/infrastructure/adapters/motus/client.py
Please use the MotusClient class from the src module instead.
This file is kept for reference only and will be removed in a future release.
================================================================================
"""
import logging
import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import requests

from common import (
    get_secrets_manager,
    get_rate_limiter,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    redact_pii,
    configure_logging,
)

# Initialize logging
configure_logging()
logger = logging.getLogger(__name__)

# -------- ENV / paths --------
_secrets = get_secrets_manager()
ENV_PATH = _secrets.get_secret("ENV_PATH") or ".env"
TOKEN_CMD = _secrets.get_secret("MOTUS_TOKEN_CMD") or "python3 motus-get-token.py --write-env"

# -------- simple .env loader --------
def load_dotenv_simple(path: str) -> None:
    if not os.path.exists(path):
        return
    for line in open(path, "r", encoding="utf-8").read().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            if k and v is not None:
                os.environ.setdefault(k.strip(), v.strip())

# load .env early
load_dotenv_simple(ENV_PATH)

MOTUS_API_BASE = _secrets.get_secret("MOTUS_API_BASE") or "https://api.motus.com/v1"
MOTUS_JWT = _secrets.get_secret("MOTUS_JWT") or ""
DEBUG = (_secrets.get_secret("DEBUG") or "0") == "1"
MAX_RETRIES = int(_secrets.get_secret("MAX_RETRIES") or "2")

# ---------------- utils & config ----------------
def _log(msg: str) -> None:
    if DEBUG:
        cid = get_correlation_id()
        cid_prefix = f"[{cid}] " if cid else ""
        msg = redact_pii(msg)
        logger.debug(f"{cid_prefix}{msg}")

def _today_ymd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def ensure_start_date_for_insert(p: Dict[str, Any]) -> None:
    val = str(p.get("startDate", "")).strip()
    if not val:
        p["startDate"] = _today_ymd()
        _log(f"startDate injected for INSERT: {p['startDate']}")

def strip_start_date_for_update(p: Dict[str, Any]) -> None:
    if "startDate" in p:
        p.pop("startDate", None)
        _log("startDate stripped for UPDATE")

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:500]}

def fail(resp: requests.Response):
    body = safe_json(resp)
    raise SystemExit(f"Motus API error {resp.status_code}: {json.dumps(body)[:1000]}")

def backoff_sleep(attempt: int):
    time.sleep(2 ** attempt)


# -------- Rate Limiting (using common module) --------
_rate_limiter = get_rate_limiter("motus")


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

def refresh_token_and_reload_env(force: bool = False) -> None:
    """
    Ejecuta el comando para obtener/actualizar el token y recarga .env en memoria.
    """
    cmd = TOKEN_CMD + (" --force" if force and "--force" not in TOKEN_CMD else "")
    _log(f"Refreshing token with: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Token refresh failed: {e}")
    load_dotenv_simple(ENV_PATH)
    global MOTUS_JWT
    MOTUS_JWT = os.getenv("MOTUS_JWT", "")

def headers() -> Dict[str, str]:
    """
    Obtiene cabeceras con Bearer; si falta token, intenta generarlo.
    """
    global MOTUS_JWT
    if not MOTUS_JWT:
        _log("No MOTUS_JWT found; attempting token generation...")
        refresh_token_and_reload_env()
        if not MOTUS_JWT:
            raise SystemExit("Missing MOTUS_JWT and token refresh failed")
    return {
        "Authorization": f"Bearer {MOTUS_JWT}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _retry_on_auth(fn):
    """
    Ejecuta la request; si devuelve 401/403, refresca token y reintenta una vez.
    """
    resp = fn()
    if resp.status_code in (401, 403):
        _log(f"Auth failed ({resp.status_code}); refreshing token and retrying once...")
        refresh_token_and_reload_env(force=True)
        resp = fn()
    return resp

# ---------------- payload checks ----------------
def validate_payload(p: Dict[str, Any]) -> None:
    required = ["clientEmployeeId1", "programId", "firstName", "lastName", "email"]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise SystemExit(f"Missing required fields in payload: {missing}")

# ---------------- Motus API calls ----------------
def motus_get_driver(client_employee_id1: str) -> requests.Response:
    _rate_limiter.acquire()
    url = f"{MOTUS_API_BASE}/drivers/{client_employee_id1}"
    _log(f"GET {url}")
    return _retry_on_auth(lambda: requests.get(url, headers=headers(), timeout=45))

def motus_post_driver(payload: Dict[str, Any]) -> requests.Response:
    _rate_limiter.acquire()
    url = f"{MOTUS_API_BASE}/drivers"
    _log(f"POST {url}")
    return _retry_on_auth(lambda: requests.post(url, headers=headers(), json=payload, timeout=60))

def motus_put_driver(client_employee_id1: str, payload: Dict[str, Any]) -> requests.Response:
    _rate_limiter.acquire()
    url = f"{MOTUS_API_BASE}/drivers/{client_employee_id1}"
    _log(f"PUT {url}")
    return _retry_on_auth(lambda: requests.put(url, headers=headers(), json=payload, timeout=60))

def upsert_probe_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    dry-run con probe real: hace GET y reporta insert/update.
    requiere MOTUS_JWT (se obtiene automáticamente si falta).
    """
    if isinstance(payload, list):
        if not payload:
            raise SystemExit("Empty payload list")
        payload = payload[0]

    validate_payload(payload)
    client_id = str(payload["clientEmployeeId1"]).strip()
    r = motus_get_driver(client_id)
    if r.status_code == 404:
        out = {"dry_run": True, "id": client_id, "action": "would_insert"}
        print(json.dumps(out, indent=2))
        return out
    if r.status_code == 200:
        out = {"dry_run": True, "id": client_id, "action": "would_update"}
        print(json.dumps(out, indent=2))
        return out
    fail(r)
    return {"dry_run": True, "id": client_id, "action": "unknown"}

# ---------------- upsert (payload in-memory) ----------------
def upsert_driver_payload(payload: Dict[str, Any], dry_run: bool=False,
                          correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Upsert de un driver Motus usando un payload (dict).
    - INSERT: asegura startDate (hoy) si falta.
    - UPDATE: remueve startDate para no modificarla.
    Dry-run:
      * validate: valida payload.
      * probe (PROBE=1): hace GET real y devuelve would_insert / would_update.
    """
    # Set up correlation ID for tracing
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        set_correlation_id(generate_correlation_id())

    if isinstance(payload, list):
        if not payload:
            raise SystemExit("Empty payload list")
        payload = payload[0]

    validate_payload(payload)
    client_id = str(payload["clientEmployeeId1"])

    probe = (os.getenv("PROBE", "0") == "1")
    if dry_run and probe:
        result = upsert_probe_action(payload)
        result["correlation_id"] = get_correlation_id()
        return result

    if dry_run:
        out = {"dry_run": True, "action": "validate", "id": client_id, "correlation_id": get_correlation_id()}
        print(json.dumps(out, indent=2))
        return out

    # Existence check
    r = motus_get_driver(client_id)

    if r.status_code == 404:
        # INSERT path
        ensure_start_date_for_insert(payload)
        for attempt in range(MAX_RETRIES + 1):
            resp = motus_post_driver(payload)
            if resp.status_code in (200, 201):
                body = safe_json(resp)
                result = {"action": "insert", "status": resp.status_code, "id": client_id, "correlation_id": get_correlation_id()}
                print(json.dumps({**result, "body": body}, indent=2))
                return result
            if resp.status_code == 429:
                wait_time = handle_rate_limit(resp)
                _log(f"Rate limited (429), waiting {wait_time}s before retry")
                time.sleep(wait_time)
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"POST retry {attempt+1} after 5xx {resp.status_code}")
                backoff_sleep(attempt)
                continue
            # Handle errors gracefully instead of crashing
            error_body = safe_json(resp)
            result = {
                "action": "insert_failed",
                "status": resp.status_code,
                "id": client_id,
                "error": error_body,
                "correlation_id": get_correlation_id()
            }
            print(json.dumps(result, indent=2))
            return result

    elif r.status_code == 200:
        # UPDATE path
        strip_start_date_for_update(payload)
        for attempt in range(MAX_RETRIES + 1):
            resp = motus_put_driver(client_id, payload)
            if resp.status_code in (200, 204):
                body = safe_json(resp)
                result = {"action": "update", "status": resp.status_code, "id": client_id, "correlation_id": get_correlation_id()}
                print(json.dumps({**result, "body": body}, indent=2))
                return result
            if resp.status_code == 429:
                wait_time = handle_rate_limit(resp)
                _log(f"Rate limited (429), waiting {wait_time}s before retry")
                time.sleep(wait_time)
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                _log(f"PUT retry {attempt+1} after 5xx {resp.status_code}")
                backoff_sleep(attempt)
                continue
            # Handle errors gracefully instead of crashing
            error_body = safe_json(resp)
            result = {
                "action": "update_failed",
                "status": resp.status_code,
                "id": client_id,
                "error": error_body,
                "correlation_id": get_correlation_id()
            }
            print(json.dumps(result, indent=2))
            return result

    else:
        fail(r)

    return {"action": "unknown", "correlation_id": get_correlation_id()}

# ---------------- cli legacy (file-based) ----------------
def load_driver_payload(employee_number: str) -> Dict[str, Any]:
    path = os.path.abspath(f"data/motus_driver_{employee_number}.json")
    if not os.path.exists(path):
        raise SystemExit(f"Driver payload not found: {path}. Run the builder first.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}")
    return data[0] if isinstance(data, list) else data

def upsert_driver(employee_number: str, dry_run: bool=False) -> Dict[str, Any]:
    payload = load_driver_payload(employee_number)
    return upsert_driver_payload(payload, dry_run=dry_run)

def main():
    if len(sys.argv) < 2:
        print("usage: python upsert-motus-driver.py <employeeNumber> [--dry-run] [--probe]")
        sys.exit(1)

    # Validate Motus JWT token at startup (fail-fast if missing or invalid)
    # Note: This script has auto-refresh capability, but we validate upfront for consistency
    from src.infrastructure.config.settings import MotusSettings

    logger.info("Validating Motus API credentials...")
    motus_settings = MotusSettings.from_env()
    motus_settings.validate_or_exit()
    logger.info("Motus JWT token validated successfully.")

    employee_number = sys.argv[1]
    dry = "--dry-run" in sys.argv
    if "--probe" in sys.argv:
        os.environ["PROBE"] = "1"
    upsert_driver(employee_number, dry_run=dry)

if __name__ == "__main__":
    main()
