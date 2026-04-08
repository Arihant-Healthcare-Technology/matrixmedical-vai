#!/usr/bin/env python3
"""
BILL.com Accounts Payable Batch Orchestrator.

Orchestrates the full AP workflow:
1. Vendor sync (create/update vendors)
2. Bill/Invoice sync (create/update bills)
3. Payment processing (optional)

usage:
  python run-ap-batch.py --vendors --bills [--payments] [--dry-run]
  python run-ap-batch.py --vendors-csv data/vendors.csv [--dry-run]
  python run-ap-batch.py --bills-csv data/invoices.csv [--dry-run]

environment (.env example):
  BILL_API_BASE=https://gateway.stage.bill.com/connect/v3
  BILL_API_TOKEN=your-api-token
  VENDOR_CSV_PATH=data/vendors.csv
  INVOICE_CSV_PATH=data/invoices.csv
  DEBUG=1

DEPRECATED: This script is deprecated and will be removed in a future version.
            Use 'ukg-bill ap batch' CLI command instead.
            Run 'ukg-bill --help' for available commands.
"""
import warnings

warnings.warn(
    "run-ap-batch.py is deprecated and will be removed in a future version. "
    "Use 'ukg-bill ap batch' CLI command instead. "
    "Run 'ukg-bill --help' for available commands.",
    DeprecationWarning,
    stacklevel=2
)

import os
import sys
import json
import logging
import importlib.util
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import argparse
from dotenv import load_dotenv

from common import (
    # Correlation IDs & Logging (SOW 7.2)
    RunContext,
    configure_logging,
    get_logger,
    # Notifications (SOW 4.6)
    get_notifier,
    # Report Generation (SOW 4.7, 7.3)
    ReportGenerator,
    # Rate Limiting (SOW 5.1, 5.2)
    get_rate_limiter,
    # PII Redaction (SOW 7.4, 7.5, 9.4)
    RedactingFilter,
)

# Load environment variables from .env file
load_dotenv()

# Initialize logging with correlation support
configure_logging(include_module=True)
_logger = get_logger(__name__)

# Add redaction filter to all handlers
for handler in logging.root.handlers:
    handler.addFilter(RedactingFilter())

HERE = Path(__file__).resolve().parent


# ---------- module loaders ----------
def load_vendor_builder():
    """Load build-bill-vendor module."""
    vendor_builder_path = HERE / "build-bill-vendor.py"
    if not vendor_builder_path.exists():
        raise SystemExit(f"Vendor builder not found: {vendor_builder_path}")
    spec = importlib.util.spec_from_file_location("vendor_builder", str(vendor_builder_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_vendor_upserter():
    """Load upsert-bill-vendor module."""
    vendor_upserter_path = HERE / "upsert-bill-vendor.py"
    if not vendor_upserter_path.exists():
        raise SystemExit(f"Vendor upserter not found: {vendor_upserter_path}")
    spec = importlib.util.spec_from_file_location("vendor_upserter", str(vendor_upserter_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_invoice_builder():
    """Load build-bill-invoice module."""
    invoice_builder_path = HERE / "build-bill-invoice.py"
    if not invoice_builder_path.exists():
        raise SystemExit(f"Invoice builder not found: {invoice_builder_path}")
    spec = importlib.util.spec_from_file_location("invoice_builder", str(invoice_builder_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_invoice_upserter():
    """Load upsert-bill-invoice module."""
    invoice_upserter_path = HERE / "upsert-bill-invoice.py"
    if not invoice_upserter_path.exists():
        raise SystemExit(f"Invoice upserter not found: {invoice_upserter_path}")
    spec = importlib.util.spec_from_file_location("invoice_upserter", str(invoice_upserter_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_payment_processor():
    """Load process-bill-payment module."""
    payment_path = HERE / "process-bill-payment.py"
    if not payment_path.exists():
        raise SystemExit(f"Payment processor not found: {payment_path}")
    spec = importlib.util.spec_from_file_location("payment_processor", str(payment_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- CLI parsing ----------
def parse_args():
    parser = argparse.ArgumentParser(
        description="BILL.com Accounts Payable Batch Orchestrator"
    )

    # Process types
    parser.add_argument("--vendors", action="store_true",
                        help="Process vendors from CSV")
    parser.add_argument("--bills", action="store_true",
                        help="Process bills/invoices from CSV")
    parser.add_argument("--payments", action="store_true",
                        help="Process payments (requires MFA-trusted session)")

    # Data sources
    parser.add_argument("--vendors-csv", dest="vendors_csv",
                        help="Path to vendors CSV file")
    parser.add_argument("--bills-csv", dest="bills_csv",
                        help="Path to bills/invoices CSV file")
    parser.add_argument("--payments-json", dest="payments_json",
                        help="Path to payments JSON file")

    # Output directories
    parser.add_argument("--vendor-dir", dest="vendor_dir", default="data/vendors",
                        help="Output directory for vendor payloads")
    parser.add_argument("--bill-dir", dest="bill_dir", default="data/bills",
                        help="Output directory for bill payloads")
    parser.add_argument("--report-dir", dest="report_dir", default="data/reports",
                        help="Output directory for reports")

    # Options
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Validate without making API calls")
    parser.add_argument("--limit", type=int,
                        help="Limit number of records to process")
    parser.add_argument("--no-notify", dest="no_notify", action="store_true",
                        help="Disable email notifications")

    return parser.parse_args()


# ---------- batch processing ----------
def process_vendors(ctx: RunContext, args) -> Dict[str, str]:
    """
    Process vendors: build payloads and upsert to BILL.

    Returns mapping: external_vendor_id -> BILL vendor_id
    """
    _logger.info("Starting vendor processing")

    vendor_builder = load_vendor_builder()
    vendor_upserter = load_vendor_upserter()

    csv_path = args.vendors_csv or os.getenv("VENDOR_CSV_PATH", "data/vendors.csv")
    vendor_dir = Path(args.vendor_dir)
    vendor_dir.mkdir(parents=True, exist_ok=True)

    # Load vendors from CSV
    try:
        vendors = vendor_builder.load_vendors_from_csv(csv_path)
    except FileNotFoundError:
        _logger.warning(f"Vendor CSV not found: {csv_path}")
        return {}

    if args.limit:
        vendors = vendors[:args.limit]

    _logger.info(f"Processing {len(vendors)} vendors")

    # Build and upsert vendors
    vendor_mapping = {}
    success = errors = 0

    for vendor_data in vendors:
        vendor_id = vendor_data.get("vendorId", "unknown")
        try:
            # Build payload
            payload = vendor_builder.build_vendor_payload(vendor_data)

            # Save payload
            out_path = vendor_dir / f"vendor_{vendor_id}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            # Upsert to BILL
            result = vendor_upserter.upsert_vendor_payload(payload, dry_run=args.dry_run)

            if result.get("id"):
                vendor_mapping[vendor_id] = result["id"]
                ctx.stats["created"] += 1
                success += 1
            else:
                ctx.stats["skipped"] += 1

        except Exception as e:
            _logger.error(f"Error processing vendor {vendor_id}: {e}")
            ctx.record_error(f"vendor:{vendor_id}", str(e))
            ctx.stats["errors"] += 1
            errors += 1

        ctx.stats["total_processed"] += 1

    # Save vendor mapping
    if vendor_mapping:
        mapping_path = vendor_dir / "vendor_id_mapping.json"
        with mapping_path.open("w", encoding="utf-8") as f:
            json.dump(vendor_mapping, f, indent=2)
        _logger.info(f"Saved vendor mapping to {mapping_path}")

    _logger.info(f"Vendor processing complete: {success} success, {errors} errors")
    return vendor_mapping


def process_bills(ctx: RunContext, args, vendor_mapping: Dict[str, str] = None) -> Dict[str, str]:
    """
    Process bills/invoices: build payloads and upsert to BILL.

    Returns mapping: invoice_number -> BILL bill_id
    """
    _logger.info("Starting bill processing")

    invoice_builder = load_invoice_builder()
    invoice_upserter = load_invoice_upserter()

    csv_path = args.bills_csv or os.getenv("INVOICE_CSV_PATH", "data/invoices.csv")
    bill_dir = Path(args.bill_dir)
    bill_dir.mkdir(parents=True, exist_ok=True)

    # Load vendor mapping if not provided
    if vendor_mapping is None:
        vendor_mapping = invoice_builder.load_vendor_mapping()

    # Load invoices from CSV
    try:
        invoices = invoice_builder.load_invoices_from_csv(csv_path)
    except FileNotFoundError:
        _logger.warning(f"Invoice CSV not found: {csv_path}")
        return {}

    if args.limit:
        invoices = invoices[:args.limit]

    _logger.info(f"Processing {len(invoices)} bills/invoices")

    # Build and upsert bills
    bill_mapping = {}
    success = errors = 0

    for invoice_data in invoices:
        invoice_number = invoice_data.get("invoiceNumber", "unknown")
        try:
            # Build payload
            payload = invoice_builder.build_bill_payload(invoice_data, vendor_mapping)

            # Save payload
            safe_name = invoice_number.replace("/", "_").replace("\\", "_")
            out_path = bill_dir / f"bill_{safe_name}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            # Upsert to BILL
            result = invoice_upserter.upsert_bill_payload(payload, dry_run=args.dry_run)

            if result.get("id"):
                bill_mapping[invoice_number] = result["id"]
                ctx.stats["created"] += 1
                success += 1
            else:
                ctx.stats["skipped"] += 1

        except Exception as e:
            _logger.error(f"Error processing bill {invoice_number}: {e}")
            ctx.record_error(f"bill:{invoice_number}", str(e))
            ctx.stats["errors"] += 1
            errors += 1

        ctx.stats["total_processed"] += 1

    # Save bill mapping
    if bill_mapping:
        mapping_path = bill_dir / "bill_id_mapping.json"
        with mapping_path.open("w", encoding="utf-8") as f:
            json.dump(bill_mapping, f, indent=2)
        _logger.info(f"Saved bill mapping to {mapping_path}")

    _logger.info(f"Bill processing complete: {success} success, {errors} errors")
    return bill_mapping


def process_payments(ctx: RunContext, args) -> List[Dict[str, Any]]:
    """
    Process payments from JSON file.

    NOTE: Payment creation requires MFA-trusted API session.
    """
    _logger.info("Starting payment processing")
    _logger.warning("Payment processing requires MFA-trusted API session")

    payment_processor = load_payment_processor()

    payments_json = args.payments_json or os.getenv("PAYMENTS_JSON_PATH", "data/payments.json")
    payments_path = Path(payments_json)

    if not payments_path.exists():
        _logger.warning(f"Payments JSON not found: {payments_json}")
        return []

    with payments_path.open("r", encoding="utf-8") as f:
        payments_data = json.load(f)

    payments = payments_data if isinstance(payments_data, list) else payments_data.get("payments", [])

    if args.limit:
        payments = payments[:args.limit]

    _logger.info(f"Processing {len(payments)} payments")

    results = []
    success = errors = 0

    for payment in payments:
        bill_id = payment.get("billId", "unknown")
        try:
            result = payment_processor.process_single_payment(
                bill_id=payment["billId"],
                amount=payment["amount"],
                process_date=payment.get("processDate"),
                funding_account_id=payment.get("fundingAccountId"),
                payment_method=payment.get("paymentMethod"),
                dry_run=args.dry_run,
            )
            results.append(result)

            if result.get("id"):
                ctx.stats["created"] += 1
                success += 1
            else:
                ctx.stats["skipped"] += 1

        except SystemExit as e:
            # MFA required or other critical error
            _logger.error(f"Payment error for bill {bill_id}: {e}")
            ctx.record_error(f"payment:{bill_id}", str(e))
            ctx.stats["errors"] += 1
            errors += 1
            # Don't continue with more payments if MFA is required
            if "MFA" in str(e):
                _logger.error("Stopping payment processing due to MFA requirement")
                break

        except Exception as e:
            _logger.error(f"Error processing payment for bill {bill_id}: {e}")
            ctx.record_error(f"payment:{bill_id}", str(e))
            ctx.stats["errors"] += 1
            errors += 1

        ctx.stats["total_processed"] += 1

    _logger.info(f"Payment processing complete: {success} success, {errors} errors")
    return results


# ---------- main orchestrator ----------
def run_ap_batch():
    """Main AP batch processing with RunContext, notifications, and reporting."""
    args = parse_args()

    # Validate at least one process type selected
    if not (args.vendors or args.bills or args.payments):
        print("[ERROR] Specify at least one: --vendors, --bills, or --payments")
        sys.exit(1)

    # Initialize notifier (optional)
    notifier = None
    if not args.no_notify:
        try:
            notifier = get_notifier()
            _logger.info("Email notifications enabled")
        except Exception as e:
            _logger.warning(f"Notifications disabled: {e}")

    # Initialize report generator
    report_gen = ReportGenerator(output_dir=args.report_dir)

    print("\n" + "=" * 60)
    print("BILL.com Accounts Payable - Batch Processor")
    print("=" * 60)
    print(f"Vendors: {'YES' if args.vendors else 'NO'}")
    print(f"Bills: {'YES' if args.bills else 'NO'}")
    print(f"Payments: {'YES' if args.payments else 'NO'}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Limit: {args.limit or 'None'}")
    print("=" * 60 + "\n")

    # Wrap batch in RunContext
    with RunContext(project="bill-ap", company_id="AP") as ctx:
        _logger.info("Starting BILL AP batch processing")
        _logger.info(f"Correlation ID: {ctx.correlation_id}")
        _logger.info(f"Run ID: {ctx.run_id}")

        vendor_mapping = {}
        bill_mapping = {}
        payment_results = []

        try:
            # Step 1: Process vendors
            if args.vendors:
                vendor_mapping = process_vendors(ctx, args)

            # Step 2: Process bills (uses vendor mapping)
            if args.bills:
                bill_mapping = process_bills(ctx, args, vendor_mapping)

            # Step 3: Process payments
            if args.payments:
                payment_results = process_payments(ctx, args)

        except Exception as e:
            _logger.error(f"Batch execution failed: {e}")
            ctx.record_error("batch", str(e))

            if notifier:
                notifier.send_critical_alert(
                    title="BILL AP Batch Failed",
                    error=e,
                    context={
                        "correlation_id": ctx.correlation_id,
                    }
                )
            raise

        # Generate reports
        _logger.info("Generating reports...")
        run_data = ctx.to_dict()

        # Add AP-specific data
        run_data["ap_summary"] = {
            "vendors_processed": len(vendor_mapping),
            "bills_processed": len(bill_mapping),
            "payments_processed": len(payment_results),
        }

        report_paths = report_gen.generate_run_report(run_data)
        _logger.info(f"Reports generated: {report_paths}")

        # Generate validation report
        validation = report_gen.generate_validation_report(
            run_data,
            target_success_rate=99.0
        )
        _logger.info(f"Validation: passed={validation['passed']}, success_rate={validation['success_rate']:.2f}%")

        # Send notification
        if notifier:
            _logger.info("Sending run summary notification...")
            notifier.send_run_summary(run_data)

        # Print summary
        print("\n" + "=" * 60)
        print("RUN SUMMARY - BILL AP")
        print("=" * 60)
        print(f"Correlation ID: {ctx.correlation_id}")
        print(f"Run ID: {ctx.run_id}")
        print(f"Duration: {ctx.duration_seconds:.2f} seconds")
        print(f"Success Rate: {ctx.success_rate:.1f}%")
        print("-" * 60)
        print(f"Total Processed: {ctx.stats['total_processed']}")
        print(f"Created/Updated: {ctx.stats['created']}")
        print(f"Skipped: {ctx.stats['skipped']}")
        print(f"Errors: {ctx.stats['errors']}")
        print("-" * 60)
        print(f"Vendors: {len(vendor_mapping)}")
        print(f"Bills: {len(bill_mapping)}")
        print(f"Payments: {len(payment_results)}")
        print("-" * 60)
        print(f"Reports: {report_paths}")
        print(f"Validation Passed: {validation['passed']}")
        print("=" * 60)

        return ctx.success_rate >= 99.0


if __name__ == "__main__":
    try:
        success = run_ap_batch()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        sys.exit(1)
