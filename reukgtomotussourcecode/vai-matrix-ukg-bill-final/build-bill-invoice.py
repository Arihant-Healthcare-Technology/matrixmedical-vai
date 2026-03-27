#!/usr/bin/env python3
"""
Build BILL.com AP Bill/Invoice payloads from source data.

This module creates bill payloads for the BILL.com Accounts Payable API.
Bills can be sourced from CSV files, accounting systems, or external data.

usage:
  python build-bill-invoice.py <invoice_number>
  python build-bill-invoice.py --csv <csv_file>
  python build-bill-invoice.py --all

environment (.env example):
  INVOICE_DATA_SOURCE=csv
  INVOICE_CSV_PATH=data/invoices.csv
  VENDOR_MAPPING_PATH=data/vendors/vendor_id_mapping.json
  DEBUG=1
"""
import os
import sys
import json
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, List
from pathlib import Path

from common import (
    get_secrets_manager,
    validate_required,
    validate_date_string,
    ValidationResult,
    ValidationResults,
)

# ---------- config ----------
_secrets = get_secrets_manager()

INVOICE_DATA_SOURCE = _secrets.get_secret("INVOICE_DATA_SOURCE") or os.getenv("INVOICE_DATA_SOURCE", "csv")
INVOICE_CSV_PATH = _secrets.get_secret("INVOICE_CSV_PATH") or os.getenv("INVOICE_CSV_PATH", "data/invoices.csv")
VENDOR_MAPPING_PATH = _secrets.get_secret("VENDOR_MAPPING_PATH") or os.getenv("VENDOR_MAPPING_PATH", "data/vendors/vendor_id_mapping.json")
DEBUG = (_secrets.get_secret("DEBUG") or os.getenv("DEBUG", "0")) == "1"

# Default payment terms in days
DEFAULT_PAYMENT_TERM_DAYS = 30


def _debug(msg: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {msg}")


# ---------- validation ----------
def validate_bill_payload(payload: Dict[str, Any]) -> ValidationResults:
    """
    Validate bill payload has required fields and valid data.

    Required fields:
    - vendorId: BILL vendor ID (required)
    - invoice.number: Invoice number (required)
    - invoice.date: Invoice date (required)
    - dueDate: Payment due date (required)
    - billLineItems: At least one line item (required)

    Returns ValidationResults with all validation errors.
    """
    results = ValidationResults()

    # Required: vendorId
    vendor_id_result = validate_required(payload.get("vendorId"), "vendorId")
    results.add(vendor_id_result)

    # Required: invoice.number
    invoice = payload.get("invoice", {})
    invoice_number_result = validate_required(invoice.get("number"), "invoice.number")
    results.add(invoice_number_result)

    # Required: invoice.date
    invoice_date = invoice.get("date")
    if invoice_date:
        date_result = validate_date_string(invoice_date)
        results.add(date_result)
    else:
        results.add(ValidationResult(
            valid=False,
            field="invoice.date",
            value=None,
            message="Invoice date is required"
        ))

    # Required: dueDate
    due_date = payload.get("dueDate")
    if due_date:
        due_date_result = validate_date_string(due_date)
        results.add(due_date_result)
    else:
        results.add(ValidationResult(
            valid=False,
            field="dueDate",
            value=None,
            message="Due date is required"
        ))

    # Required: at least one line item
    line_items = payload.get("billLineItems", [])
    if not line_items:
        results.add(ValidationResult(
            valid=False,
            field="billLineItems",
            value=None,
            message="At least one line item is required"
        ))
    else:
        # Validate each line item
        for i, item in enumerate(line_items):
            amount = item.get("amount")
            if amount is None:
                results.add(ValidationResult(
                    valid=False,
                    field=f"billLineItems[{i}].amount",
                    value=None,
                    message=f"Line item {i} is missing amount"
                ))
            elif not isinstance(amount, (int, float, Decimal)) or amount < 0:
                results.add(ValidationResult(
                    valid=False,
                    field=f"billLineItems[{i}].amount",
                    value=amount,
                    message=f"Line item {i} has invalid amount: {amount}"
                ))

    return results


# ---------- vendor mapping ----------
def load_vendor_mapping(mapping_path: str = None) -> Dict[str, str]:
    """
    Load vendor ID mapping from JSON file.

    Returns dict: external_vendor_id -> BILL vendor_id
    """
    path = Path(mapping_path or VENDOR_MAPPING_PATH)

    if not path.exists():
        _debug(f"Vendor mapping file not found: {path}")
        return {}

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_vendor_id(vendor_identifier: str, vendor_mapping: Dict[str, str]) -> Optional[str]:
    """
    Resolve vendor identifier to BILL vendor ID.

    Args:
        vendor_identifier: Either BILL vendor ID or external vendor ID
        vendor_mapping: Mapping from external IDs to BILL IDs

    Returns:
        BILL vendor ID or None if not found
    """
    # Check if it's already a BILL ID (UUID format)
    if len(vendor_identifier) == 36 and vendor_identifier.count("-") == 4:
        return vendor_identifier

    # Look up in mapping
    return vendor_mapping.get(vendor_identifier)


# ---------- data extraction ----------
def load_invoices_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load invoice data from CSV file.

    Expected CSV columns:
    - invoice_number (required)
    - vendor_id (required) - external vendor ID or BILL vendor ID
    - invoice_date (required) - YYYY-MM-DD
    - due_date (optional) - YYYY-MM-DD, calculated from payment_term_days if not provided
    - payment_term_days (optional) - defaults to 30
    - amount (required) - total amount
    - description (optional)
    - line_items (optional) - JSON string of line items
    - gl_account (optional) - GL account code
    - department (optional)
    - po_number (optional) - purchase order number
    """
    invoices = []
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"Invoice CSV file not found: {csv_path}")

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse line items if provided
            line_items_json = row.get("line_items", "").strip()
            if line_items_json:
                try:
                    line_items = json.loads(line_items_json)
                except json.JSONDecodeError:
                    line_items = None
            else:
                line_items = None

            # If no line items provided, create single line item from amount
            if not line_items:
                amount = float(row.get("amount", "0") or "0")
                description = row.get("description", "").strip()
                line_items = [{"amount": amount, "description": description or "Invoice payment"}]

            # Calculate due date if not provided
            invoice_date_str = row.get("invoice_date", "").strip()
            due_date_str = row.get("due_date", "").strip()
            payment_term_days = int(row.get("payment_term_days", str(DEFAULT_PAYMENT_TERM_DAYS)) or DEFAULT_PAYMENT_TERM_DAYS)

            if not due_date_str and invoice_date_str:
                try:
                    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                    due_date = invoice_date + timedelta(days=payment_term_days)
                    due_date_str = due_date.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            invoice = {
                "invoiceNumber": row.get("invoice_number", "").strip(),
                "vendorId": row.get("vendor_id", "").strip(),
                "invoiceDate": invoice_date_str,
                "dueDate": due_date_str,
                "lineItems": line_items,
                "glAccount": row.get("gl_account", "").strip(),
                "department": row.get("department", "").strip(),
                "poNumber": row.get("po_number", "").strip(),
            }
            invoices.append(invoice)

    _debug(f"Loaded {len(invoices)} invoices from CSV: {csv_path}")
    return invoices


def get_invoice_from_csv(invoice_number: str, csv_path: str = None) -> Optional[Dict[str, Any]]:
    """Get a single invoice from CSV by invoice_number."""
    csv_path = csv_path or INVOICE_CSV_PATH
    invoices = load_invoices_from_csv(csv_path)

    for invoice in invoices:
        if invoice.get("invoiceNumber") == invoice_number:
            return invoice

    return None


# ---------- payload builders ----------
def build_bill_payload(invoice_data: Dict[str, Any],
                        vendor_mapping: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Build BILL.com bill payload from invoice data.

    BILL API v3 bill payload format:
    {
        "vendorId": "uuid",
        "invoice": {
            "number": "INV-001",
            "date": "2026-03-22"
        },
        "dueDate": "2026-04-22",
        "billLineItems": [
            {
                "amount": 1000.00,
                "description": "Services rendered",
                "glAccountId": "optional-gl-account-id"
            }
        ]
    }
    """
    vendor_mapping = vendor_mapping or {}

    # Resolve vendor ID
    vendor_identifier = invoice_data.get("vendorId", "")
    vendor_id = resolve_vendor_id(vendor_identifier, vendor_mapping)

    if not vendor_id:
        raise ValueError(f"Cannot resolve vendor ID: {vendor_identifier}")

    # Build line items
    line_items = []
    for item in invoice_data.get("lineItems", []):
        line_item = {
            "amount": float(item.get("amount", 0)),
        }
        if item.get("description"):
            line_item["description"] = item["description"]
        if item.get("glAccountId"):
            line_item["glAccountId"] = item["glAccountId"]
        if item.get("departmentId"):
            line_item["departmentId"] = item["departmentId"]
        line_items.append(line_item)

    payload = {
        "vendorId": vendor_id,
        "invoice": {
            "number": invoice_data.get("invoiceNumber", ""),
            "date": invoice_data.get("invoiceDate", ""),
        },
        "dueDate": invoice_data.get("dueDate", ""),
        "billLineItems": line_items,
    }

    # Optional fields
    if invoice_data.get("poNumber"):
        payload["poNumber"] = invoice_data["poNumber"]

    # Add external ID for upsert tracking
    if invoice_data.get("invoiceNumber"):
        payload["externalId"] = invoice_data["invoiceNumber"]

    # Validate payload
    validation = validate_bill_payload(payload)
    if not validation.is_valid:
        errors = [f"{e.field}: {e.message}" for e in validation.errors if not e.valid]
        _debug(f"Validation errors for invoice {invoice_data.get('invoiceNumber')}: {errors}")
        if any(e.field in ("vendorId", "invoice.number", "billLineItems") for e in validation.errors if not e.valid):
            raise ValueError(f"Critical validation errors: {errors}")

    _debug(f"Built bill payload: {json.dumps(payload, indent=2)}")

    return payload


# ---------- main ----------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build BILL.com bill payloads")
    parser.add_argument("invoice_number", nargs="?", help="Invoice number to build payload for")
    parser.add_argument("--csv", dest="csv_path", help="CSV file path to load invoices from")
    parser.add_argument("--vendor-mapping", dest="vendor_mapping_path",
                        help="Path to vendor ID mapping JSON file")
    parser.add_argument("--all", action="store_true", help="Build payloads for all invoices in CSV")
    args = parser.parse_args()

    csv_path = args.csv_path or INVOICE_CSV_PATH
    vendor_mapping_path = args.vendor_mapping_path or VENDOR_MAPPING_PATH

    # Load vendor mapping
    vendor_mapping = load_vendor_mapping(vendor_mapping_path)
    _debug(f"Loaded {len(vendor_mapping)} vendor mappings")

    if args.all:
        # Build all invoices from CSV
        invoices = load_invoices_from_csv(csv_path)
        out_dir = Path("data/bills")
        out_dir.mkdir(parents=True, exist_ok=True)

        success = 0
        errors = 0
        for invoice_data in invoices:
            invoice_number = invoice_data.get("invoiceNumber", "unknown")
            try:
                payload = build_bill_payload(invoice_data, vendor_mapping)

                # Sanitize filename
                safe_name = invoice_number.replace("/", "_").replace("\\", "_")
                out_path = out_dir / f"bill_{safe_name}.json"
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                print(f"[INFO] Built bill payload: {out_path}")
                success += 1
            except Exception as e:
                print(f"[ERROR] Failed to build bill for {invoice_number}: {e}")
                errors += 1

        print(f"\n[INFO] Built {success} bill payloads ({errors} errors)")

    elif args.invoice_number:
        # Build single invoice
        invoice_data = get_invoice_from_csv(args.invoice_number, csv_path)

        if not invoice_data:
            print(f"[ERROR] Invoice not found: {args.invoice_number}")
            sys.exit(1)

        try:
            payload = build_bill_payload(invoice_data, vendor_mapping)

            out_dir = Path("data/bills")
            out_dir.mkdir(parents=True, exist_ok=True)

            safe_name = args.invoice_number.replace("/", "_").replace("\\", "_")
            out_path = out_dir / f"bill_{safe_name}.json"

            with out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            print(out_path)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
