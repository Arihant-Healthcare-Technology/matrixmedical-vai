"""
Health check utilities for container orchestration.

This module provides health check functionality for Kubernetes, Docker,
and other container orchestration platforms.

Usage:
    python -m src.presentation.cli.health          # Run health check
    python -m src.presentation.cli.health --json   # Output as JSON
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List


def check_environment_variables() -> Dict[str, Any]:
    """
    Check required environment variables are set.

    Returns:
        Dict with check results for each variable.
    """
    # Core UKG variables
    ukg_vars = [
        "UKG_BASE_URL",
        "UKG_CUSTOMER_API_KEY",
    ]

    # BILL Spend & Expense variables
    bill_se_vars = [
        "BILL_API_BASE",
        "BILL_SE_API_TOKEN",
    ]

    # BILL Accounts Payable variables
    bill_ap_vars = [
        "BILL_AP_API_BASE",
        "BILL_AP_API_TOKEN",
    ]

    optional_vars = [
        "LOG_LEVEL",
        "DATA_DIR",
        "BILL_MODE",
    ]

    results = {
        "ukg": {},
        "bill_se": {},
        "bill_ap": {},
        "optional": {},
        "healthy": True,
    }

    # Check UKG variables (always required)
    for var in ukg_vars:
        value = os.getenv(var)
        if value:
            results["ukg"][var] = "configured"
        else:
            results["ukg"][var] = "missing"
            results["healthy"] = False

    # Check BILL S&E variables
    bill_mode = os.getenv("BILL_MODE", "spend_expense")

    for var in bill_se_vars:
        value = os.getenv(var)
        if value:
            results["bill_se"][var] = "configured"
        elif bill_mode == "spend_expense":
            results["bill_se"][var] = "missing"
            results["healthy"] = False
        else:
            results["bill_se"][var] = "not required"

    # Check BILL AP variables
    for var in bill_ap_vars:
        value = os.getenv(var)
        if value:
            results["bill_ap"][var] = "configured"
        elif bill_mode == "accounts_payable":
            results["bill_ap"][var] = "missing"
            results["healthy"] = False
        else:
            results["bill_ap"][var] = "not required"

    for var in optional_vars:
        value = os.getenv(var)
        results["optional"][var] = "configured" if value else "not set"

    return results


def check_data_directory() -> Dict[str, Any]:
    """
    Check data directory exists and is writable.

    Returns:
        Dict with directory check results.
    """
    data_dir = os.getenv("DATA_DIR", "/app/data")
    batch_dir = os.path.join(data_dir, "batch")
    reports_dir = os.path.join(data_dir, "reports")

    result = {
        "data_dir": {
            "path": data_dir,
            "exists": False,
            "writable": False,
        },
        "batch_dir": {
            "path": batch_dir,
            "exists": os.path.exists(batch_dir),
        },
        "reports_dir": {
            "path": reports_dir,
            "exists": os.path.exists(reports_dir),
        },
        "healthy": False,
    }

    if os.path.exists(data_dir):
        result["data_dir"]["exists"] = True

        # Test write access
        test_file = os.path.join(data_dir, ".health_check")
        try:
            with open(test_file, "w") as f:
                f.write(f"health check at {datetime.utcnow().isoformat()}")
            os.remove(test_file)
            result["data_dir"]["writable"] = True
            result["healthy"] = True
        except (IOError, OSError) as e:
            result["error"] = str(e)

    return result


def check_imports() -> Dict[str, Any]:
    """
    Check that required Python modules can be imported.

    Returns:
        Dict with import check results.
    """
    required_modules = [
        "requests",
        "pydantic",
        "dotenv",
        "tenacity",
    ]

    optional_modules = [
        "playwright",  # For scraping
        "boto3",       # For AWS secrets
    ]

    result = {
        "required": {},
        "optional": {},
        "healthy": True,
    }

    for module in required_modules:
        try:
            __import__(module)
            result["required"][module] = "available"
        except ImportError as e:
            result["required"][module] = f"error: {e}"
            result["healthy"] = False

    for module in optional_modules:
        try:
            __import__(module)
            result["optional"][module] = "available"
        except ImportError:
            result["optional"][module] = "not installed"

    return result


def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health check.

    Returns:
        Dict containing all health check results.
    """
    bill_mode = os.getenv("BILL_MODE", "spend_expense")

    checks = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": f"ukg-bill-{bill_mode.replace('_', '-')}-sync",
        "version": os.getenv("IMAGE_VERSION", "1.0.0"),
        "mode": bill_mode,
        "status": "healthy",
        "checks": {
            "environment": check_environment_variables(),
            "data_directory": check_data_directory(),
            "imports": check_imports(),
        },
    }

    # Determine overall health
    all_healthy = all(
        check.get("healthy", True)
        for check in checks["checks"].values()
    )

    if not all_healthy:
        checks["status"] = "unhealthy"

    return checks


def main() -> None:
    """CLI entry point for health check."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run health check for UKG-BILL integration"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed check results",
    )
    parser.add_argument(
        "--mode",
        choices=["spend_expense", "accounts_payable"],
        default=os.getenv("BILL_MODE", "spend_expense"),
        help="BILL integration mode to check",
    )

    args = parser.parse_args()

    # Set mode for check
    os.environ["BILL_MODE"] = args.mode

    result = check_health()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result["status"].upper()
        if result["status"] == "healthy":
            print(f"OK - {status}")
        else:
            print(f"FAIL - {status}")

        if args.verbose:
            print(f"\nTimestamp: {result['timestamp']}")
            print(f"Service: {result['service']}")
            print(f"Version: {result['version']}")
            print(f"Mode: {result['mode']}")
            print("\nChecks:")
            for name, check in result["checks"].items():
                healthy = check.get("healthy", True)
                status_icon = "[OK]" if healthy else "[FAIL]"
                print(f"  {status_icon} {name}")

    sys.exit(0 if result["status"] == "healthy" else 1)


if __name__ == "__main__":
    main()
