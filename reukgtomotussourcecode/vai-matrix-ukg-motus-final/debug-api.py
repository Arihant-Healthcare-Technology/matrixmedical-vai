#!/usr/bin/env python3
"""
Debug API for UKG-to-Motus data validation.

Run locally for Postman/curl testing.

Usage:
    python debug-api.py [--port PORT] [--host HOST] [--reload]

Examples:
    python debug-api.py                     # Default: localhost:8000
    python debug-api.py --port 8080         # Custom port
    python debug-api.py --reload            # Auto-reload on code changes

Environment Variables:
    UKG_BASE_URL        - UKG API base URL
    UKG_BASIC_B64       - UKG Basic Auth token (base64)
    UKG_CUSTOMER_API_KEY - UKG Customer API key
    MOTUS_API_BASE      - Motus API base URL
    MOTUS_JWT           - Motus JWT token
    DEBUG               - Enable debug logging (0/1)

API Documentation:
    http://localhost:8000/docs      - Swagger UI
    http://localhost:8000/redoc     - ReDoc
"""

import argparse
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
from common.correlation import configure_logging

logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file."""
    env_path = os.getenv("ENV_PATH", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    """Run the debug API server."""
    parser = argparse.ArgumentParser(
        description="Run MOTUS Debug API server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("API_PORT", "8000")),
        help="Port to run on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("API_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    args = parser.parse_args()

    # Load environment
    load_env()

    if args.debug:
        os.environ["DEBUG"] = "1"

    # Configure logging based on environment
    configure_logging()

    # Check required environment variables
    required_vars = ["UKG_CUSTOMER_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        logger.warning(f"Missing environment variables: {missing}")
        logger.warning("Some UKG endpoints may not work without proper configuration.")

    # Validate UKG credentials at startup (required)
    from src.infrastructure.config.settings import UKGSettings

    logger.info("Validating API credentials...")

    ukg_settings = UKGSettings.from_env()
    ukg_settings.validate_or_exit()
    logger.info("UKG credentials validated successfully.")

    # Check Motus JWT (warn only for debug server - allows testing UKG endpoints)
    if not os.getenv("MOTUS_JWT"):
        logger.warning("MOTUS_JWT not set. Motus endpoints will not work.")
        logger.warning("Run 'python3 motus-get-token.py --write-env' to generate a token.")
    else:
        jwt = os.getenv("MOTUS_JWT", "")
        if len(jwt.split(".")) != 3:
            logger.warning("MOTUS_JWT appears to be invalid (not a valid JWT format).")
            logger.warning("Motus endpoints may not work correctly.")
        else:
            logger.info("Motus JWT token validated successfully.")

    # Print startup banner (user-facing CLI output)
    print(f"Starting MOTUS Debug API on http://{args.host}:{args.port}")
    print(f"Swagger UI: http://localhost:{args.port}/docs")
    print(f"ReDoc: http://localhost:{args.port}/redoc")
    print()

    import uvicorn

    # When using --reload, uvicorn requires app as import string
    if args.reload:
        uvicorn.run(
            "src.presentation.api.debug_api:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="debug" if args.debug else "info",
        )
    else:
        from src.presentation.api.debug_api import app

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
        )


if __name__ == "__main__":
    main()
