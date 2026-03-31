"""
Correlation ID Module - SOW Requirement 7.2

Provides correlation ID generation and propagation for distributed tracing.
Enables end-to-end request tracking across all integration components.

Usage:
    from common.correlation import (
        generate_correlation_id,
        get_correlation_id,
        set_correlation_id,
        correlation_context,
        get_logger
    )

    # Start a new run with correlation ID
    with correlation_context() as cid:
        logger = get_logger(__name__)
        logger.info("Starting batch processing")
        # All logs will include the correlation ID
"""

import os
import uuid
import logging
import sys
import threading
import contextvars
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime

# Thread-local storage for correlation ID (backward compatibility)
_correlation_local = threading.local()

# Context variable for async-compatible correlation ID
_correlation_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


def generate_correlation_id(prefix: str = "") -> str:
    """
    Generate a new unique correlation ID.

    Args:
        prefix: Optional prefix for the ID (e.g., 'bill', 'motus', 'tp')

    Returns:
        A unique correlation ID string
    """
    uid = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{uid}"
    return uid


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_local.value = correlation_id
    _correlation_var.set(correlation_id)


def get_correlation_id() -> str:
    """
    Get the current correlation ID.

    Returns:
        The current correlation ID, or 'UNKNOWN' if not set
    """
    # Try context var first (async-compatible)
    cid = _correlation_var.get()
    if cid:
        return cid

    # Fall back to thread-local
    return getattr(_correlation_local, 'value', 'UNKNOWN')


def clear_correlation_id() -> None:
    """Clear the current correlation ID."""
    _correlation_local.value = None
    _correlation_var.set(None)


class correlation_context:
    """
    Context manager for correlation ID scope.

    Usage:
        with correlation_context() as cid:
            print(f"Processing with correlation ID: {cid}")
            # All operations within this block share the same correlation ID

        # Or with a pre-defined ID:
        with correlation_context(existing_cid):
            ...
    """

    def __init__(self, correlation_id: Optional[str] = None, prefix: str = ""):
        """
        Initialize correlation context.

        Args:
            correlation_id: Use existing ID, or generate new if None
            prefix: Prefix for generated ID
        """
        self.correlation_id = correlation_id or generate_correlation_id(prefix)
        self._previous_id: Optional[str] = None

    def __enter__(self) -> str:
        self._previous_id = _correlation_var.get()
        set_correlation_id(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._previous_id:
            set_correlation_id(self._previous_id)
        else:
            clear_correlation_id()


def with_correlation_id(func: Callable) -> Callable:
    """
    Decorator to ensure a function runs with a correlation ID.

    If no correlation ID exists, generates a new one.

    Usage:
        @with_correlation_id
        def process_batch():
            logger.info("Processing...")  # Will include correlation ID
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        existing_cid = _correlation_var.get()
        if not existing_cid:
            with correlation_context():
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


class CorrelationLogFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to log records.

    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(CorrelationLogFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class CorrelationLogFormatter(logging.Formatter):
    """
    Log formatter that includes correlation ID.

    Format: [LEVEL] [CORRELATION_ID] [TIMESTAMP] message
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        include_module: bool = True
    ):
        if fmt is None:
            if include_module:
                fmt = "[%(levelname)s] [%(correlation_id)s] [%(asctime)s] [%(name)s] %(message)s"
            else:
                fmt = "[%(levelname)s] [%(correlation_id)s] [%(asctime)s] %(message)s"

        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"

        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        # Ensure correlation_id is present
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = get_correlation_id()
        return super().format(record)


def configure_logging(
    level: Optional[int] = None,
    include_module: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging with correlation ID support and environment variable control.

    Environment Variables:
        LOG_LEVEL: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        DEBUG: If "1" or "true", enables DEBUG level
        VERBOSE: If "1" or "true", enables DEBUG level
        LOGGING_DISABLED: If "1" or "true", disables all logging

    Args:
        level: Logging level (overridden by environment variables if not set)
        include_module: Include module name in log format
        log_file: Optional file path for file logging
    """
    # Check if logging is disabled via environment
    logging_disabled = os.getenv("LOGGING_DISABLED", "0").lower() in ("1", "true", "yes")
    if logging_disabled:
        logging.disable(logging.CRITICAL)
        return

    # Determine log level from environment if not explicitly passed
    if level is None:
        # Check DEBUG and VERBOSE flags first
        debug_mode = os.getenv("DEBUG", "0").lower() in ("1", "true", "yes")
        verbose = os.getenv("VERBOSE", "0").lower() in ("1", "true", "yes")

        if debug_mode or verbose:
            level = logging.DEBUG
        else:
            # Get LOG_LEVEL from environment
            log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
            valid_levels = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "WARN": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            level = valid_levels.get(log_level_str, logging.INFO)

    # Create formatter
    formatter = CorrelationLogFormatter(include_module=include_module)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationLogFilter())
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationLogFilter())
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with correlation ID support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Ensure handlers have our filter
    for handler in logger.handlers + logging.getLogger().handlers:
        has_filter = any(
            isinstance(f, CorrelationLogFilter) for f in handler.filters
        )
        if not has_filter:
            handler.addFilter(CorrelationLogFilter())

    return logger


class RunContext:
    """
    Extended context for batch runs with correlation ID and metadata.

    Tracks run information including timing, counts, and errors.
    """

    def __init__(
        self,
        project: str,
        correlation_id: Optional[str] = None,
        company_id: Optional[str] = None
    ):
        """
        Initialize run context.

        Args:
            project: Project identifier ('bill', 'motus', 'travelperk')
            correlation_id: Existing correlation ID or None to generate
            company_id: UKG company ID being processed
        """
        self.project = project
        self.correlation_id = correlation_id or generate_correlation_id(project)
        self.company_id = company_id
        self.run_id = str(uuid.uuid4())
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.stats: Dict[str, int] = {
            'total_processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        self.errors: list = []

    def __enter__(self) -> 'RunContext':
        self.start_time = datetime.now()
        set_correlation_id(self.correlation_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = datetime.now()
        clear_correlation_id()

    @property
    def duration_seconds(self) -> float:
        """Get run duration in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def record_created(self) -> None:
        """Record a successful creation."""
        self.stats['created'] += 1
        self.stats['total_processed'] += 1

    def record_updated(self) -> None:
        """Record a successful update."""
        self.stats['updated'] += 1
        self.stats['total_processed'] += 1

    def record_skipped(self, reason: str = "") -> None:
        """Record a skipped record."""
        self.stats['skipped'] += 1
        self.stats['total_processed'] += 1

    def record_error(
        self,
        identifier: str,
        error: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an error.

        Args:
            identifier: Record identifier (e.g., employee number)
            error: Error message
            details: Additional error details
        """
        self.stats['errors'] += 1
        self.stats['total_processed'] += 1
        self.errors.append({
            'identifier': identifier,
            'error': error,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert run context to dictionary for reporting."""
        return {
            'run_id': self.run_id,
            'correlation_id': self.correlation_id,
            'project': self.project,
            'company_id': self.company_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': round(self.duration_seconds, 2),
            'stats': self.stats,
            'errors': self.errors[:100],  # Limit errors in summary
            'total_errors': len(self.errors)
        }

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        processed = self.stats['total_processed']
        if processed == 0:
            return 100.0
        successful = processed - self.stats['errors']
        return (successful / processed) * 100
