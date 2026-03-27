#!/usr/bin/env python3
"""
solution: build a single TravelPerk user payload from UKG for a given employeeNumber,
auth method: using Basic Auth + US-CUSTOMER-API-KEY.
usage:
  python build-travelperk-user.py <employeeNumber> <companyID>

environment (.env example):
  UKG_BASE_URL=https://service4.ultipro.com
  UKG_USERNAME=your-username
  UKG_PASSWORD=your-password
  UKG_BASIC_B64= # opcional si querés pasar el token ya codificado
  UKG_CUSTOMER_API_KEY=your-customer-api-key

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
import requests

# ---------- config ----------
UKG_BASE = os.getenv("UKG_BASE_URL", "https://service4.ultipro.com")
UKG_USERNAME = os.getenv("UKG_USERNAME", "")
UKG_PASSWORD = os.getenv("UKG_PASSWORD", "")
UKG_BASIC_B64 = os.getenv("UKG_BASIC_B64", "")
UKG_CUSTOMER_API_KEY = os.getenv("UKG_CUSTOMER_API_KEY", "")
DEBUG = os.getenv("DEBUG", "0") == "1"

# ---------- HTTP helpers ----------
def _get_token() -> str:
    """
    Returns the HTTP Basic token as base64(username:password). If UKG_BASIC_B64
    is provided, it will validate and use it; otherwise, it encodes UKG_USERNAME/UKG_PASSWORD.
    """
    if UKG_BASIC_B64:
        token = UKG_BASIC_B64.strip()
        token = ''.join(token.split())
        try:
            base64.b64decode(token, validate=True)
            if DEBUG:
                print(f"[DEBUG] Using UKG_BASIC_B64 (length: {len(token)}, valid base64)")
            return token
        except Exception as e:
            if DEBUG:
                print(f"[WARN] UKG_BASIC_B64 is invalid base64: {e}")
                print(f"[WARN] Falling back to UKG_USERNAME/UKG_PASSWORD")
    if not UKG_USERNAME or not UKG_PASSWORD:
        raise SystemExit("Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64")
    raw = f"{UKG_USERNAME}:{UKG_PASSWORD}".encode()
    return base64.b64encode(raw).decode()

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
    normalize a date-like string to 'YYYY-MM-DD'.
    accepts ISO strings with 'Z' or offsets, or plain 'YYYY-MM-DD'.
    returns '' if not parseable or empty.
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

# ---------- UKG fetchers (strict by employeeNumber + companyID) ----------
def get_employee_employment_details(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    returns /employee-employment-details info for the given (employeeNumber, companyID)
    Mapping: employeeNumber, primaryProjectCode, terminationDate
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

def get_person_details(employee_id: Optional[str]) -> Dict[str, Any]:
    """
    returns person-details for the given employeeId
    Mapping: emailAddress, firstName, lastName
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
def build_travelperk_user(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    Build a TravelPerk SCIM user payload from UKG data.
    Mapping:
    - employeeNumber (employee-employment-details) → externalId
    - emailAddress (person-details) → userName
    - firstName (person-details) → name.givenName
    - lastName (person-details) → name.familyName
    - primaryProjectCode (employee-employment-details) → costCenter (Project Code)
    - terminationDate (employee-employment-details) → active (false if terminated, true otherwise)
    - Supervisor → LineManager (TODO)
    """
    # 1) employee-employment-details: employeeNumber, primaryProjectCode, terminationDate
    employee = get_employee_employment_details(employee_number, company_id)
    if DEBUG:
        print("[DEBUG] employee-employment-details:")
        print(json.dumps(employee, indent=2))
    if not employee:
        raise SystemExit(f"no employee-employment-details found for employeeNumber={employee_number} companyID={company_id}")

    # 2) resolve employeeID for person-details
    employee_id = employee.get("employeeID")
    if not employee_id:
        raise SystemExit(f"no employeeID found for employeeNumber={employee_number} companyID={company_id}")

    # 3) person-details: emailAddress, firstName, lastName
    person = get_person_details(employee_id)
    if DEBUG:
        print("[DEBUG] person-details:")
        print(json.dumps(person, indent=2))

    # 4) Extract mapped fields
    external_id = str(employee_number)  # employeeNumber → externalId
    
    email = person.get("emailAddress", "").strip()  # emailAddress → userName
    if not email:
        raise SystemExit(f"no emailAddress found for employeeNumber={employee_number} companyID={company_id}")

    first_name = person.get("firstName", "")  # firstName → name.givenName
    last_name  = person.get("lastName", "")   # lastName  → name.familyName

    # primaryProjectCode → costCenter (Project Code)
    primary_project_code = employee.get("primaryProjectCode", "")

    # terminationDate → active (false if terminated, true otherwise)
    termination_date = to_iso_ymd(employee.get("terminationDate"))
    is_active = not bool(termination_date)
    # Or: UKG employeeStatusCode logic
    status_code = str(employee.get("employeeStatusCode", "")).strip().upper()
    if status_code:
        is_active = (status_code == "A")

    # 5) Build SCIM payload
    user_payload = {
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"
        ],
        "userName": email,
        "externalId": external_id,
        "name": {
            "givenName": first_name,
            "familyName": last_name
        },
        "active": is_active,
        "emails": [
            {
                "value": email,
                "type": "work",
                "primary": True
            }
        ],
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {},
        "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User": {}
    }

    # Add costCenter (Project Code) if available
    if primary_project_code:
        user_payload["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"]["costCenter"] = primary_project_code

    # Note: endDate is not supported by TravelPerk schema — we use 'active' instead.

    # TODO: Supervisor → LineManager when source is defined
    # user_payload["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"]["manager"] = {"value": supervisor_id}
    # or
    # user_payload["urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"]["lineManagerEmail"] = supervisor_email

    if DEBUG:
        print("[DEBUG] TravelPerk user payload:")
        print(json.dumps(user_payload, indent=2))

    return user_payload

def main():
    if len(sys.argv) < 3:
        print("usage: python build-travelperk-user.py <employeeNumber> <companyID>")
        sys.exit(1)
    employee_number = sys.argv[1]
    company_id = sys.argv[2]
    user_payload = build_travelperk_user(employee_number, company_id)
    out_path = os.path.abspath(f"data/travelperk_user_{employee_number}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(user_payload, f, indent=2)
    print(out_path)

if __name__ == "__main__":
    main()