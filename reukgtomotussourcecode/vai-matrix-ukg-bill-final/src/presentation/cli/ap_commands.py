"""
AP commands for Accounts Payable operations.

Provides CLI handlers for:
- Vendor synchronization
- Invoice/bill management
- Payment processing
- Full AP batch operations
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.domain.models.vendor import Vendor
from src.domain.models.invoice import Invoice
from src.presentation.cli.container import Container
from src.presentation.cli.utils import (
    format_currency,
    load_json_file,
    print_preview,
    print_step_header,
    print_summary,
    print_sync_result,
)


logger = logging.getLogger(__name__)


def run_vendor_sync(
    container: Container,
    vendor_file: Optional[str] = None,
    workers: int = 8,
    dry_run: bool = False,
) -> int:
    """
    Sync vendors to BILL.com.

    Args:
        container: DI container.
        vendor_file: Path to JSON file with vendor data.
        workers: Number of concurrent workers.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting vendor sync to BILL.com AP")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    try:
        if not vendor_file:
            logger.error("Vendor file is required for vendor sync")
            return 1

        # Load vendors from file
        vendors = _load_vendors_from_file(vendor_file)
        logger.info(f"Loaded {len(vendors)} vendors from file")

        if dry_run:
            print_preview(vendors, "vendors to sync")
            return 0

        vendor_service = container.vendor_service()

        # Run batch sync
        result = vendor_service.sync_batch(
            vendors=vendors,
            workers=workers,
        )

        print_sync_result(result, "VENDOR SYNC")
        return 0 if result.errors == 0 else 1

    except FileNotFoundError:
        logger.error(f"File not found: {vendor_file}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {vendor_file}: {e}")
        return 1
    except Exception as e:
        logger.error(f"Vendor sync failed: {e}")
        return 1


def run_invoice_sync(
    container: Container,
    invoice_file: Optional[str] = None,
    vendor_mapping_file: Optional[str] = None,
    workers: int = 8,
    dry_run: bool = False,
) -> int:
    """
    Sync invoices/bills to BILL.com.

    Args:
        container: DI container.
        invoice_file: Path to JSON file with invoice data.
        vendor_mapping_file: Path to JSON file with vendor ID mappings.
        workers: Number of concurrent workers.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting invoice sync to BILL.com AP")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    try:
        if not invoice_file:
            logger.error("Invoice file is required for invoice sync")
            return 1

        # Load invoices from file
        invoices = _load_invoices_from_file(invoice_file)
        logger.info(f"Loaded {len(invoices)} invoices from file")

        # Load vendor mapping if provided
        vendor_mapping: Dict[str, str] = {}
        if vendor_mapping_file:
            vendor_mapping = _load_vendor_mapping(vendor_mapping_file)
            logger.info(f"Loaded {len(vendor_mapping)} vendor mappings")

        if dry_run:
            print_preview(invoices, "invoices to sync")
            return 0

        invoice_service = container.invoice_service()

        # Run batch sync
        result = invoice_service.sync_batch(
            invoices=invoices,
            vendor_mapping=vendor_mapping,
            workers=workers,
        )

        print_sync_result(result, "INVOICE SYNC")
        return 0 if result.errors == 0 else 1

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return 1
    except Exception as e:
        logger.error(f"Invoice sync failed: {e}")
        return 1


def run_payment_process(
    container: Container,
    invoice_ids: Optional[List[str]] = None,
    pay_all_approved: bool = False,
    funding_account_id: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """
    Process payments in BILL.com.

    Args:
        container: DI container.
        invoice_ids: Specific invoice IDs to pay.
        pay_all_approved: Pay all approved invoices.
        funding_account_id: Funding account to use.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting payment processing in BILL.com AP")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    try:
        payment_service = container.payment_service()
        invoice_service = container.invoice_service()

        invoices_to_pay = []

        if invoice_ids:
            # Get specific invoices
            for invoice_id in invoice_ids:
                invoice = invoice_service.get_invoice_by_id(invoice_id)
                if invoice:
                    invoices_to_pay.append(invoice)
                else:
                    logger.warning(f"Invoice not found: {invoice_id}")

        elif pay_all_approved:
            # Get all payable invoices
            invoices_to_pay = invoice_service.get_payable_invoices()

        else:
            logger.error("Must specify --invoice-ids or --pay-all-approved")
            return 1

        logger.info(f"Found {len(invoices_to_pay)} invoices to pay")

        if not invoices_to_pay:
            logger.info("No invoices to process")
            return 0

        if dry_run:
            print_preview(invoices_to_pay, "invoices to pay")
            total = sum(float(inv.total_amount or 0) for inv in invoices_to_pay)
            print(f"Total payment amount: {format_currency(total)}")
            return 0

        # Process payments
        result = payment_service.create_bulk_payments(
            invoices=invoices_to_pay,
            funding_account_id=funding_account_id,
        )

        print_sync_result(result, "PAYMENT PROCESSING")
        return 0 if result.errors == 0 else 1

    except Exception as e:
        logger.error(f"Payment processing failed: {e}")
        return 1


def run_ap_batch(
    container: Container,
    include_vendors: bool = False,
    include_invoices: bool = False,
    include_payments: bool = False,
    data_dir: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """
    Run full AP batch operation.

    Processes in order: vendors -> invoices -> payments.

    Args:
        container: DI container.
        include_vendors: Include vendor sync.
        include_invoices: Include invoice sync.
        include_payments: Include payment processing.
        data_dir: Directory containing data files.
        dry_run: If True, preview without making changes.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting full AP batch operation")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    if not any([include_vendors, include_invoices, include_payments]):
        logger.error("At least one of --vendors, --invoices, --payments required")
        return 1

    results = []
    exit_code = 0

    try:
        # Step 1: Vendor sync
        if include_vendors:
            print_step_header(1, "Vendor Sync")

            vendor_file = None
            if data_dir:
                vendor_file = str(Path(data_dir) / "vendors.json")

            result = run_vendor_sync(
                container=container,
                vendor_file=vendor_file,
                dry_run=dry_run,
            )
            results.append(("Vendors", result))
            if result != 0:
                exit_code = result

        # Step 2: Invoice sync
        if include_invoices:
            print_step_header(2, "Invoice Sync")

            invoice_file = None
            vendor_mapping_file = None
            if data_dir:
                invoice_file = str(Path(data_dir) / "invoices.json")
                mapping_path = Path(data_dir) / "vendor_mapping.json"
                if mapping_path.exists():
                    vendor_mapping_file = str(mapping_path)

            result = run_invoice_sync(
                container=container,
                invoice_file=invoice_file,
                vendor_mapping_file=vendor_mapping_file,
                dry_run=dry_run,
            )
            results.append(("Invoices", result))
            if result != 0:
                exit_code = result

        # Step 3: Payment processing
        if include_payments:
            print_step_header(3, "Payment Processing")

            result = run_payment_process(
                container=container,
                pay_all_approved=True,
                dry_run=dry_run,
            )
            results.append(("Payments", result))
            if result != 0:
                exit_code = result

        # Print summary
        print_summary(results, "AP BATCH SUMMARY")

        return exit_code

    except Exception as e:
        logger.error(f"AP batch failed: {e}")
        return 1


def _load_vendors_from_file(file_path: str) -> List[Vendor]:
    """Load vendors from JSON file."""
    from src.domain.models.vendor import VendorAddress

    data = load_json_file(file_path)

    vendors = []
    items = data if isinstance(data, list) else data.get("vendors", [])

    for item in items:
        try:
            # Build address from nested or flat structure
            address_data = item.get("address", {})
            address = VendorAddress(
                line1=item.get("address_line1", "") or address_data.get("line1", ""),
                city=item.get("address_city", "") or address_data.get("city", ""),
                state=item.get("address_state", "") or address_data.get("state", ""),
                zip_code=item.get("address_zip", "") or address_data.get("zip", ""),
            )

            vendor = Vendor(
                name=item.get("name", ""),
                email=item.get("email", ""),
                external_id=item.get("external_id", "") or item.get("externalId", ""),
                address=address,
            )
            vendors.append(vendor)
        except Exception as e:
            logger.warning(f"Failed to parse vendor: {e}")

    return vendors


def _load_invoices_from_file(file_path: str) -> List[Invoice]:
    """Load invoices from JSON file."""
    from datetime import datetime
    from decimal import Decimal
    from src.domain.models.invoice import InvoiceLineItem

    data = load_json_file(file_path)

    invoices = []
    items = data if isinstance(data, list) else data.get("invoices", [])

    for item in items:
        try:
            # Parse dates
            invoice_date = None
            if item.get("invoice_date"):
                invoice_date = datetime.strptime(item["invoice_date"], "%Y-%m-%d").date()

            due_date = None
            if item.get("due_date"):
                due_date = datetime.strptime(item["due_date"], "%Y-%m-%d").date()

            # Parse line items
            line_items = []
            for li in item.get("line_items", []):
                line_items.append(
                    InvoiceLineItem(
                        description=li.get("description", ""),
                        amount=Decimal(str(li.get("amount", 0))),
                        quantity=li.get("quantity", 1),
                        gl_account_id=li.get("gl_account_id", "") or li.get("glAccountId", "") or "",
                        department_id=li.get("department_id", "") or li.get("departmentId", "") or "",
                        location_id=li.get("location_id", "") or li.get("locationId", "") or "",
                        class_id=li.get("class_id", "") or li.get("classId", "") or "",
                    )
                )

            invoice = Invoice(
                invoice_number=item.get("invoice_number", ""),
                vendor_id=item.get("vendor_id", ""),
                invoice_date=invoice_date,
                due_date=due_date,
                line_items=line_items,
                total_amount=Decimal(str(item.get("total_amount", 0))),
            )
            invoices.append(invoice)
        except Exception as e:
            logger.warning(f"Failed to parse invoice: {e}")

    return invoices


def _load_vendor_mapping(file_path: str) -> Dict[str, str]:
    """Load vendor ID mapping from JSON file."""
    return load_json_file(file_path)
