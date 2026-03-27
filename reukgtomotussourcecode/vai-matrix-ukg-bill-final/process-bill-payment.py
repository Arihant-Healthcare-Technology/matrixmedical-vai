#!/usr/bin/env python3
"""
Process BILL.com payments via Accounts Payable API.
Handles single payments, bulk payments, and external payment recording.

IMPORTANT: Payment operations require MFA-trusted API sessions.

usage:
  python process-bill-payment.py --bill-id <bill_id> --amount <amount> [--dry-run]
  python process-bill-payment.py --bulk <json_file> [--dry-run]
  python process-bill-payment.py --record-external --bill-id <bill_id> --amount <amount> --date <date>

environment (.env example):
  BILL_API_BASE=https://gateway.stage.bill.com/connect/v3
  BILL_API_TOKEN=your-api-token
  BILL_FUNDING_ACCOUNT_ID=your-bank-account-id
  DEBUG=1
  MAX_RETRIES=2
"""
import os
import sys
import json
import time
from datetime import datetime
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
BILL_FUNDING_ACCOUNT_ID = _secrets.get_secret("BILL_FUNDING_ACCOUNT_ID") or os.getenv("BILL_FUNDING_ACCOUNT_ID", "")
DEBUG = (_secrets.get_secret("DEBUG") or os.getenv("DEBUG", "0")) == "1"
MAX_RETRIES = int(_secrets.get_secret("MAX_RETRIES") or os.getenv("MAX_RETRIES", "2"))

# Valid payment statuses
PAYMENT_STATUSES = {
    "PENDING": "Payment is pending approval",
    "APPROVED": "Payment approved, awaiting processing",
    "SCHEDULED": "Payment scheduled for future date",
    "PROCESSING": "Payment is being processed",
    "COMPLETED": "Payment completed successfully",
    "FAILED": "Payment failed",
    "CANCELLED": "Payment was cancelled",
    "VOIDED": "Payment was voided",
}


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
def bill_get_payment_options(bill_id: str) -> requests.Response:
    """Get available payment options for a bill."""
    url = f"{BILL_AP_API_BASE}/payments/options"
    params = {"billId": bill_id}
    _log(f"GET {url} billId={bill_id}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


def bill_create_payment(payload: Dict[str, Any]) -> requests.Response:
    """Create a single payment."""
    url = f"{BILL_AP_API_BASE}/payments"
    _log(f"POST {url}")
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json=payload, timeout=60)


def bill_create_bulk_payments(payments: List[Dict[str, Any]]) -> requests.Response:
    """Create bulk payments."""
    url = f"{BILL_AP_API_BASE}/payments/bulk"
    _log(f"POST {url} (bulk: {len(payments)} payments)")
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json={"payments": payments}, timeout=120)


def bill_record_external_payment(bill_id: str, amount: float, payment_date: str,
                                   reference: str = None) -> requests.Response:
    """Record an external payment that was made outside BILL."""
    url = f"{BILL_AP_API_BASE}/bills/record-payment"
    payload = {
        "billId": bill_id,
        "amount": amount,
        "paymentDate": payment_date,
    }
    if reference:
        payload["reference"] = reference
    _log(f"POST {url} billId={bill_id} amount={amount}")
    _rate_limiter.acquire()
    return requests.post(url, headers=headers(), json=payload, timeout=60)


def bill_get_payment_status(payment_id: str) -> requests.Response:
    """Get status of a payment."""
    url = f"{BILL_AP_API_BASE}/payments/{payment_id}"
    _log(f"GET {url}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), timeout=45)


def bill_list_payments(bill_id: str = None, status: str = None,
                        page: int = 1, page_size: int = 200) -> requests.Response:
    """List payments with optional filters."""
    url = f"{BILL_AP_API_BASE}/payments"
    params = {"page": page, "pageSize": page_size}
    if bill_id:
        params["billId"] = bill_id
    if status:
        params["status"] = status
    _log(f"GET {url} params={params}")
    _rate_limiter.acquire()
    return requests.get(url, headers=headers(), params=params, timeout=45)


# ---------- payment options ----------
def get_payment_options(bill_id: str) -> Dict[str, Any]:
    """
    Get available payment options for a bill.

    Returns dict with available payment methods and funding accounts.
    """
    resp = bill_get_payment_options(bill_id)
    if resp.status_code != 200:
        fail(resp)

    data = safe_json(resp)
    _log(f"Payment options for bill {bill_id}: {json.dumps(data, indent=2)}")
    return data


# ---------- payment processing ----------
def build_payment_payload(bill_id: str, amount: float,
                           process_date: str = None,
                           funding_account_id: str = None,
                           payment_method: str = None) -> Dict[str, Any]:
    """
    Build payment payload for BILL API.

    Args:
        bill_id: BILL bill ID to pay
        amount: Payment amount
        process_date: Date to process payment (YYYY-MM-DD), defaults to today
        funding_account_id: Funding account ID, defaults to BILL_FUNDING_ACCOUNT_ID
        payment_method: Payment method (CHECK, ACH, etc.), defaults based on vendor preference

    Returns:
        Payment payload dict
    """
    if not process_date:
        process_date = datetime.now().strftime("%Y-%m-%d")

    funding_account_id = funding_account_id or BILL_FUNDING_ACCOUNT_ID
    if not funding_account_id:
        raise ValueError("Missing funding account ID. Set BILL_FUNDING_ACCOUNT_ID or provide --funding-account")

    payload = {
        "billId": bill_id,
        "amount": float(amount),
        "processDate": process_date,
        "fundingAccount": {
            "type": "BANK_ACCOUNT",
            "id": funding_account_id,
        }
    }

    if payment_method:
        payload["paymentMethod"] = payment_method

    return payload


def process_single_payment(bill_id: str, amount: float,
                            process_date: str = None,
                            funding_account_id: str = None,
                            payment_method: str = None,
                            dry_run: bool = False) -> Dict[str, Any]:
    """
    Process a single payment for a bill.

    NOTE: Payment creation typically requires MFA verification.
    """
    payload = build_payment_payload(
        bill_id=bill_id,
        amount=amount,
        process_date=process_date,
        funding_account_id=funding_account_id,
        payment_method=payment_method,
    )

    if dry_run:
        result = {
            "dry_run": True,
            "action": "validate",
            "billId": bill_id,
            "amount": amount,
            "payload": payload,
        }
        print(json.dumps(result, indent=2))
        return result

    _log(f"POST payment payload: {json.dumps(sanitize_for_logging(payload), indent=2)}")

    for attempt in range(MAX_RETRIES + 1):
        resp = bill_create_payment(payload)

        if resp.status_code in (200, 201):
            body = safe_json(resp)
            payment_id = body.get("id")
            status = body.get("status", "UNKNOWN")
            result = {
                "action": "create",
                "status": resp.status_code,
                "id": payment_id,
                "paymentStatus": status,
                "billId": bill_id,
                "amount": amount,
            }
            print(json.dumps(result, indent=2))
            return result

        if resp.status_code == 403:
            # MFA required
            body = safe_json(resp)
            _log("MFA verification required for payment creation", level="error")
            raise SystemExit("Payment creation requires MFA verification. Please use BILL.com UI or ensure API session is MFA-trusted.")

        if resp.status_code >= 500 and attempt < MAX_RETRIES:
            _log(f"POST retry {attempt+1} after 5xx {resp.status_code}", level="warn")
            backoff_sleep(attempt)
            continue

        fail(resp)


def process_bulk_payments(payments: List[Dict[str, Any]],
                           dry_run: bool = False) -> Dict[str, Any]:
    """
    Process multiple payments in bulk.

    payments: List of dicts with billId, amount, and optional processDate, paymentMethod

    NOTE: Bulk payments fail entirely if any single payment is invalid.
    """
    payment_payloads = []
    for payment in payments:
        payload = build_payment_payload(
            bill_id=payment["billId"],
            amount=payment["amount"],
            process_date=payment.get("processDate"),
            funding_account_id=payment.get("fundingAccountId"),
            payment_method=payment.get("paymentMethod"),
        )
        payment_payloads.append(payload)

    if dry_run:
        result = {
            "dry_run": True,
            "action": "validate",
            "paymentCount": len(payment_payloads),
            "totalAmount": sum(p["amount"] for p in payment_payloads),
            "payments": payment_payloads,
        }
        print(json.dumps(result, indent=2))
        return result

    _log(f"POST bulk payments: {len(payment_payloads)} payments")

    for attempt in range(MAX_RETRIES + 1):
        resp = bill_create_bulk_payments(payment_payloads)

        if resp.status_code in (200, 201):
            body = safe_json(resp)
            results = body.get("results", [])
            success_count = sum(1 for r in results if r.get("status") in ("PENDING", "APPROVED", "SCHEDULED"))
            result = {
                "action": "bulk_create",
                "status": resp.status_code,
                "totalPayments": len(payment_payloads),
                "successCount": success_count,
                "results": results,
            }
            print(json.dumps(result, indent=2))
            return result

        if resp.status_code == 403:
            _log("MFA verification required for bulk payment creation", level="error")
            raise SystemExit("Bulk payment creation requires MFA verification.")

        if resp.status_code >= 500 and attempt < MAX_RETRIES:
            _log(f"POST retry {attempt+1} after 5xx {resp.status_code}", level="warn")
            backoff_sleep(attempt)
            continue

        fail(resp)


def record_external_payment(bill_id: str, amount: float, payment_date: str,
                             reference: str = None,
                             dry_run: bool = False) -> Dict[str, Any]:
    """
    Record an external payment that was made outside BILL.

    This is useful for payments made via check, wire, or other methods
    that were processed externally.
    """
    if dry_run:
        result = {
            "dry_run": True,
            "action": "validate",
            "billId": bill_id,
            "amount": amount,
            "paymentDate": payment_date,
            "reference": reference,
        }
        print(json.dumps(result, indent=2))
        return result

    for attempt in range(MAX_RETRIES + 1):
        resp = bill_record_external_payment(bill_id, amount, payment_date, reference)

        if resp.status_code in (200, 201, 204):
            body = safe_json(resp) if resp.status_code != 204 else {}
            result = {
                "action": "record_external",
                "status": resp.status_code,
                "billId": bill_id,
                "amount": amount,
                "paymentDate": payment_date,
            }
            if body.get("id"):
                result["id"] = body["id"]
            print(json.dumps(result, indent=2))
            return result

        if resp.status_code >= 500 and attempt < MAX_RETRIES:
            _log(f"POST retry {attempt+1} after 5xx {resp.status_code}", level="warn")
            backoff_sleep(attempt)
            continue

        fail(resp)


# ---------- payment tracking ----------
def get_payment_status_info(payment_id: str) -> Dict[str, Any]:
    """Get current status of a payment."""
    resp = bill_get_payment_status(payment_id)
    if resp.status_code != 200:
        fail(resp)

    data = safe_json(resp)
    status = data.get("status", "UNKNOWN")
    status_desc = PAYMENT_STATUSES.get(status, "Unknown status")

    return {
        "id": payment_id,
        "status": status,
        "statusDescription": status_desc,
        "data": data,
    }


def get_payments_for_bill(bill_id: str) -> List[Dict[str, Any]]:
    """Get all payments for a specific bill."""
    resp = bill_list_payments(bill_id=bill_id)
    if resp.status_code != 200:
        fail(resp)

    data = safe_json(resp)
    if isinstance(data, list):
        return data
    return data.get("payments", data.get("items", data.get("results", [])))


# ---------- main ----------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Process BILL.com payments")
    parser.add_argument("--bill-id", dest="bill_id", help="Bill ID to pay")
    parser.add_argument("--amount", type=float, help="Payment amount")
    parser.add_argument("--process-date", dest="process_date", help="Process date (YYYY-MM-DD)")
    parser.add_argument("--funding-account", dest="funding_account", help="Funding account ID")
    parser.add_argument("--payment-method", dest="payment_method",
                        choices=["CHECK", "ACH", "WIRE", "CARD_ACCOUNT"],
                        help="Payment method")

    parser.add_argument("--bulk", dest="bulk_file", help="JSON file with bulk payment data")

    parser.add_argument("--record-external", dest="record_external", action="store_true",
                        help="Record external payment (made outside BILL)")
    parser.add_argument("--date", dest="payment_date", help="Payment date for external payment")
    parser.add_argument("--reference", help="Reference number for external payment")

    parser.add_argument("--status", dest="check_status", help="Check status of payment ID")
    parser.add_argument("--list-payments", dest="list_payments", action="store_true",
                        help="List payments for --bill-id")

    parser.add_argument("--options", action="store_true", help="Show payment options for --bill-id")

    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Validate without making API calls")

    args = parser.parse_args()

    # Payment options
    if args.options:
        if not args.bill_id:
            print("[ERROR] --bill-id required with --options")
            sys.exit(1)
        options = get_payment_options(args.bill_id)
        print(json.dumps(options, indent=2))

    # Check payment status
    elif args.check_status:
        status_info = get_payment_status_info(args.check_status)
        print(json.dumps(status_info, indent=2))

    # List payments for a bill
    elif args.list_payments:
        if not args.bill_id:
            print("[ERROR] --bill-id required with --list-payments")
            sys.exit(1)
        payments = get_payments_for_bill(args.bill_id)
        print(json.dumps(payments, indent=2))

    # Bulk payments
    elif args.bulk_file:
        bulk_path = Path(args.bulk_file)
        if not bulk_path.exists():
            print(f"[ERROR] Bulk file not found: {args.bulk_file}")
            sys.exit(1)

        with bulk_path.open("r", encoding="utf-8") as f:
            bulk_data = json.load(f)

        payments = bulk_data if isinstance(bulk_data, list) else bulk_data.get("payments", [])
        result = process_bulk_payments(payments, dry_run=args.dry_run)
        print(f"\n[INFO] Bulk payment result: {result.get('successCount', 0)}/{result.get('totalPayments', 0)} succeeded")

    # Record external payment
    elif args.record_external:
        if not args.bill_id or not args.amount or not args.payment_date:
            print("[ERROR] --bill-id, --amount, and --date required with --record-external")
            sys.exit(1)
        result = record_external_payment(
            bill_id=args.bill_id,
            amount=args.amount,
            payment_date=args.payment_date,
            reference=args.reference,
            dry_run=args.dry_run,
        )
        print(f"\n[INFO] Result: {result}")

    # Single payment
    elif args.bill_id and args.amount:
        result = process_single_payment(
            bill_id=args.bill_id,
            amount=args.amount,
            process_date=args.process_date,
            funding_account_id=args.funding_account,
            payment_method=args.payment_method,
            dry_run=args.dry_run,
        )
        print(f"\n[INFO] Result: {result}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
