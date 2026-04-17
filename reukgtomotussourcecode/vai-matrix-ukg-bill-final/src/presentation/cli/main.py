"""
Main CLI entry point for UKG to BILL.com integration.

Provides command-line interface for:
- Spend & Expense (S&E) user synchronization
- Accounts Payable (AP) vendor/invoice/payment management
"""

import argparse
import logging
import sys
from typing import Optional

from src.infrastructure.config.settings import get_settings
from src.presentation.cli.container import get_container, reset_container
from src.presentation.cli.batch_commands import (
    run_sync_all,
    run_sync_batch,
    run_export_csv,
)
from src.presentation.cli.ap_commands import (
    run_vendor_sync,
    run_invoice_sync,
    run_payment_process,
    run_ap_batch,
)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all commands."""
    parser = argparse.ArgumentParser(
        prog="ukg-bill",
        description="UKG to BILL.com Integration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync all employees to BILL.com S&E
  ukg-bill sync --all

  # Sync specific company
  ukg-bill sync --company-id J9A6Y

  # Export CSV for bulk import
  ukg-bill export --output users.csv

  # Sync vendors from file
  ukg-bill ap vendors --file vendors.json

  # Run full AP batch
  ukg-bill ap batch --vendors --invoices --payments
        """,
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--log-file",
        help="Write logs to file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them",
    )
    parser.add_argument(
        "--env-file",
        help="Path to environment file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # S&E Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync employees to BILL.com Spend & Expense",
    )
    sync_parser.add_argument(
        "--all",
        action="store_true",
        help="Sync all active employees",
    )
    sync_parser.add_argument(
        "--company-id",
        help="Filter by UKG company ID",
    )
    sync_parser.add_argument(
        "--employee-file",
        help="Path to JSON file with employee data",
    )
    sync_parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Number of concurrent workers (default: 6)",
    )
    sync_parser.add_argument(
        "--default-role",
        choices=["ADMIN", "AUDITOR", "BOOKKEEPER", "MEMBER", "NO_ACCESS"],
        default="MEMBER",
        help="Default role for new users (default: MEMBER)",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="sync_dry_run",
        help="Preview changes without making them",
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export users to CSV for BILL.com bulk import",
    )
    export_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output CSV file path",
    )
    export_parser.add_argument(
        "--company-id",
        help="Filter by UKG company ID",
    )
    export_parser.add_argument(
        "--include-managers",
        action="store_true",
        help="Include manager column for UI import",
    )

    # AP command group
    ap_parser = subparsers.add_parser(
        "ap",
        help="Accounts Payable operations",
    )
    ap_subparsers = ap_parser.add_subparsers(dest="ap_command", help="AP commands")

    # AP Vendors
    vendors_parser = ap_subparsers.add_parser(
        "vendors",
        help="Sync vendors to BILL.com",
    )
    vendors_parser.add_argument(
        "--file",
        help="Path to JSON file with vendor data",
    )
    vendors_parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of concurrent workers (default: 8)",
    )

    # AP Invoices
    invoices_parser = ap_subparsers.add_parser(
        "invoices",
        help="Sync invoices/bills to BILL.com",
    )
    invoices_parser.add_argument(
        "--file",
        help="Path to JSON file with invoice data",
    )
    invoices_parser.add_argument(
        "--vendor-mapping",
        help="Path to JSON file with vendor ID mappings",
    )
    invoices_parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of concurrent workers (default: 8)",
    )

    # AP Payments
    payments_parser = ap_subparsers.add_parser(
        "payments",
        help="Process payments in BILL.com",
    )
    payments_parser.add_argument(
        "--invoice-ids",
        nargs="+",
        help="Invoice IDs to pay",
    )
    payments_parser.add_argument(
        "--pay-all-approved",
        action="store_true",
        help="Pay all approved invoices",
    )
    payments_parser.add_argument(
        "--funding-account",
        help="Funding account ID to use",
    )

    # AP Batch
    batch_parser = ap_subparsers.add_parser(
        "batch",
        help="Run full AP batch (vendors -> invoices -> payments)",
    )
    batch_parser.add_argument(
        "--vendors",
        action="store_true",
        help="Include vendor sync",
    )
    batch_parser.add_argument(
        "--invoices",
        action="store_true",
        help="Include invoice sync",
    )
    batch_parser.add_argument(
        "--payments",
        action="store_true",
        help="Include payment processing",
    )
    batch_parser.add_argument(
        "--data-dir",
        help="Directory containing vendor/invoice JSON files",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Check integration status",
    )
    status_parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Verify API authentication",
    )
    status_parser.add_argument(
        "--check-rate-limit",
        action="store_true",
        help="Check current rate limit status",
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)
    logger = logging.getLogger(__name__)

    # Load environment
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)

    try:
        # Get container
        container = get_container()

        # Route to appropriate command handler
        if args.command == "sync":
            # Use company_id from CLI arg, or fall back to env variable
            company_id = args.company_id or container.settings.ukg_company_id
            # Check both global and subparser dry_run flags
            dry_run = args.dry_run or getattr(args, 'sync_dry_run', False)
            if args.all or company_id:
                return run_sync_all(
                    container=container,
                    company_id=company_id,
                    workers=args.workers,
                    default_role=args.default_role,
                    dry_run=dry_run,
                )
            elif args.employee_file:
                return run_sync_batch(
                    container=container,
                    employee_file=args.employee_file,
                    workers=args.workers,
                    default_role=args.default_role,
                    dry_run=dry_run,
                )
            else:
                parser.error("sync requires --all, --company-id, or --employee-file")

        elif args.command == "export":
            return run_export_csv(
                container=container,
                output_path=args.output,
                company_id=args.company_id or container.settings.ukg_company_id,
                include_managers=args.include_managers,
            )

        elif args.command == "ap":
            # ============================================================
            # TEMPORARILY DISABLED: BILL.com Accounts Payable API calls
            # To re-enable, uncomment the code below and remove this block
            # ============================================================
            logger.warning("BILL.com Accounts Payable (AP) commands are temporarily disabled")
            print("\n" + "=" * 60)
            print("  BILL.com AP API calls are TEMPORARILY DISABLED")
            print("=" * 60)
            print("\nThe following AP commands are currently disabled:")
            print("  - ap vendors   : Vendor synchronization")
            print("  - ap invoices  : Invoice/bill synchronization")
            print("  - ap payments  : Payment processing")
            print("  - ap batch     : Full AP batch operations")
            print("\nTo re-enable, edit: src/presentation/cli/main.py")
            print("=" * 60 + "\n")
            return 0

            # --- DISABLED AP COMMANDS (DO NOT REMOVE) ---
            # if args.ap_command == "vendors":
            #     return run_vendor_sync(
            #         container=container,
            #         vendor_file=args.file,
            #         workers=args.workers,
            #         dry_run=args.dry_run,
            #     )
            # elif args.ap_command == "invoices":
            #     return run_invoice_sync(
            #         container=container,
            #         invoice_file=args.file,
            #         vendor_mapping_file=args.vendor_mapping,
            #         workers=args.workers,
            #         dry_run=args.dry_run,
            #     )
            # elif args.ap_command == "payments":
            #     return run_payment_process(
            #         container=container,
            #         invoice_ids=args.invoice_ids,
            #         pay_all_approved=args.pay_all_approved,
            #         funding_account_id=args.funding_account,
            #         dry_run=args.dry_run,
            #     )
            # elif args.ap_command == "batch":
            #     return run_ap_batch(
            #         container=container,
            #         include_vendors=args.vendors,
            #         include_invoices=args.invoices,
            #         include_payments=args.payments,
            #         data_dir=args.data_dir,
            #         dry_run=args.dry_run,
            #     )
            # else:
            #     parser.error("ap requires a subcommand (vendors, invoices, payments, batch)")
            # --- END DISABLED AP COMMANDS ---

        elif args.command == "status":
            return check_status(
                container=container,
                check_auth=args.check_auth,
                check_rate_limit=args.check_rate_limit,
            )

        else:
            parser.print_help()
            return 0

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Command failed: {e}")
        if args.verbose:
            logger.exception("Full traceback:")
        return 1
    finally:
        reset_container()


def check_status(
    container,
    check_auth: bool = False,
    check_rate_limit: bool = False,
) -> int:
    """Check integration status."""
    logger = logging.getLogger(__name__)
    settings = container.settings

    print("\n=== UKG to BILL.com Integration Status ===\n")

    print("Configuration:")
    print(f"  UKG API Base: {settings.ukg_api_base}")
    print(f"  BILL API Base: {settings.bill_api_base}")
    print(f"  BILL Org ID: {settings.bill_org_id}")
    print(f"  Rate Limit: {settings.rate_limit_calls_per_minute} calls/min")
    print()

    if check_auth:
        print("Authentication Check:")
        try:
            # Test UKG auth
            ukg = container.ukg_client()
            ukg_ok = ukg.test_connection()
            print(f"  UKG API: {'OK' if ukg_ok else 'FAILED'}")
        except Exception as e:
            print(f"  UKG API: FAILED - {e}")

        try:
            # Test BILL auth
            bill = container.bill_client()
            bill_ok = bill.test_connection()
            print(f"  BILL API: {'OK' if bill_ok else 'FAILED'}")
        except Exception as e:
            print(f"  BILL API: FAILED - {e}")
        print()

    print("Status: Ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
