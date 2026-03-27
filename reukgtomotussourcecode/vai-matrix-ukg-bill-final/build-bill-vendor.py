#!/usr/bin/env python3
"""
Build BILL.com AP Vendor payloads from source data.

This module creates vendor payloads for the BILL.com Accounts Payable API.
Vendors can be sourced from CSV files, UKG data, or external systems.

usage:
  python build-bill-vendor.py <vendor_id>
  python build-bill-vendor.py --csv <csv_file>

environment (.env example):
  VENDOR_DATA_SOURCE=csv  # or 'ukg', 'api'
  VENDOR_CSV_PATH=data/vendors.csv
  DEBUG=1
"""
import os
import sys
import json
import csv
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path

from common import (
    get_secrets_manager,
    validate_email,
    validate_state_code,
    validate_country_code,
    validate_phone,
    validate_required,
    ValidationResult,
    ValidationResults,
)

# ---------- config ----------
_secrets = get_secrets_manager()

VENDOR_DATA_SOURCE = _secrets.get_secret("VENDOR_DATA_SOURCE") or os.getenv("VENDOR_DATA_SOURCE", "csv")
VENDOR_CSV_PATH = _secrets.get_secret("VENDOR_CSV_PATH") or os.getenv("VENDOR_CSV_PATH", "data/vendors.csv")
DEBUG = (_secrets.get_secret("DEBUG") or os.getenv("DEBUG", "0")) == "1"

# Valid payment methods for BILL.com AP
VALID_PAYMENT_METHODS = ["CHECK", "ACH", "WIRE", "CARD_ACCOUNT"]

# Default payment terms in days
DEFAULT_PAYMENT_TERM_DAYS = 30


def _debug(msg: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {msg}")


# ---------- validation ----------
def validate_vendor_payload(payload: Dict[str, Any]) -> ValidationResults:
    """
    Validate vendor payload has required fields and valid data.

    Required fields:
    - name: Vendor name (required)
    - email: Vendor email (optional but validated if present)
    - address.country: Country code (required for international)

    Returns ValidationResults with all validation errors.
    """
    results = ValidationResults()

    # Required: name
    name_result = validate_required(payload.get("name"), "name")
    results.add(name_result)

    # Optional but validated: email
    email = payload.get("email")
    if email:
        email_result = validate_email(email)
        results.add(email_result)

    # Optional but validated: phone
    phone = payload.get("phone")
    if phone:
        phone_result = validate_phone(phone)
        results.add(phone_result)

    # Address validation
    address = payload.get("address", {})
    if address:
        # State validation (US only)
        state = address.get("state")
        country = address.get("country", "US")
        if state and country == "US":
            state_result = validate_state_code(state)
            results.add(state_result)

        # Country validation
        if country:
            country_result = validate_country_code(country)
            results.add(country_result)

    # Payment method validation
    payment_method = payload.get("paymentMethod")
    if payment_method and payment_method not in VALID_PAYMENT_METHODS:
        results.add(ValidationResult(
            valid=False,
            field="paymentMethod",
            value=payment_method,
            message=f"Invalid payment method: {payment_method}. Must be one of: {VALID_PAYMENT_METHODS}"
        ))

    return results


# ---------- data extraction ----------
def load_vendors_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load vendor data from CSV file.

    Expected CSV columns:
    - vendor_id (required)
    - name (required)
    - short_name (optional)
    - email (optional)
    - phone (optional)
    - address_line1 (optional)
    - address_line2 (optional)
    - city (optional)
    - state (optional)
    - zip (optional)
    - country (optional, defaults to US)
    - payment_method (optional, defaults to CHECK)
    - payment_term_days (optional, defaults to 30)
    - tax_id (optional)
    """
    vendors = []
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"Vendor CSV file not found: {csv_path}")

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor = {
                "vendorId": row.get("vendor_id", "").strip(),
                "name": row.get("name", "").strip(),
                "shortName": row.get("short_name", "").strip(),
                "email": row.get("email", "").strip(),
                "phone": row.get("phone", "").strip(),
                "address": {
                    "line1": row.get("address_line1", "").strip(),
                    "line2": row.get("address_line2", "").strip(),
                    "city": row.get("city", "").strip(),
                    "state": row.get("state", "").strip().upper(),
                    "zip": row.get("zip", "").strip(),
                    "country": row.get("country", "US").strip().upper(),
                },
                "paymentMethod": row.get("payment_method", "CHECK").strip().upper(),
                "paymentTermDays": int(row.get("payment_term_days", str(DEFAULT_PAYMENT_TERM_DAYS)) or DEFAULT_PAYMENT_TERM_DAYS),
                "taxId": row.get("tax_id", "").strip(),
            }
            vendors.append(vendor)

    _debug(f"Loaded {len(vendors)} vendors from CSV: {csv_path}")
    return vendors


def get_vendor_from_csv(vendor_id: str, csv_path: str = None) -> Optional[Dict[str, Any]]:
    """Get a single vendor from CSV by vendor_id."""
    csv_path = csv_path or VENDOR_CSV_PATH
    vendors = load_vendors_from_csv(csv_path)

    for vendor in vendors:
        if vendor.get("vendorId") == vendor_id:
            return vendor

    return None


# ---------- payload builders ----------
def build_us_vendor_payload(vendor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build BILL.com vendor payload for US vendor.

    BILL API v3 vendor payload format:
    {
        "name": "Vendor Name",
        "shortName": "VEND",
        "email": "vendor@example.com",
        "phone": "555-123-4567",
        "address": {
            "line1": "123 Main St",
            "line2": "Suite 100",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "country": "US"
        },
        "paymentTermDays": 30,
        "paymentMethod": "CHECK"
    }
    """
    address = vendor_data.get("address", {})

    payload = {
        "name": vendor_data.get("name", ""),
        "address": {
            "line1": address.get("line1", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "zip": address.get("zip", ""),
            "country": "US",
        },
        "paymentTermDays": vendor_data.get("paymentTermDays", DEFAULT_PAYMENT_TERM_DAYS),
        "paymentMethod": vendor_data.get("paymentMethod", "CHECK"),
    }

    # Optional fields
    if vendor_data.get("shortName"):
        payload["shortName"] = vendor_data["shortName"]

    if vendor_data.get("email"):
        payload["email"] = vendor_data["email"]

    if vendor_data.get("phone"):
        payload["phone"] = vendor_data["phone"]

    if address.get("line2"):
        payload["address"]["line2"] = address["line2"]

    if vendor_data.get("taxId"):
        payload["taxId"] = vendor_data["taxId"]

    return payload


def build_international_vendor_payload(vendor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build BILL.com vendor payload for international vendor.

    International vendors have different address requirements:
    - No state validation
    - Country code is required and must be valid ISO 3166-1 alpha-2
    - May require additional banking info for international payments
    """
    address = vendor_data.get("address", {})
    country = address.get("country", "").upper()

    payload = {
        "name": vendor_data.get("name", ""),
        "address": {
            "line1": address.get("line1", ""),
            "city": address.get("city", ""),
            "country": country,
        },
        "paymentTermDays": vendor_data.get("paymentTermDays", DEFAULT_PAYMENT_TERM_DAYS),
        "paymentMethod": vendor_data.get("paymentMethod", "WIRE"),  # Default to WIRE for international
    }

    # Optional fields
    if vendor_data.get("shortName"):
        payload["shortName"] = vendor_data["shortName"]

    if vendor_data.get("email"):
        payload["email"] = vendor_data["email"]

    if vendor_data.get("phone"):
        payload["phone"] = vendor_data["phone"]

    if address.get("line2"):
        payload["address"]["line2"] = address["line2"]

    # Postal code (international format may vary)
    if address.get("zip"):
        payload["address"]["zip"] = address["zip"]

    # State/Province (optional for international)
    if address.get("state"):
        payload["address"]["state"] = address["state"]

    return payload


def build_vendor_payload(vendor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build BILL.com vendor payload, auto-detecting US vs international.

    Args:
        vendor_data: Raw vendor data from source

    Returns:
        BILL.com API-compatible vendor payload
    """
    address = vendor_data.get("address", {})
    country = address.get("country", "US").upper()

    # Build appropriate payload based on country
    if country == "US":
        payload = build_us_vendor_payload(vendor_data)
    else:
        payload = build_international_vendor_payload(vendor_data)

    # Add external ID for upsert tracking
    if vendor_data.get("vendorId"):
        payload["externalId"] = vendor_data["vendorId"]

    # Validate payload
    validation = validate_vendor_payload(payload)
    if not validation.is_valid:
        _debug(f"Validation warnings for vendor {vendor_data.get('vendorId')}: {validation.errors}")

    _debug(f"Built vendor payload: {json.dumps(payload, indent=2)}")

    return payload


# ---------- main ----------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build BILL.com vendor payloads")
    parser.add_argument("vendor_id", nargs="?", help="Vendor ID to build payload for")
    parser.add_argument("--csv", dest="csv_path", help="CSV file path to load vendors from")
    parser.add_argument("--all", action="store_true", help="Build payloads for all vendors in CSV")
    args = parser.parse_args()

    csv_path = args.csv_path or VENDOR_CSV_PATH

    if args.all:
        # Build all vendors from CSV
        vendors = load_vendors_from_csv(csv_path)
        out_dir = Path("data/vendors")
        out_dir.mkdir(parents=True, exist_ok=True)

        for vendor_data in vendors:
            vendor_id = vendor_data.get("vendorId", "unknown")
            payload = build_vendor_payload(vendor_data)

            out_path = out_dir / f"vendor_{vendor_id}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"[INFO] Built vendor payload: {out_path}")

        print(f"[INFO] Built {len(vendors)} vendor payloads")

    elif args.vendor_id:
        # Build single vendor
        vendor_data = get_vendor_from_csv(args.vendor_id, csv_path)

        if not vendor_data:
            print(f"[ERROR] Vendor not found: {args.vendor_id}")
            sys.exit(1)

        payload = build_vendor_payload(vendor_data)

        out_dir = Path("data/vendors")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"vendor_{args.vendor_id}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(out_path)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
