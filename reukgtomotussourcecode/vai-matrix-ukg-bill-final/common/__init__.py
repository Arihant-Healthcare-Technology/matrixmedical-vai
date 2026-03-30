# UKG 3-Way Integration Common Modules
# Shared utilities for BILL.com, Motus, and TravelPerk integrations

__version__ = "1.0.0"

# Secrets Management (SOW 2.6)
from .secrets_manager import (
    SecretsManager,
    EnvSecretsManager,
    AWSSecretsManager,
    VaultSecretsManager,
    CompositeSecretsManager,
    get_secrets_manager,
    get_secret,
)

# Rate Limiting (SOW 5.1, 5.2, 11.10, 13.10, 14.10)
from .rate_limiter import (
    RateLimiter,
    AdaptiveRateLimiter,
    SlidingWindowRateLimiter,
    RateLimitStats,
    get_rate_limiter,
)

# Correlation IDs (SOW 7.2)
from .correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    correlation_context,
    with_correlation_id,
    RunContext,
    configure_logging,
    get_logger,
    CorrelationLogFormatter,
    CorrelationLogFilter,
)

# Notifications (SOW 4.6)
from .notifications import (
    NotificationConfig,
    Notifier,
    SMTPNotifier,
    AWSESNotifier,
    SendGridNotifier,
    NoOpNotifier,
    get_notifier,
)

# Metrics (SOW 4.7, 7.3)
from .metrics import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    Timer,
    get_metrics_collector,
)

# Report Generation (SOW 4.7, 7.3, 10.4)
from .report_generator import ReportGenerator

# PII/Secrets Redaction (SOW 7.4, 7.5, 9.4)
from .redaction import (
    redact_pii,
    redact_secrets,
    redact_all,
    RedactingFormatter,
    RedactingFilter,
    sanitize_for_logging,
    create_safe_error_context,
)

# Validators (SOW 3.6, 3.7)
from .validators import (
    validate_email,
    validate_state_code,
    validate_country_code,
    validate_phone,
    validate_employee_number,
    validate_date_string,
    validate_required,
    validate_length,
    ValidationResult,
    ValidationResults,
    EntityValidator,
    validate_batch,
)

__all__ = [
    # Version
    "__version__",
    # Secrets
    "SecretsManager",
    "EnvSecretsManager",
    "AWSSecretsManager",
    "VaultSecretsManager",
    "CompositeSecretsManager",
    "get_secrets_manager",
    "get_secret",
    # Rate Limiting
    "RateLimiter",
    "AdaptiveRateLimiter",
    "SlidingWindowRateLimiter",
    "RateLimitStats",
    "get_rate_limiter",
    # Correlation
    "generate_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    "correlation_context",
    "with_correlation_id",
    "RunContext",
    "configure_logging",
    "get_logger",
    "CorrelationLogFormatter",
    "CorrelationLogFilter",
    # Notifications
    "NotificationConfig",
    "Notifier",
    "SMTPNotifier",
    "AWSESNotifier",
    "SendGridNotifier",
    "NoOpNotifier",
    "get_notifier",
    # Metrics
    "MetricsCollector",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "get_metrics_collector",
    # Reports
    "ReportGenerator",
    # Redaction
    "redact_pii",
    "redact_secrets",
    "redact_all",
    "RedactingFormatter",
    "RedactingFilter",
    "sanitize_for_logging",
    "create_safe_error_context",
    # Validators
    "validate_email",
    "validate_state_code",
    "validate_country_code",
    "validate_phone",
    "validate_employee_number",
    "validate_date_string",
    "validate_required",
    "validate_length",
    "ValidationResult",
    "ValidationResults",
    "EntityValidator",
    "validate_batch",
]
