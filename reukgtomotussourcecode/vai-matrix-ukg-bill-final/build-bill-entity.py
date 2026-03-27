#!/usr/bin/env python3
"""
solution: Build a single Bill.com entity payload from UKG for a given employeeNumber,
auth method: using Basic Auth + US-CUSTOMER-API-KEY.

usage:
  python build-bill-entity.py <employeeNumber> <companyID>

environment (.env example):
  UKG_BASE_URL=https://service4.ultipro.com
  UKG_USERNAME=your-username
  UKG_PASSWORD=your-password

  # or provide the already-encoded token (base64 of "username:password"):
  UKG_BASIC_B64=
  UKG_CUSTOMER_API_KEY=YOUR_CUSTOMER_API_KEY

optional:
  DEBUG=1 # prints requested URLs and brief response info
"""
import os
import re
import sys
import json
import base64
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path
import requests

from common import (
    get_secrets_manager,
    validate_email,
    validate_state_code,
    validate_phone,
    ValidationResult,
)

# ---------- config ----------
# Initialize secrets manager (supports env, AWS Secrets Manager, or Vault)
_secrets = get_secrets_manager()

UKG_BASE = _secrets.get_secret("UKG_BASE_URL") or "https://service4.ultipro.com"
UKG_USERNAME = _secrets.get_secret("UKG_USERNAME") or ""
UKG_PASSWORD = _secrets.get_secret("UKG_PASSWORD") or ""
UKG_CUSTOMER_API_KEY = _secrets.get_secret("UKG_CUSTOMER_API_KEY") or ""
UKG_BASIC_B64 = _secrets.get_secret("UKG_BASIC_B64") or ""  # optional pre-encoded base64(username:password)
DEBUG = (_secrets.get_secret("DEBUG") or "0") == "1"

# ---------- HTTP helpers ----------
def _get_token() -> str:
    """
    Returns the HTTP Basic token as base64(username:password).
    If UKG_BASIC_B64 is provided and valid, uses it; otherwise, encodes UKG_USERNAME/UKG_PASSWORD.
    """
    if UKG_BASIC_B64:
        token = ''.join(UKG_BASIC_B64.strip().split())
        try:
            base64.b64decode(token, validate=True)
            if DEBUG:
                print(f"[DEBUG] Using UKG_BASIC_B64 (len={len(token)})")
            return token
        except Exception:
            if DEBUG:
                print("[WARN] Invalid UKG_BASIC_B64; falling back to username/password")
    if not UKG_USERNAME or not UKG_PASSWORD:
        raise SystemExit("Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64")
    return base64.b64encode(f"{UKG_USERNAME}:{UKG_PASSWORD}".encode()).decode()

def headers() -> Dict[str, str]:
    if not UKG_CUSTOMER_API_KEY:
        raise SystemExit("Missing UKG_CUSTOMER_API_KEY")
    return {
        "Authorization": f"Basic {_get_token()}",
        "US-CUSTOMER-API-KEY": UKG_CUSTOMER_API_KEY,
        "Accept": "application/json"
    }

def get_data(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{UKG_BASE.rstrip('/')}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params, timeout=45)
    if DEBUG:
        print(f"[DEBUG] GET {r.url} -> {r.status_code}")
    r.raise_for_status()
    try:
        data = r.json()
        if DEBUG:
            if isinstance(data, list):
                print(f"[DEBUG] list len={len(data)}; first keys={list(data[0].keys())[:12] if data else []}")
            elif isinstance(data, dict):
                print(f"[DEBUG] dict keys={list(data.keys())[:12]}")
        return data
    except Exception:
        return {}

# ---------- normalizers ----------
def to_iso_ymd(d: Optional[str]) -> str:
    """
    Normalize a date-like string to 'YYYY-MM-DD'.
    Accepts ISO strings with 'Z' or offsets, or plain 'YYYY-MM-DD'.
    Returns '' if not parseable or empty.
    """
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return ""

def normalize_phone(val: Optional[str]) -> str:
    if not val:
        return ""
    digits = re.sub(r"\D", "", val)
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    return val

# ---------- UKG fetchers (strict by employeeNumber + companyID) ----------
def get_employee_employment_details(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    Returns /personnel/v1/employee-employment-details for the given (employeeNumber, companyID).
    This is strict: it must match both fields or it returns {}.
    """
    params = {"employeeNumber": employee_number, "companyID": company_id}
    data = get_data("/personnel/v1/employee-employment-details", params)
    items: List[Dict[str, Any]] = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    for it in items:
        if str(it.get("employeeNumber")) == str(employee_number):
            comp = it.get("companyID") or it.get("companyId")
            if str(comp) == str(company_id):
                return it
    return {}  # not found

def get_employment_details(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    Returns /personnel/v1/employment-details for the given (employeeNumber, companyID).
    This is strict: it must match both fields or it returns {}.
    """
    params = {"employeeNumber": employee_number, "companyID": company_id}
    data = get_data("/personnel/v1/employment-details", params)
    items: List[Dict[str, Any]] = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    for it in items:
        if str(it.get("employeeNumber")) == str(employee_number):
            comp = it.get("companyID") or it.get("companyId")
            if str(comp) == str(company_id):
                return it
    return {}  # not found

def get_person_details(employee_id: Optional[str]) -> Dict[str, Any]:
    """
    Returns /personnel/v1/person-details for the given employeeId.
    """
    if not employee_id:
        raise SystemExit("No employeeId available — cannot fetch person-details")
    data = get_data("/personnel/v1/person-details", {"employeeId": employee_id})
    items: List[Dict[str, Any]] = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    for it in items:
        if str(it.get("employeeId")) == str(employee_id):
            return it
    return items[0] if items else {}

# ---------- builder ----------
def build_bill_entity(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    Build a Bill.com entity payload from UKG data.
    Minimal mapping (adapt to your concrete Bill.com object: Vendor/Customer/Employee):
    - externalId: employeeNumber
    - name: "<firstName> <lastName>"
    - email: person-details.emailAddress
    - isActive: true unless terminationDate present or employeeStatusCode != 'A'
    - custom.projectCode: employee-employment-details.primaryProjectCode
    """
    # 1) strict employment (dates, status, org, job...)
    employment = get_employment_details(employee_number, company_id)
    if DEBUG:
        print("[DEBUG] employment-details:")
        print(json.dumps(employment, indent=2))
    if not employment:
        raise SystemExit(f"no employment-details found for employeeNumber={employee_number} companyID={company_id}")

    # 2) strict employee-employment (primaryProjectCode, maybe employeeID fallback)
    emp_emp = get_employee_employment_details(employee_number, company_id)
    if DEBUG:
        print("[DEBUG] employee-employment-details:")
        print(json.dumps(emp_emp, indent=2))
    if not emp_emp:
        raise SystemExit(f"no employee-employment-details found for employeeNumber={employee_number} companyID={company_id}")

    # 3) resolve employeeId (covers employeeId/employeeID in either object)
    employee_id = (
        employment.get("employeeId") or employment.get("employeeID") or
        emp_emp.get("employeeId") or emp_emp.get("employeeID")
    )
    if not employee_id:
        raise SystemExit(f"no employeeId found for employeeNumber={employee_number} companyID={company_id}")

    # 4) person-details (email/name)
    person = get_person_details(employee_id)
    if DEBUG:
        print("[DEBUG] person-details:")
        print(json.dumps(person, indent=2))

    first_name = (person.get("firstName") or "").strip()
    last_name  = (person.get("lastName") or "").strip()
    full_name  = (first_name + " " + last_name).strip() or str(employee_number)

    email = (person.get("emailAddress") or "").strip()

    # Validate email before proceeding (SOW 3.6)
    email_validation = validate_email(email)
    if not email_validation.valid:
        if DEBUG:
            print(f"[WARN] Invalid email for employeeNumber={employee_number}: {email_validation.message}")
        # Continue with empty email - let BILL API reject if required
        if not email:
            raise SystemExit(f"Missing required email for employeeNumber={employee_number}")

    # active: default true; if terminationDate present -> false; else use employeeStatusCode heuristic
    termination_date = to_iso_ymd(employment.get("terminationDate") or emp_emp.get("terminationDate"))
    is_active = not bool(termination_date)
    status_code = str(employment.get("employeeStatusCode") or emp_emp.get("employeeStatusCode") or "").strip().upper()
    if status_code:
        # Commonly 'A' means Active
        is_active = (status_code == "A")

    # project code (often mapped to department/costCenter/class in accounting)
    primary_project_code = str(emp_emp.get("primaryProjectCode") or "")

    # 5) minimal Bill.com entity payload
    entity_payload = {
        "externalId": str(employee_number),
        "name": full_name,
        "email": email,
        "isActive": bool(is_active),
        "custom": {
            "projectCode": primary_project_code
        }
    }

    # Optional contact info if you want it available downstream (safe no-ops for Bill.com mapping later)
    # You may map these to vendor address fields in your Bill.com integration layer.
    addr1 = person.get("addressLine1")
    city  = person.get("addressCity")
    state = person.get("addressState")
    zipc  = person.get("addressZipCode")
    phone = normalize_phone(person.get("homePhone") or person.get("mobilePhone"))

    # Validate state code (SOW 3.7) - US states only
    if state:
        state_validation = validate_state_code(state)
        if not state_validation.valid:
            if DEBUG:
                print(f"[WARN] Invalid state code for employeeNumber={employee_number}: {state} - {state_validation.message}")
            # Normalize to uppercase for consistency
            state = state.upper() if state else ""

    # Validate phone format
    if phone:
        phone_validation = validate_phone(phone)
        if not phone_validation.valid and DEBUG:
            print(f"[WARN] Invalid phone format for employeeNumber={employee_number}: {phone}")

    entity_payload["contact"] = {
        "address1": addr1 or "",
        "city": city or "",
        "state": state or "",
        "postalCode": zipc or "",
        "phone": phone or "",
    }

    if DEBUG:
        print("[DEBUG] Bill.com entity payload:")
        print(json.dumps(entity_payload, indent=2))

    return entity_payload

def main():
    if len(sys.argv) < 3:
        print("usage: python build-bill-entity.py <employeeNumber> <companyID>")
        sys.exit(1)
    employee_number = sys.argv[1]
    company_id = sys.argv[2]
    entity = build_bill_entity(employee_number, company_id)
    out_path = os.path.abspath(f"data/bill_entity_{employee_number}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entity, f, indent=2)
    print(out_path)

if __name__ == "__main__":
    main()