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
    required_vars = [
        "UKG_BASE_URL",
        "UKG_CUSTOMER_API_KEY",
    ]

    optional_vars = [
        "TRAVELPERK_SCIM_BASE",
        "TRAVELPERK_SCIM_TOKEN",
        "LOG_LEVEL",
        "DATA_DIR",
    ]

    results = {
        "required": {},
        "optional": {},
        "healthy": True,
    }

    for var in required_vars:
        value = os.getenv(var)
        if value:
            results["required"][var] = "configured"
        else:
            results["required"][var] = "missing"
            results["healthy"] = False

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

    result = {
        "path": data_dir,
        "exists": False,
        "writable": False,
        "healthy": False,
    }

    if os.path.exists(data_dir):
        result["exists"] = True

        # Test write access
        test_file = os.path.join(data_dir, ".health_check")
        try:
            with open(test_file, "w") as f:
                f.write(f"health check at {datetime.utcnow().isoformat()}")
            os.remove(test_file)
            result["writable"] = True
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

    result = {
        "modules": {},
        "healthy": True,
    }

    for module in required_modules:
        try:
            __import__(module)
            result["modules"][module] = "available"
        except ImportError as e:
            result["modules"][module] = f"error: {e}"
            result["healthy"] = False

    return result


def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health check.

    Returns:
        Dict containing all health check results.
    """
    checks = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ukg-travelperk-sync",
        "version": os.getenv("IMAGE_VERSION", "1.0.0"),
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
        description="Run health check for UKG-TravelPerk integration"
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

    args = parser.parse_args()

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
            print("\nChecks:")
            for name, check in result["checks"].items():
                healthy = check.get("healthy", True)
                status_icon = "[OK]" if healthy else "[FAIL]"
                print(f"  {status_icon} {name}")

    sys.exit(0 if result["status"] == "healthy" else 1)


if __name__ == "__main__":
    main()
