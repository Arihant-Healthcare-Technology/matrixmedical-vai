#!/usr/bin/env python3
"""
DEPRECATED: This file has been replaced by src/application/services/driver_builder.py
Please use the DriverBuilderService class from the src module instead.
This file is kept for reference only and will be removed in a future release.
================================================================================

solution: Build a single Motus driver payload from UKG for a given employeeNumber,
auth method: using Basic Auth + US-CUSTOMER-API-KEY.
usage:
  python get-data-by-id.py <employeeNumber>

environment (.env example):
  UKG_BASE_URL=https://service4.ultipro.com
  UKG_USERNAME=your-username
  UKG_PASSWORD=your-password

  # or provide the already-encoded token (base64 of "username:password"):
  UKG_BASIC_B64=
  UKG_CUSTOMER_API_KEY=YOUR_CUSTOMER_API_KEY

  # need to be adjusted
  MOTUS_PROGRAM_ID=21233

optional:
  DEBUG=1 # prints requested URLs and brief response info
"""
import logging
import os
import re
import sys
import json
import base64
from datetime import datetime
from typing import Any, Dict, Optional, List
import requests

from common import get_secrets_manager, configure_logging
from common.correlation import correlation_context, get_correlation_id

# Initialize logging
configure_logging()
logger = logging.getLogger(__name__)

# ---------- config ----------
_secrets = get_secrets_manager()

UKG_BASE = _secrets.get_secret("UKG_BASE_URL") or "https://service4.ultipro.com"
UKG_USERNAME = _secrets.get_secret("UKG_USERNAME") or ""
UKG_PASSWORD = _secrets.get_secret("UKG_PASSWORD") or ""
UKG_CUSTOMER_API_KEY = _secrets.get_secret("UKG_CUSTOMER_API_KEY") or ""
UKG_BASIC_B64 = _secrets.get_secret("UKG_BASIC_B64") or ""  # optional pre-encoded base64(username:password)
PROGRAM_ID = int(_secrets.get_secret("MOTUS_PROGRAM_ID") or "21233")
DEBUG = (_secrets.get_secret("DEBUG") or "0") == "1"

# ---------- constants for programId ----------
JOBCODE_TO_PROGRAM: dict[str, int] = {
    # FAVR (21232)
    "1103": 21232,
    "4165": 21232,
    "4166": 21232,
    "1102": 21232,
    "1106": 21232,
    "4197": 21232,
    "4196": 21232,

    # CPM (21233)
    "4154": 21233,
    "4152": 21233,
    "2817": 21233,
    "4121": 21233,
    "2157": 21233,
}

# ---------- HTTP helpers ----------
def _get_token() -> str:
    if UKG_BASIC_B64:
        return UKG_BASIC_B64.strip()
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

def get_data(path: str, params: Optional[Dict[str, Any]]=None) -> Any:
    url = f"{UKG_BASE.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, headers=headers(), params=params, timeout=45)
        if DEBUG:
            logger.debug(f"GET {r.url} -> {r.status_code}")
        r.raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(f"HTTP error fetching {url}: {e}")

    try:
        data = r.json()
        if DEBUG:
            if isinstance(data, list):
                logger.debug(f"list len={len(data)}; first keys={list(data[0].keys())[:12] if data else []}")
            elif isinstance(data, dict):
                logger.debug(f"dict keys={list(data.keys())[:12]}")
        return data
    except ValueError as e:
        raise SystemExit(f"JSON parse error from {url}: {e}")

def get_first_item(x: Any) -> Dict[str, Any]:
    if isinstance(x, list):
        return x[0] if x else {}
    return x if isinstance(x, dict) else {}

# ---------- normalizers ----------
def to_iso_date(d: Optional[str]) -> str:
    """Convert date to YYYY-MM-DD format as required by Motus API."""
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
    except Exception:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return d
    return dt.strftime("%Y-%m-%d")

def normalize_phone(val: Optional[str]) -> str:
    if not val:
        return ""
    digits = re.sub(r"\D", "", val)
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    return val


def filter_empty_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter out null, empty string, and zero values from payload.
    Motus API doesn't need empty values - they cause issues.
    """
    def is_empty(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        if isinstance(v, int) and v == 0:
            return True
        return False

    # Filter main payload fields (except customVariables)
    filtered = {k: v for k, v in payload.items() if k != "customVariables" and not is_empty(v)}

    # Filter custom variables - only include those with non-empty values
    if "customVariables" in payload:
        filtered_cvs = [
            cv for cv in payload["customVariables"]
            if cv.get("value") is not None and str(cv.get("value", "")).strip() != ""
        ]
        if filtered_cvs:
            filtered["customVariables"] = filtered_cvs

    return filtered

# ---------- UKG fetchers (strict by employeeNumber + companyID) ----------
def get_employee_employment_details(employee_number: str, company_id: str) -> Dict[str, Any]:
    """
    returns /employee-employment-details for the given (employeeNumber, companyID)
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
    returns /employment-details for the given (employeeNumber, companyID)
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
    returns person-details for the given employeeId
    """
    if not employee_id:
        raise SystemExit("No employeeId available — cannot fetch person-details")
    data = get_data("/personnel/v1/person-details", {"employeeId": employee_id})
    items: List[Dict[str, Any]] = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    for it in items:
        if str(it.get("employeeId")) == str(employee_id):
            return it
    return items[0] if items else {}

def get_supervisor_details(employee_id: str) -> Dict[str, Any]:
    """
    Fetch supervisor/manager details for the given employeeId.
    Returns supervisor info or empty dict if not found.
    """
    try:
        data = get_data("/personnel/v1/supervisor-details", {"employeeId": employee_id})
        items: List[Dict[str, Any]] = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        for it in items:
            if str(it.get("employeeId")) == str(employee_id):
                return it
        return items[0] if items else {}
    except SystemExit:
        if DEBUG:
            logger.warning(f"No supervisor found for employeeId={employee_id}")
        return {}

def determine_employment_status(employment_details: Dict[str, Any]) -> str:
    """
    Determine employment status including leave of absence.
    Returns: 'Active', 'Leave', 'Terminated', etc.
    """
    status_code = employment_details.get("employeeStatusCode", "")
    leave_start = employment_details.get("employeeStatusStartDate")
    leave_end = employment_details.get("employeeStatusExpectedEndDate")
    termination_date = employment_details.get("dateOfTermination")

    # Check for active leave of absence
    if leave_start and not leave_end:
        return "Leave"

    # Check for terminated
    if termination_date:
        return "Terminated"

    # Default to status code or Active
    return status_code if status_code else "Active"

def resolve_program_id_from_job_code(primary_job_code: Any, default_program_id: int | None = None) -> int | None:
    if primary_job_code is None:
        return default_program_id
    job_str = str(primary_job_code).strip()
    # first exact match, then without leading zeros
    return JOBCODE_TO_PROGRAM.get(job_str) or JOBCODE_TO_PROGRAM.get(job_str.lstrip("0"), default_program_id)

# ---------- builder ----------
def build_motus_driver(employee_number: str, company_id: str) -> Dict[str, Any]:
    correlation_id = get_correlation_id()

    logger.info(
        f"[{correlation_id}] BUILD START | "
        f"Employee: {employee_number} | Company: {company_id}"
    )

    # 1) employment-details (strict by company)
    logger.info(f"[{correlation_id}] UKG FETCH employment-details | Employee: {employee_number}")
    employment_details = get_employment_details(employee_number, company_id)
    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === EMPLOYMENT DETAILS ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employment_details keys: {list(employment_details.keys())}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: dateOfTermination = {employment_details.get('terminationDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employeeStatusStartDate = {employment_details.get('employeeStatusStartDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employeeStatusExpectedEndDate = {employment_details.get('employeeStatusExpectedEndDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employeeStatusCode = {employment_details.get('employeeStatusCode')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: originalHireDate = {employment_details.get('originalHireDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: primaryJobCode = {employment_details.get('primaryJobCode')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: jobDescription = {employment_details.get('jobDescription')}")
        logger.debug(f"[{correlation_id}] employment-details full response:")
        logger.debug(json.dumps(employment_details, indent=2))
    if not employment_details:
        logger.error(
            f"[{correlation_id}] BUILD ERROR | "
            f"Employee: {employee_number} | "
            f"Reason: No employment details found"
        )
        raise SystemExit(f"no employment details found for employeeNumber={employee_number} companyID={company_id}")

    # 2) employee-employment-details (strict by company) - for primaryProjectCode and fallback employeeId
    logger.info(f"[{correlation_id}] UKG FETCH employee-employment-details | Employee: {employee_number}")
    employee_employment = get_employee_employment_details(employee_number, company_id)
    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === EMPLOYEE EMPLOYMENT DETAILS ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employee_employment keys: {list(employee_employment.keys())}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: primaryProjectCode = {employee_employment.get('primaryProjectCode')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: primaryProjectDescription = {employee_employment.get('primaryProjectDescription')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employeeId = {employee_employment.get('employeeId')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: employeeID = {employee_employment.get('employeeID')}")
        logger.debug(f"[{correlation_id}] employee-employment-details full response:")
        logger.debug(json.dumps(employee_employment, indent=2))

    # 3) resolve employeeId (covers employeeId / employeeID with fallback)
    employee_id = (
        employment_details.get("employeeId") or
        employment_details.get("employeeID") or
        employee_employment.get("employeeId") or
        employee_employment.get("employeeID")
    )
    if not employee_id:
        logger.error(
            f"[{correlation_id}] BUILD ERROR | "
            f"Employee: {employee_number} | "
            f"Reason: No employeeId found"
        )
        raise SystemExit(f"no employeeId found for employeeNumber={employee_number} companyID={company_id}")

    # 4) person (requires employeeId)
    logger.info(f"[{correlation_id}] UKG FETCH person-details | Employee: {employee_number}")
    person = get_person_details(employee_id)
    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === PERSON DETAILS ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: person keys: {list(person.keys())}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: firstName = {person.get('firstName')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: lastName = {person.get('lastName')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: emailAddress = {person.get('emailAddress')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: addressLine1 = {person.get('addressLine1')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: addressCity = {person.get('addressCity')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: addressState = {person.get('addressState')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: addressZipCode = {person.get('addressZipCode')}")

    # 4b) supervisor/manager details
    logger.info(f"[{correlation_id}] UKG FETCH supervisor-details | Employee: {employee_number}")
    supervisor = get_supervisor_details(employee_id)
    supervisor_name = ""
    if supervisor:
        sup_first = supervisor.get("supervisorFirstName", "") or ""
        sup_last = supervisor.get("supervisorLastName", "") or ""
        supervisor_name = f"{sup_first} {sup_last}".strip()
    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === SUPERVISOR DETAILS ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: supervisor keys: {list(supervisor.keys()) if supervisor else []}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: supervisor_name = {supervisor_name}")

    # 4c) determine derived employment status
    derived_status = determine_employment_status(employment_details)
    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === STATUS DETERMINATION ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: Input - employeeStatusCode = {employment_details.get('employeeStatusCode')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: Input - employeeStatusStartDate = {employment_details.get('employeeStatusStartDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: Input - employeeStatusExpectedEndDate = {employment_details.get('employeeStatusExpectedEndDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: Input - dateOfTermination = {employment_details.get('dateOfTermination')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: Output - derived_status = {derived_status}")

    # 5) location for primaryWorkLocationCode
    location = {}
    loc_code = employment_details.get("primaryWorkLocationCode")
    if loc_code:
        logger.info(f"[{correlation_id}] UKG FETCH location | Employee: {employee_number} | LocationCode: {loc_code}")
        if DEBUG:
            logger.debug(f"[{correlation_id}] primaryWorkLocationCode = {loc_code}")
        try:
            location = get_first_item(get_data(f"/configuration/v1/locations/{loc_code}"))
        except SystemExit:
            try:
                location = get_first_item(get_data("/configuration/v1/locations", {"locationCode": loc_code}))
            except SystemExit as e:
                if DEBUG:
                    logger.warning(f"[{correlation_id}] Location fetch failed for {loc_code}: {e}")
                location = {}
        if DEBUG:
            logger.debug(f"[{correlation_id}] location full object:")
            logger.debug(json.dumps(location, indent=2))

    # 6) project
    primary_project_code = employee_employment.get("primaryProjectCode") or ""
    project_label = employee_employment.get("primaryProjectDescription") or ""

    # 7) programId (from job code)
    job_code = employment_details.get("primaryJobCode")
    program_id = resolve_program_id_from_job_code(job_code)
    if not program_id:
        logger.error(
            f"[{correlation_id}] BUILD ERROR | "
            f"Employee: {employee_number} | "
            f"Reason: No programId for jobCode={job_code}"
        )
        raise SystemExit(f"no programId found for employeeNumber={employee_number} companyID={company_id}")

    # 8) build driver payload
    driver = {
        "clientEmployeeId1": employee_number,
        "clientEmployeeId2": None,
        "programId": program_id,

        "firstName": person.get("firstName"),
        "lastName": person.get("lastName"),

        "address1": person.get("addressLine1"),
        "address2": person.get("addressLine2"),
        "city": person.get("addressCity"),
        "stateProvince": person.get("addressState"),
        "country": person.get("addressCountry"),
        "postalCode": person.get("addressZipCode"),

        "email": person.get("emailAddress", ""),
        "phone": normalize_phone(person.get("homePhone", "")),
        "alternatePhone": person.get("mobilePhone") or employment_details.get("workPhoneNumber") or "",

        "startDate": to_iso_date(employment_details.get("originalHireDate")),
        "endDate": to_iso_date(employment_details.get("dateOfTermination")),
        "leaveStartDate": to_iso_date(employment_details.get("employeeStatusStartDate")),
        "leaveEndDate": to_iso_date(employment_details.get("employeeStatusExpectedEndDate")),

        "annualBusinessMiles": 0,
        "commuteDeductionType": None,
        "commuteDeductionCap": None,

        "customVariables": [
            # project
            {"name": "Project Code", "value": primary_project_code},
            {"name": "Project",      "value": project_label},

            # role
            {"name": "Job Code", "value": employment_details.get("primaryJobCode", "") or ""},
            {"name": "Job",      "value": employment_details.get("jobDescription", "") or ""},

            # location
            {"name": "Location Code", "value": employment_details.get("primaryWorkLocationCode", "") or ""},
            {"name": "Location",      "value": location.get("description", "") or ""},

            # organizational structure
            {"name": "Org Level 1 Code", "value": employment_details.get("orgLevel1Code", "") or ""},
            {"name": "Org Level 2 Code", "value": employment_details.get("orgLevel2Code", "") or ""},
            {"name": "Org Level 3 Code", "value": employment_details.get("orgLevel3Code", "") or ""},
            {"name": "Org Level 4 Code", "value": employment_details.get("orgLevel4Code", "") or ""},

            # employment
            {"name": "Full/Part Time Code",    "value": employment_details.get("fullTimeOrPartTimeCode", "") or ""},
            {"name": "Employment Type Code",   "value": employment_details.get("employeeTypeCode", "") or ""},
            {"name": "Employment Status Code", "value": employment_details.get("employeeStatusCode", "") or ""},

            # important dates (MM/DD/YYYY)
            {"name": "Last Hire",        "value": to_iso_date(employment_details.get("lastHireDate"))},
            {"name": "Termination Date", "value": to_iso_date(employment_details.get("dateOfTermination"))},

            # manager/supervisor
            {"name": "Manager Name", "value": supervisor_name},

            # derived status (Active, Leave, Terminated)
            {"name": "Derived Status", "value": derived_status},
        ]
    }

    # Filter out null/empty values before returning
    driver = filter_empty_values(driver)

    if DEBUG:
        logger.debug(f"[{correlation_id}] Employee {employee_number}: === FINAL DRIVER PAYLOAD SUMMARY ===")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: clientEmployeeId1 = {driver.get('clientEmployeeId1')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: programId = {driver.get('programId')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: firstName = {driver.get('firstName')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: lastName = {driver.get('lastName')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: email = {driver.get('email')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: address1 = {driver.get('address1')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: city = {driver.get('city')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: stateProvince = {driver.get('stateProvince')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: postalCode = {driver.get('postalCode')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: startDate = {driver.get('startDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: endDate = {driver.get('endDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: leaveStartDate = {driver.get('leaveStartDate')}")
        logger.debug(f"[{correlation_id}] Employee {employee_number}: leaveEndDate = {driver.get('leaveEndDate')}")
        # Log custom variables
        for cv in driver.get('customVariables', []):
            logger.debug(f"[{correlation_id}] Employee {employee_number}: CV[{cv['name']}] = {cv['value']}")

    logger.info(
        f"[{correlation_id}] BUILD COMPLETE | "
        f"Employee: {employee_number} | "
        f"Name: {driver.get('firstName')} {driver.get('lastName')} | "
        f"Program: {program_id}"
    )

    return driver

def main():
    if len(sys.argv) < 3:
        print("usage: python build-motus-driver.py <employeeNumber> <companyID>")
        sys.exit(1)
    employee_number = sys.argv[1]
    company_id = sys.argv[2]

    # Create correlation context for this employee
    with correlation_context(prefix=f"build-{employee_number}"):
        driver = build_motus_driver(employee_number, company_id)
        out_path = os.path.abspath(f"data/motus_driver_{employee_number}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([driver], f, indent=2)
        print(out_path)

if __name__ == "__main__":
    main()