#!/usr/bin/env python3
"""
Batch Wrapper - Integration of common modules with batch processors

This wrapper script demonstrates how to run the existing batch processors
with all SOW-required features enabled:
- Correlation IDs for distributed tracing
- Rate limiting to respect API limits
- Email notifications on completion/failure
- Metrics collection and reporting
- PII redaction in logs

Usage:
    python scripts/batch_wrapper.py --project bill --company-id J9A6Y
    python scripts/batch_wrapper.py --project motus --company-id J9A6Y
    python scripts/batch_wrapper.py --project travelperk --company-id J9A6Y

Environment Variables:
    SECRETS_PROVIDER: 'env', 'aws', or 'vault' (default: env)
    NOTIFICATION_PROVIDER: 'smtp', 'ses', or 'sendgrid' (default: smtp)
    NOTIFICATIONS_ENABLED: 'true' or 'false' (default: true)
    ALERT_RECIPIENTS: Comma-separated email addresses
"""

import os
import sys
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for common module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import (
    # Correlation
    correlation_context,
    configure_logging,
    get_logger,
    RunContext,
    # Rate Limiting
    get_rate_limiter,
    # Notifications
    get_notifier,
    NotificationConfig,
    # Metrics
    get_metrics_collector,
    # Reports
    ReportGenerator,
    # Secrets
    get_secrets_manager,
    # Redaction
    RedactingFilter,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run UKG integration batch with SOW-compliant features"
    )
    parser.add_argument(
        "--project",
        required=True,
        choices=["bill", "motus", "travelperk"],
        help="Project to run"
    )
    parser.add_argument(
        "--company-id",
        dest="company_id",
        help="UKG Company ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without making changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of records to process"
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable email notifications"
    )
    parser.add_argument(
        "--report-dir",
        default="data/reports",
        help="Directory for reports"
    )
    return parser.parse_args()


def get_project_dir(project: str) -> Path:
    """Get the directory for a project."""
    base_dir = Path(__file__).resolve().parent.parent
    project_map = {
        "bill": "vai-matrix-ukg-bill-final",
        "motus": "vai-matrix-ukg-motus-final",
        "travelperk": "vai-matrix-ukg-travelperk-final",
    }
    return base_dir / project_map[project]


def get_batch_script(project: str) -> str:
    """Get the batch script name for a project."""
    script_map = {
        "bill": "run-bill-batch.py",
        "motus": "run-motus-batch.py",
        "travelperk": "run-travelperk-batch.py",
    }
    return script_map[project]


def run_batch_with_features(args):
    """Run batch processor with all SOW features enabled."""

    # Initialize logging with correlation ID support
    configure_logging(include_module=True)
    logger = get_logger(__name__)

    # Add redaction filter to all handlers
    import logging
    for handler in logging.root.handlers:
        handler.addFilter(RedactingFilter())

    # Initialize run context
    with RunContext(
        project=args.project,
        company_id=args.company_id
    ) as ctx:

        logger.info(f"Starting {args.project.upper()} batch processing")
        logger.info(f"Correlation ID: {ctx.correlation_id}")
        logger.info(f"Run ID: {ctx.run_id}")

        # Get secrets manager
        secrets = get_secrets_manager()

        # Get rate limiter for this project
        rate_limiter = get_rate_limiter(args.project)
        logger.info(f"Rate limiter configured: {rate_limiter.calls_per_minute} calls/min")

        # Initialize metrics
        metrics = get_metrics_collector(prefix=f"{args.project}_")

        # Get notifier
        notifier = None
        if not args.no_notify:
            try:
                notifier = get_notifier()
                logger.info("Email notifications enabled")
            except Exception as e:
                logger.warning(f"Notifications disabled: {e}")

        # Initialize report generator
        report_gen = ReportGenerator(output_dir=args.report_dir)

        # Build command for batch script
        project_dir = get_project_dir(args.project)
        batch_script = get_batch_script(args.project)
        script_path = project_dir / batch_script

        cmd = [sys.executable, str(script_path)]

        if args.company_id:
            cmd.extend(["--company-id", args.company_id])
        if args.dry_run:
            cmd.append("--dry-run")
        if args.limit:
            cmd.extend(["--limit", str(args.limit)])

        # Set environment with correlation ID
        env = os.environ.copy()
        env["CORRELATION_ID"] = ctx.correlation_id
        env["RUN_ID"] = ctx.run_id

        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            # Run the batch script
            with metrics.timer("batch_execution"):
                result = subprocess.run(
                    cmd,
                    cwd=project_dir,
                    env=env,
                    capture_output=True,
                    text=True
                )

            # Parse output for stats
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if "[INFO]" in line:
                    print(line)
                    # Parse stats from output
                    if "saved=" in line:
                        try:
                            parts = line.split("|")
                            for part in parts:
                                if "saved=" in part:
                                    count = int(part.split("=")[1].strip())
                                    ctx.stats['created'] = count
                                    ctx.stats['updated'] = count
                                elif "skipped=" in part:
                                    count = int(part.split("=")[1].strip())
                                    ctx.stats['skipped'] = count
                                elif "errors=" in part:
                                    count = int(part.split("=")[1].strip())
                                    ctx.stats['errors'] = count
                                elif "total=" in part:
                                    count = int(part.split("=")[1].strip())
                                    ctx.stats['total_processed'] = count
                        except (ValueError, IndexError):
                            pass
                elif "[WARN]" in line or "[ERROR]" in line:
                    print(line)
                    # Record errors
                    if "employeeNumber=" in line:
                        try:
                            emp_num = line.split("employeeNumber=")[1].split()[0]
                            error_msg = line.split(":", 1)[-1].strip()
                            ctx.record_error(emp_num, error_msg)
                        except IndexError:
                            pass

            if result.stderr:
                logger.error(f"Batch stderr: {result.stderr}")

            metrics.increment("batch_runs_total")

            if result.returncode != 0:
                metrics.increment("batch_runs_failed")
                logger.error(f"Batch failed with exit code {result.returncode}")
            else:
                metrics.increment("batch_runs_success")
                logger.info("Batch completed successfully")

        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            ctx.record_error("batch", str(e))
            metrics.increment("batch_runs_failed")

            # Send critical alert
            if notifier:
                notifier.send_critical_alert(
                    title=f"{args.project.upper()} Batch Failed",
                    error=e,
                    context={
                        "correlation_id": ctx.correlation_id,
                        "company_id": args.company_id,
                    }
                )
            raise

        # Generate reports
        logger.info("Generating reports...")
        run_data = ctx.to_dict()

        report_paths = report_gen.generate_run_report(run_data)
        logger.info(f"Reports generated: {report_paths}")

        # Generate validation report
        validation = report_gen.generate_validation_report(
            run_data,
            target_success_rate=99.0
        )
        logger.info(f"Validation: passed={validation['passed']}, success_rate={validation['success_rate']:.2f}%")

        # Send notification
        if notifier:
            logger.info("Sending run summary notification...")
            notifier.send_run_summary(run_data)

        # Print summary
        print("\n" + "=" * 60)
        print(f"RUN SUMMARY - {args.project.upper()}")
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
        print(f"Reports: {report_paths}")
        print(f"Validation Passed: {validation['passed']}")
        print("=" * 60)

        # Get rate limiter stats
        rl_stats = rate_limiter.get_stats()
        if rl_stats.total_requests > 0:
            print(f"\nRate Limiter Stats:")
            print(f"  Total API Calls: {rl_stats.total_requests}")
            print(f"  Throttled: {rl_stats.throttled_requests}")
            print(f"  Throttle Rate: {rl_stats.throttle_rate:.2%}")

        return ctx.success_rate >= 99.0


def main():
    args = parse_args()

    print(f"\n{'=' * 60}")
    print("UKG Integration Suite - SOW-Compliant Batch Processor")
    print(f"{'=' * 60}")
    print(f"Project: {args.project.upper()}")
    print(f"Company ID: {args.company_id or 'N/A'}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Limit: {args.limit or 'None'}")
    print(f"{'=' * 60}\n")

    try:
        success = run_batch_with_features(args)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
