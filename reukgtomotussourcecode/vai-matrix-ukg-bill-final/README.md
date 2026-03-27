# UKG Pro to BILL.com Integration

Enterprise integration pipeline for synchronizing employee data from UKG Pro to BILL.com Spend & Expense (S&E) and Accounts Payable (AP) modules.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Configuration](#4-configuration)
5. [CLI Usage](#5-cli-usage)
6. [Data Formats](#6-data-formats)
7. [API Reference](#7-api-reference)
8. [SOW Compliance](#8-sow-compliance)
9. [Testing](#9-testing)
10. [Deployment](#10-deployment)
11. [Monitoring & Logging](#11-monitoring--logging)
12. [Troubleshooting](#12-troubleshooting)
13. [Security](#13-security)
14. [Change Log](#14-change-log)
15. [Support](#15-support)

---

## 1. Overview

### Purpose

This integration provides enterprise-grade synchronization between UKG Pro and BILL.com for:

- **Spend & Expense (S&E)**: User provisioning from UKG employee data
- **Accounts Payable (AP)**: Vendor, invoice, and payment management
- **Browser Automation**: UI automation for features not available via API (manager assignment, CSV import)

### Key Features

- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **Multi-Module Support**: Both S&E and AP modules in one integration
- **Rate Limiting**: Built-in rate limiting with configurable limits
- **Parallel Processing**: ThreadPoolExecutor for high-throughput batch operations
- **Dry-Run Mode**: Validate payloads without making API calls
- **Legacy Compatibility**: Backward-compatible with existing scripts

---

## 2. Architecture

The codebase follows Clean Architecture principles with clear separation of concerns:

```
src/
├── domain/                    # Domain Layer (Business Logic)
│   ├── models/               # Domain entities
│   │   ├── employee.py       # UKG employee model
│   │   ├── bill_user.py      # BILL.com user model
│   │   ├── vendor.py         # AP vendor model
│   │   ├── invoice.py        # AP invoice/bill model
│   │   └── payment.py        # AP payment model
│   ├── exceptions/           # Domain exceptions
│   └── interfaces/           # Repository & service interfaces
│
├── application/              # Application Layer (Use Cases)
│   └── services/
│       ├── sync_service.py   # S&E user synchronization
│       ├── vendor_service.py # Vendor management
│       ├── invoice_service.py# Invoice/bill management
│       └── payment_service.py# Payment processing
│
├── infrastructure/           # Infrastructure Layer (External Systems)
│   ├── config/              # Configuration management
│   │   ├── settings.py      # Pydantic settings
│   │   └── constants.py     # Application constants
│   ├── http/                # HTTP utilities
│   │   ├── client.py        # Base HTTP client with retry
│   │   └── retry.py         # Retry strategies
│   └── adapters/
│       ├── ukg/             # UKG Pro API adapter
│       ├── bill/            # BILL.com API adapters
│       │   ├── spend_expense.py   # S&E API
│       │   └── accounts_payable.py# AP API
│       └── scraping/        # Browser automation (Page Object Model)
│
└── presentation/            # Presentation Layer (CLI)
    └── cli/
        ├── main.py          # CLI entry point
        ├── batch_commands.py# S&E sync commands
        └── ap_commands.py   # AP commands
```

### Self-Contained Repository

This repository is **fully self-contained** with all dependencies included locally for easy Azure deployment:

```
vai-matrix-ukg-bill-final/
├── common/                   # Shared utility modules (local copy)
│   ├── __init__.py
│   ├── secrets_manager.py    # SOW 2.6 - Secrets management
│   ├── rate_limiter.py       # SOW 5.1, 5.2 - Rate limiting
│   ├── correlation.py        # SOW 7.2 - Correlation IDs & logging
│   ├── notifications.py      # SOW 4.6 - Email notifications
│   ├── metrics.py            # SOW 4.7, 7.3 - Metrics collection
│   ├── report_generator.py   # SOW 4.7, 7.3, 10.4 - Report generation
│   ├── redaction.py          # SOW 7.4, 7.5, 9.4 - PII redaction
│   └── validators.py         # SOW 3.6, 3.7 - Input validation
├── src/                      # Clean architecture source
├── build-bill-entity.py      # Build BILL user payload from UKG
├── upsert-bill-entity.py     # Create/update BILL user
├── run-bill-batch.py         # Batch orchestrator
├── Dockerfile                # Container definition
└── requirements.txt          # Python dependencies
```

All scripts import from the local `./common/` package:

```python
from common import (
    get_secrets_manager,
    get_rate_limiter,
    configure_logging,
    get_logger,
    # ... other imports
)
```

### Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐     ┌─────────────┐
│   UKG Pro   │────▶│  Domain Models   │────▶│   Services     │────▶│  BILL.com   │
│     API     │     │  (Clean Arch)    │     │  (Use Cases)   │     │    API      │
└─────────────┘     └──────────────────┘     └────────────────┘     └─────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   CLI / Batch    │
                    │  (Presentation)  │
                    └──────────────────┘
```

---

## 3. Prerequisites

### System Requirements

- Python 3.11 or higher
- pip (Python package manager)
- Docker (for containerized deployment)

### Dependencies

```bash
pip install -r requirements.txt
```

### Development Installation

```bash
pip install -e ".[dev]"
```

### Access Requirements

- UKG Pro API credentials (Basic Auth + Customer API Key)
- BILL.com API token and Organization ID
- Network access to both UKG and BILL.com API endpoints

---

## 4. Configuration

### Environment Variables

Create a `.env` file or set environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKG_API_BASE` | Yes | `https://service4.ultipro.com` | UKG Pro API base URL |
| `UKG_USERNAME` | Yes | - | UKG API username |
| `UKG_PASSWORD` | Yes | - | UKG API password |
| `UKG_API_KEY` | Yes | - | UKG Customer API Key |
| `BILL_API_BASE` | Yes | `https://gateway.bill.com/connect/v3` | BILL.com API base URL |
| `BILL_API_TOKEN` | Yes | - | BILL.com API token |
| `BILL_ORG_ID` | Yes | - | BILL.com Organization ID |
| `BILL_DEFAULT_FUNDING_ACCOUNT` | No | - | Default funding account UUID |
| `RATE_LIMIT_CALLS_PER_MINUTE` | No | `60` | API rate limit |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `WORKERS` | No | `12` | Thread pool size |

### Example Configuration File

**matrix-ukg-bill.env:**
```bash
# UKG Pro API
UKG_API_BASE=https://service4.ultipro.com
UKG_USERNAME=your-username
UKG_PASSWORD=your-password
UKG_API_KEY=your-customer-api-key

# BILL.com API
BILL_API_BASE=https://gateway.bill.com/connect/v3
BILL_API_TOKEN=your-api-token
BILL_ORG_ID=your-org-id

# Optional: Default funding account for payments
BILL_DEFAULT_FUNDING_ACCOUNT=account-uuid

# Rate limiting
RATE_LIMIT_CALLS_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
```

### Environment URLs

| Environment | URL |
|-------------|-----|
| Production | `https://gateway.bill.com/connect/v3` |
| Staging | `https://gateway.stage.bill.com/connect/v3` |

---

## 5. CLI Usage

### Global Options

```bash
ukg-bill [OPTIONS] COMMAND [ARGS]

Options:
  --verbose, -v          Enable verbose logging
  --log-file FILE        Write logs to file
  --dry-run              Preview changes without executing
  --env-file FILE        Load environment from file
  --help                 Show help message
```

### Spend & Expense Commands

#### Sync All Employees

```bash
# Sync all active employees from UKG to BILL.com
ukg-bill sync --all

# Filter by UKG company ID
ukg-bill sync --all --company-id J9A6Y

# Dry run (preview only)
ukg-bill --dry-run sync --all
```

#### Sync from File

```bash
# Sync employees from JSON file
ukg-bill sync --employee-file employees.json

# With custom worker count
ukg-bill sync --employee-file employees.json --workers 16
```

#### Export to CSV

```bash
# Export employees for BILL.com UI import
ukg-bill export --output people.csv
```

### Accounts Payable Commands

#### Vendor Management

```bash
# Sync vendors from JSON file
ukg-bill ap vendors --file vendors.json

# Dry run
ukg-bill --dry-run ap vendors --file vendors.json
```

#### Invoice/Bill Management

```bash
# Sync invoices from JSON file
ukg-bill ap invoices --file invoices.json

# With vendor mapping
ukg-bill ap invoices --file invoices.json --vendor-mapping vendor_map.json
```

#### Payment Processing

```bash
# Pay specific invoices
ukg-bill ap payments --invoice-ids INV001,INV002,INV003

# Pay all approved invoices
ukg-bill ap payments --pay-all-approved

# Specify funding account
ukg-bill ap payments --pay-all-approved --funding-account ACC123
```

#### Full AP Batch

```bash
# Run full AP workflow: vendors -> invoices -> payments
ukg-bill ap batch --vendors --invoices --payments --data-dir ./data/ap/

# Just vendors and invoices
ukg-bill ap batch --vendors --invoices --data-dir ./data/ap/
```

### Status Check

```bash
# Check system status and connectivity
ukg-bill status
```

### Legacy Scripts

For backward compatibility, legacy scripts are still available:

| Legacy Script | New Command |
|---------------|-------------|
| `run-bill-batch.py --company-id X` | `ukg-bill sync --all --company-id X` |
| `build-bill-entity.py 12345` | `ukg-bill sync --employee-file <file>` |
| `upsert-bill-entity.py` | `ukg-bill sync --all` (auto upserts) |
| `run-ap-batch.py` | `ukg-bill ap batch` |

---

## 6. Data Formats

### Employee JSON Format

```json
[
  {
    "employeeId": "EMP001",
    "employeeNumber": "12345",
    "firstName": "John",
    "lastName": "Doe",
    "emailAddress": "john.doe@example.com",
    "employeeStatusCode": "A"
  }
]
```

### Vendor JSON Format

```json
[
  {
    "name": "Acme Corp",
    "email": "vendor@acme.com",
    "external_id": "ACME-001",
    "address": {
      "line1": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip": "94105"
    }
  }
]
```

### Invoice JSON Format

```json
[
  {
    "invoice_number": "INV-001",
    "vendor_id": "VND001",
    "invoice_date": "2024-03-01",
    "due_date": "2024-04-01",
    "total_amount": 1000.00,
    "line_items": [
      {"description": "Services", "amount": 1000.00}
    ]
  }
]
```

---

## 7. API Reference

### BILL.com Spend & Expense API

- **Base URL**: `https://gateway.bill.com/connect/v3/spend`
- **Authentication**: Bearer token via `apiToken` header
- **Rate Limit**: 60 calls/minute

### BILL.com Accounts Payable API

- **Base URL**: `https://gateway.bill.com/connect/v3`
- **Authentication**: Bearer token via `apiToken` header
- **Rate Limit**: 60 calls/minute

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v3/spend/users` | POST | Create S&E user |
| `/v3/spend/users` | GET | List S&E users |
| `/v3/spend/users/{id}` | PATCH | Update S&E user |
| `/v3/vendors` | POST/GET | Manage vendors |
| `/v3/bills` | POST/GET | Manage bills/invoices |
| `/v3/payments` | POST | Process payments |
| `/v3/payments/bulk` | POST | Bulk payments |

### UKG Pro Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/personnel/v1/employee-employment-details` | GET | Employment details |
| `/personnel/v1/person-details` | GET | Personal information |
| `/personnel/v1/employment-details` | GET | Employment status |

---

## 8. SOW Compliance

### Implemented Features

| Feature | Status | Implementation |
|---------|--------|---------------|
| Rate Limiting | Implemented | Configurable calls per minute |
| Retry Logic | Implemented | Exponential backoff for 5xx errors |
| Error Handling | Implemented | Comprehensive error codes |
| Logging | Implemented | Structured logging with correlation |

### Rate Limiting

The system implements configurable rate limiting:

```python
# Configuration
RATE_LIMIT_CALLS_PER_MINUTE=60

# Implementation in src/infrastructure/http/client.py
class RateLimitedClient:
    def __init__(self, calls_per_minute: int = 60):
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0
```

### Retry Logic

Automatic retry with exponential backoff for transient failures:

```python
# src/infrastructure/http/retry.py
class RetryStrategy:
    max_retries: int = 3
    backoff_factor: float = 2.0
    retry_statuses: set = {429, 500, 502, 503, 504}
```

### Error Handling

Comprehensive error handling with domain-specific exceptions:

```python
# src/domain/exceptions/
class BillApiError(Exception): pass
class VendorNotFoundError(Exception): pass
class PaymentFailedError(Exception): pass
class InsufficientFundsError(Exception): pass
```

---

## 9. Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── domain/           # Domain model tests
│   ├── application/      # Service tests
│   └── infrastructure/   # Adapter tests
└── integration/
    ├── test_e2e.py       # End-to-end tests
    └── test_api.py       # API integration tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_sync_service.py -v
```

### Test Coverage

Run coverage report:

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 10. Deployment

### Docker Deployment

#### Build Image

```bash
docker build -t ukg-bill:latest .
```

#### Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["python", "-m", "ukg_bill"]
CMD []
```

#### Run Container

```bash
# Standard execution (S&E sync)
docker run --rm \
  --env-file matrix-ukg-bill.env \
  -v "$(pwd)/data:/app/data" \
  ukg-bill:latest sync --all

# AP batch
docker run --rm \
  --env-file matrix-ukg-bill.env \
  -v "$(pwd)/data:/app/data" \
  ukg-bill:latest ap batch --vendors --invoices --data-dir /app/data/ap/

# Dry run
docker run --rm \
  --env-file matrix-ukg-bill.env \
  ukg-bill:latest --dry-run sync --all
```

### Azure Container Instance

```bash
# Create container instance
az container create \
  --resource-group rg-matrix-integrations \
  --name matrix-ukg-bill \
  --image matrixacr.azurecr.io/ukg-bill:latest \
  --environment-variables \
    COMPANY_ID=J9A6Y \
  --secure-environment-variables \
    UKG_USERNAME=$UKG_USERNAME \
    UKG_PASSWORD=$UKG_PASSWORD \
    UKG_API_KEY=$UKG_API_KEY \
    BILL_API_TOKEN=$BILL_API_TOKEN \
    BILL_ORG_ID=$BILL_ORG_ID
```

### Scheduled Execution (Cron)

```bash
# Daily S&E sync at 4 AM
0 4 * * * docker run --rm --env-file /opt/matrix/matrix-ukg-bill.env ukg-bill:latest sync --all >> /var/log/bill-sync.log 2>&1

# Weekly AP batch on Sundays
0 5 * * 0 docker run --rm --env-file /opt/matrix/matrix-ukg-bill.env ukg-bill:latest ap batch --vendors --invoices --data-dir /app/data/ap/ >> /var/log/bill-ap.log 2>&1
```

---

## 11. Monitoring & Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed trace information |
| INFO | Progress updates, processing stats |
| WARNING | Validation issues, skipped records |
| ERROR | API failures, critical errors |

### Log Format

```
2026-03-26 10:30:15 INFO  [sync_service] Starting employee sync for company J9A6Y
2026-03-26 10:30:16 INFO  [sync_service] Fetched 450 employees from UKG
2026-03-26 10:30:20 INFO  [sync_service] Progress: 100/450 processed
2026-03-26 10:30:45 INFO  [sync_service] Completed: 445 synced, 5 skipped, 0 errors
```

### Structured Logging

Enable JSON logging for log aggregation:

```bash
LOG_FORMAT=json
```

Output:
```json
{
  "timestamp": "2026-03-26T10:30:15Z",
  "level": "INFO",
  "service": "sync_service",
  "message": "Starting employee sync",
  "company_id": "J9A6Y",
  "correlation_id": "abc123"
}
```

### Health Check

```bash
ukg-bill status
```

Output:
```
UKG Pro API:    ✓ Connected
BILL.com API:   ✓ Connected
Database:       ✓ Connected
Rate Limit:     45/60 requests remaining
```

---

## 12. Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid API token | Verify `BILL_API_TOKEN` |
| `403 Forbidden` | Missing org access | Check `BILL_ORG_ID` |
| `429 Rate Limited` | Too many requests | Reduce worker count or rate limit |
| `Vendor not found` | Missing vendor mapping | Create vendor first |
| `Insufficient funds` | Funding account empty | Check account balance |
| `Connection timeout` | Network issues | Check network connectivity |

### Debugging Steps

1. **Enable verbose logging**: Use `--verbose` flag
2. **Check connectivity**: Run `ukg-bill status`
3. **Dry run first**: Use `--dry-run` to validate payloads
4. **Review logs**: Check log file with `--log-file`
5. **Test single record**: Process one employee/vendor first

### FAQ

**Q: Why are some employees skipped?**
A: Employees may be skipped due to missing required fields (email, name) or inactive status.

**Q: How do I handle vendor mapping errors?**
A: Ensure vendors exist in BILL.com before creating invoices, or use `--vendor-mapping` file.

**Q: Can I run multiple modules simultaneously?**
A: Yes, but ensure rate limits are not exceeded. Use separate processes with lower `WORKERS` count.

**Q: How do I recover from a failed batch?**
A: Check `data/batch/` for processed records and resume with remaining items.

---

## 13. Security

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Employee PII | Sensitive | Redacted in logs |
| Financial Data | Confidential | Encrypted in transit |
| API Tokens | Secret | Environment variables only |
| Payment Info | Confidential | Never logged |

**Note: This integration processes PII and financial data. No PHI (Protected Health Information) is accessed or transmitted.**

### Authentication

| System | Method |
|--------|--------|
| UKG Pro | Basic Auth + Customer API Key header |
| BILL.com | Bearer Token (apiToken header) |

### BILL.com Auth Header

```
apiToken: your-api-token-here
```

### Secrets Management

- All secrets stored as environment variables
- Never commit `.env` files to version control
- Use Azure Key Vault for production deployments
- Rotate API tokens periodically

### Network Security

- All API communication over HTTPS
- TLS 1.2+ required
- IP whitelisting recommended for production

---

## 14. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-02-01 | Initial S&E module release |
| 1.1.0 | 2025-03-01 | Added AP module (vendors, invoices) |
| 1.2.0 | 2025-03-15 | Added payment processing |
| 1.3.0 | 2026-03-26 | Clean Architecture refactor |
| 1.3.0 | 2026-03-26 | Added comprehensive test suite |
| 1.3.0 | 2026-03-26 | Added SOW compliance features |

---

## 15. Support

### Contact

- **Team**: Matrix Medical Integration Team
- **Repository**: vai-matrix-ukg-bill-final

### Resources

- [BILL.com API Documentation](https://developer.bill.com/)
- [BILL.com S&E API Reference](https://developer.bill.com/docs/spend-expense)
- [UKG Pro API Documentation](https://developer.ukg.com/)

### Escalation Path

1. Check troubleshooting section
2. Review logs for error details
3. Contact integration team
4. Escalate to BILL.com support if needed

### Contributing

1. Follow Clean Architecture principles
2. Write unit tests for new features
3. Use type hints throughout
4. Run `pytest` before submitting changes
