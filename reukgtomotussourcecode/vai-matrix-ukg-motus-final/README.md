# UKG Pro to Motus Driver Sync

Enterprise integration pipeline for synchronizing employee data from UKG Pro to the Motus mileage reimbursement platform.

---

## Table of Contents

- [Quick Start](#quick-start)
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Business Logic](#3-business-logic)
4. [Prerequisites](#4-prerequisites)
5. [Configuration](#5-configuration)
6. [Usage](#6-usage)
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

## Quick Start

Get up and running in 5 steps:

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
```

**Required credentials in `.env`** (see [Section 5](#5-configuration) for the full list):
```bash
# UKG Pro API
UKG_USERNAME=your_ukg_username
UKG_PASSWORD=your_ukg_password
UKG_CUSTOMER_API_KEY=your_ukg_customer_api_key

# Motus API (used to mint the JWT on first call)
MOTUS_LOGIN_ID=your_motus_login_id
MOTUS_PASSWORD=your_motus_password

# Batch
COMPANY_ID=J9A6Y
```

### 3. Generate a Motus Token (optional)

The client mints and caches a JWT automatically on first use, but you can
pre-generate one:

```bash
python motus-get-token.py --write-env
```

### 4. Dry Run (Preview Changes)

```bash
python -m src.presentation.cli.batch_runner --company-id J9A6Y --dry-run
```

### 5. Execute Sync

```bash
python -m src.presentation.cli.batch_runner --company-id J9A6Y
```

### Test a Single Employee (Local Testing)

There is no single-employee flag on the batch runner. To exercise the full
pipeline for **one** employee, use the built-in Debug API (see
[Section 6](#debug-api)):

```bash
# Start the debug API
uvicorn src.presentation.api.debug_api:app --reload --port 8000

# Dry-run sync one employee (no changes written to Motus)
curl -X POST "http://localhost:8000/sync" \
  -H "Content-Type: application/json" \
  -d '{"employee_number": "12345", "company_id": "J9A6Y", "dry_run": true}'
```

### Docker Alternative

```bash
# Build and run with Docker
docker build -t matrix-ukg-motus:latest .
docker run --rm --env-file .env matrix-ukg-motus:latest --company-id J9A6Y --dry-run
```

---

## 1. Overview

### Purpose

This integration automates the synchronization of employee data from UKG Pro (Ultimate Kronos Group) to Motus, a platform that reimburses employees for business use of their personal vehicles. It keeps the Motus driver roster, status, and attributes aligned with UKG HR data across two reimbursement programs:

| Program | Program ID | Description |
|---------|------------|-------------|
| FAVR | 21232 | Fixed and Variable Rate reimbursement |
| CPM | 21233 | Cents Per Mile reimbursement |

### Key Features

- **Job Code Eligibility Filtering**: Only sync employees with eligible `primaryJobCode` values
- **Change-Window Filtering**: Only process employees changed within the last _N_ days (`--batch-run-days`)
- **Employment Status Derivation**: Track Active, Leave, and Terminated status
- **Manager/Supervisor Tracking**: Include supervisor name in the driver payload
- **Automatic Token Refresh**: JWT is minted and cached transparently
- **Parallel or Sequential Processing**: ThreadPoolExecutor or sequential mode for batch operations
- **Dry-Run Mode**: Validate payloads without making API calls
- **Debug API**: FastAPI service for single-employee troubleshooting

---

## 2. Architecture

The codebase follows a Clean Architecture layout under `src/`:

```
src/
├── domain/                        # Domain Layer (entities, interfaces)
├── application/
│   └── services/
│       ├── driver_sync.py         # Batch upsert orchestration
│       └── driver_builder.py      # UKG → Motus payload builder
├── infrastructure/
│   ├── config/
│   │   └── settings.py            # UKG/Motus/Batch settings (dataclasses)
│   └── adapters/
│       ├── ukg/                   # UKG Pro API client
│       └── motus/                 # Motus API client + token manager
└── presentation/
    ├── cli/
    │   └── batch_runner.py        # CLI entry point (python -m ...)
    └── api/
        └── debug_api.py           # FastAPI debug/troubleshooting service
```

### Entry Point

The supported entry point is the batch-runner module (this is also the Docker
`ENTRYPOINT`):

```bash
python -m src.presentation.cli.batch_runner --company-id J9A6Y
```

> **Note:** The legacy top-level scripts (`run-motus-batch.py`,
> `build-motus-driver.py`, `upsert-motus-driver.py`) have been retired to the
> `_deprecated/` folder and are no longer the supported interface.
> `motus-get-token.py` remains a standalone helper (see [Token Management](#token-management)).

### Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐     ┌─────────────┐
│   UKG Pro   │────▶│  driver_builder  │────▶│  driver_sync   │────▶│  Motus API  │
│     API     │     │  (payload build) │     │ (POST / PUT)   │     │             │
└─────────────┘     └──────────────────┘     └────────────────┘     └─────────────┘
                              ▲
                              │
                    ┌──────────────────┐
                    │   batch_runner   │
                    │  (CLI + filters) │
                    └──────────────────┘
```

### Self-Contained Repository

This repository is **fully self-contained** with shared utilities included
locally under `common/` for easy Azure deployment:

```
vai-matrix-ukg-motus-final/
├── common/                   # Shared utility packages (local copy)
│   ├── secrets_manager.py    # Secrets/env-file resolution
│   ├── correlation.py        # Correlation IDs & logging config
│   ├── rate_limiter/         # Rate limiting
│   ├── notifications/        # Email/alert notifications
│   └── redaction/            # PII redaction
├── src/                      # Clean-architecture source
├── motus-get-token.py        # Standalone JWT helper
├── Dockerfile                # Container definition
└── requirements.txt          # Python dependencies
```

---

## 3. Business Logic

### 3.1 Job Code Eligibility (Pre-filter)

Only employees whose `primaryJobCode` is in the eligible set are synchronized to
Motus. The default set is defined as `DEFAULT_JOB_IDS` in `batch_runner.py` and
can be overridden with the `JOB_IDS` environment variable (comma-separated):

| Program | Job Codes |
|---------|-----------|
| FAVR (21232) | 1103, 4165, 4166, 1102, 1106, 4197, 4196 |
| CPM (21233) | 2817, 4121, 2157 |

Employees with ineligible job codes are skipped during batch processing.

### 3.2 Change-Window Filter

Employees are further filtered by `dateTimeChanged` — only those changed within
the last `--batch-run-days` days (default `1`) are processed. Use
`--batch-run-days 7` for a weekly catch-up run.

### 3.3 Employment Status Derivation

The system derives employment status from UKG data:

| Status | Condition |
|--------|-----------|
| `Leave` | `leaveStartDate` is set AND `leaveEndDate` is null |
| `Terminated` | `terminationDate` is set |
| `Active` | Default (or uses `employeeStatusCode`) |

This derived status is included as a custom variable in the Motus payload.

### 3.4 Manager/Supervisor Tracking

Manager information is fetched from UKG's supervisor-details endpoint:

- **Source**: `/personnel/v1/supervisor-details`
- **Fields Used**: `supervisorFirstName`, `supervisorLastName`
- **Output**: "Manager Name" custom variable (e.g., "Jane Manager")

### 3.5 Data Transformations

| Field | Transformation | Example |
|-------|---------------|---------|
| Dates | ISO 8601 → MM/DD/YYYY | `2024-03-15` → `03/15/2024` |
| Phone | Normalize to XXX-XXX-XXXX | `5551234567` → `555-123-4567` |
| State | Uppercase for filtering | `fl` → `FL` |

---

## 4. Prerequisites

### System Requirements

- Python 3.9 or higher (`requires-python = ">=3.9"`; the Docker image uses 3.11)
- pip (Python package manager)
- Docker (for containerized deployment)

### Local Setup on a Desktop Machine

Run the integration directly on your Mac, Windows, or Linux desktop (no Docker
required). From the project root:

**macOS / Linux:**
```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env      # then edit .env with your credentials

# 4. Generate a Motus token (optional — the client will mint one on demand)
python motus-get-token.py --write-env

# 5. Dry run (no changes written to Motus)
python -m src.presentation.cli.batch_runner --company-id J9A6Y --dry-run
```

**Windows (PowerShell):**
```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
copy .env.example .env     # then edit .env with your credentials

# 4. Dry run
python -m src.presentation.cli.batch_runner --company-id J9A6Y --dry-run
```

### Access Requirements

- UKG Pro API credentials (Basic Auth + Customer API Key)
- Motus API credentials (Login ID + Password for JWT generation)
- Network access to both UKG and Motus API endpoints

---

## 5. Configuration

### Environment Variables

The fastest way to configure is to copy the template and edit it:

```bash
cp .env.example .env
```

Settings are read by explicit name (no shared prefix) in
`src/infrastructure/config/settings.py`. The tables below list the variables
you will most commonly set.

#### UKG Pro

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKG_BASE_URL` | No | `https://service4.ultipro.com` | UKG Pro API base URL |
| `UKG_USERNAME` | Yes* | - | UKG API username |
| `UKG_PASSWORD` | Yes* | - | UKG API password |
| `UKG_CUSTOMER_API_KEY` | Yes | - | UKG Customer API Key header |
| `UKG_BASIC_B64` | No | - | Pre-encoded Basic auth token; used instead of username/password if set |
| `UKG_TIMEOUT` | No | `45` | Request timeout (seconds) |
| `UKG_MAX_RETRIES` | No | `3` | Max retry attempts |

\* Either `UKG_USERNAME` + `UKG_PASSWORD`, **or** `UKG_BASIC_B64`, is required.

#### Motus

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MOTUS_API_BASE` | No | `https://api.motus.com/v1` | Motus API base URL |
| `MOTUS_LOGIN_ID` | Yes** | - | Motus login ID (needed to mint the JWT) |
| `MOTUS_PASSWORD` | Yes** | - | Motus password (needed to mint the JWT) |
| `MOTUS_JWT` | No | - | Pre-supplied JWT; if empty it is generated and cached automatically |
| `MOTUS_PROGRAM_ID` | No | `21233` | Default program id (CPM) |
| `MOTUS_TOKEN_URL` | No | `https://token.motus.com/tokenservice/token/api` | Token endpoint |
| `MOTUS_TOKEN_CACHE` | No | `.motus_token.json` | Token cache file |
| `MOTUS_TOKEN_REFRESH_SAFETY` | No | `60` | Seconds before expiry to refresh |
| `MOTUS_DEFAULT_TTL_SECONDS` | No | `3300` | Fallback token TTL (55 min) |
| `MOTUS_TIMEOUT` | No | `45` | Request timeout (seconds) |
| `MOTUS_MAX_RETRIES` | No | `3` | Max retry attempts |

\*\* Required only when a JWT must be minted (i.e. `MOTUS_JWT` is not supplied).

#### Batch, Logging & Other

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COMPANY_ID` | Yes*** | - | UKG Company ID (fallback when `--company-id` is omitted) |
| `WORKERS` | No | `12` | Thread pool size |
| `USE_SEQUENTIAL` | No | `1` | Sequential (`1`) vs threaded (`0`) processing |
| `BATCH_RUN_DAYS` | No | `1` | Change-window look-back for `dateTimeChanged` |
| `JOB_IDS` | No | built-in default | Eligible job codes (comma-separated) |
| `STATES` | No | - | Optional comma-separated state filter |
| `DRY_RUN` | No | `0` | Validate only, no API calls (`1` enables) |
| `SAVE_LOCAL` | No | `0` | Write JSON payloads to `data/batch` |
| `PROBE` | No | `0` | On dry-run, GET Motus to report would-insert/update |
| `OUT_DIR` | No | `data/batch` | Output directory |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `DEBUG` | No | `0` | Enable verbose debug logging (`1` enables) |

\*\*\* Required unless passed as `--company-id`.

Environment selection (`ENV_FILE`, `ENV_NAME`) and notification/secrets-provider
variables are documented inline in `.env.example`. Notification variables read
by the code are `NOTIFICATIONS_ENABLED`, `NOTIFICATION_PROVIDER`,
`NOTIFICATION_SENDER`, `ALERT_RECIPIENTS`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_USE_TLS`.

### Minimal `.env` Example

```bash
# UKG Configuration
UKG_BASE_URL=https://service4.ultipro.com
UKG_USERNAME=your-username
UKG_PASSWORD=your-password
UKG_CUSTOMER_API_KEY=your-customer-api-key

# Motus Configuration (JWT minted automatically if omitted)
MOTUS_LOGIN_ID=your-login-id
MOTUS_PASSWORD=your-password
MOTUS_API_BASE=https://api.motus.com/v1

# Batch Configuration
COMPANY_ID=J9A6Y
WORKERS=12
BATCH_RUN_DAYS=1
LOG_LEVEL=INFO
```

### Environment-Specific Configuration

The secrets manager resolves an env file in this order:

1. `ENV_FILE` environment variable (explicit override)
2. `.env.dev` if `ENV_NAME=development`
3. `.env.prod` if `ENV_NAME=production`
4. `.env` (default fallback)
5. Project-specific files (`matrix-ukg-motus.env`, etc.)

```bash
# Development
ENV_NAME=development python -m src.presentation.cli.batch_runner --company-id J9A6Y

# Production
ENV_NAME=production python -m src.presentation.cli.batch_runner --company-id J9A6Y
```

---

## 6. Usage

### Batch Processing

```bash
# Full batch
python -m src.presentation.cli.batch_runner --company-id J9A6Y

# Dry run (validate only)
python -m src.presentation.cli.batch_runner --company-id J9A6Y --dry-run

# Weekly catch-up (employees changed in the last 7 days)
python -m src.presentation.cli.batch_runner --company-id J9A6Y --batch-run-days 7

# Save payloads locally
python -m src.presentation.cli.batch_runner --company-id J9A6Y --save-local

# Custom worker count
python -m src.presentation.cli.batch_runner --company-id J9A6Y --workers 24

# Dry run with probe (reports would-insert/update)
python -m src.presentation.cli.batch_runner --company-id J9A6Y --dry-run --probe
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--company-id` | UKG Company ID (falls back to `COMPANY_ID` env) |
| `--workers` | Thread pool size |
| `--dry-run` | Validate without POST/PUT to Motus |
| `--save-local` | Write JSON payloads to `data/batch` |
| `--probe` | On dry-run, GET Motus to report would-insert/update |
| `--batch-run-days` | Filter employees changed within the last _N_ days |

> **Note:** State filtering is available via the `STATES` environment variable;
> there is no `--states` CLI flag on the batch runner.

### Token Management

Generate or refresh a Motus JWT with the standalone helper:

```bash
# Generate token and print to stdout
python motus-get-token.py

# Generate token and write MOTUS_JWT to the .env file
python motus-get-token.py --write-env

# Force refresh (ignore cache)
python motus-get-token.py --force --write-env

# Output as JSON with expiration details
python motus-get-token.py --json

# Print an `export MOTUS_JWT=...` line for shell use
python motus-get-token.py --print-export
```

The `MotusClient` auto-refreshes the token when no `MOTUS_JWT` is present or a
cached token has expired, so manual generation is optional.

### Debug API

A FastAPI-based debug service is available for testing individual employees and
troubleshooting sync issues — this is the recommended single-employee workflow.

```bash
# Development
ENV_FILE=.env.dev uvicorn src.presentation.api.debug_api:app --reload --port 8000

# Production
ENV_FILE=.env.prod uvicorn src.presentation.api.debug_api:app --port 8000
```

#### Debug API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ukg/employment-details/{employee_number}` | GET | Raw UKG employment data |
| `/ukg/employee-employment-details/{employee_number}` | GET | Employment details with project codes |
| `/ukg/person-details/{employee_id}` | GET | Raw UKG person data |
| `/ukg/supervisor-details/{employee_id}` | GET | Supervisor/manager data |
| `/motus/driver/{employee_id}` | GET | Current Motus driver data |
| `/build-driver` | POST | Build driver payload without syncing |
| `/compare` | POST | Compare UKG vs Motus data |
| `/validate-scenario` | POST | Validate a specific scenario |
| `/sync` | POST | Sync a single employee (with `dry_run` option) |

#### Example: Debug Single Employee Sync

```bash
curl -X POST "http://localhost:8000/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_number": "12345",
    "company_id": "J9A6Y",
    "dry_run": true
  }'
```

Interactive API docs are available at `http://localhost:8000/docs`.

---

## 7. API Reference

### UKG Pro Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/personnel/v1/employment-details` | GET | Employee employment data |
| `/personnel/v1/employee-employment-details` | GET | Employment details with project codes |
| `/personnel/v1/person-details` | GET | Personal information (address, phone) |
| `/personnel/v1/supervisor-details` | GET | Manager/supervisor information |

### Motus API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/drivers` | POST | Create new driver |
| `/drivers/{id}` | PUT | Update existing driver |
| token service | POST | Obtain JWT token (`MOTUS_TOKEN_URL`) |

### Driver Payload Schema (abridged)

```json
{
  "clientEmployeeId1": "12345",
  "programId": 21232,
  "firstName": "John",
  "lastName": "Doe",
  "address1": "123 Main St",
  "city": "Springfield",
  "stateProvince": "IL",
  "postalCode": "62701",
  "email": "john.doe@example.com",
  "phone": "555-123-4567",
  "startDate": "03/15/2024",
  "customVariables": [
    {"name": "Job Code", "value": "1103"},
    {"name": "Manager Name", "value": "Jane Manager"},
    {"name": "Derived Status", "value": "Active"}
  ]
}
```

---

## 8. SOW Compliance

### Implemented Features

| Feature | Status | Implementation |
|---------|--------|---------------|
| Rate Limiting | Implemented | Token bucket (`common/rate_limiter/`) |
| 429 Handling | Implemented | Retry-After support with backoff |
| Correlation IDs | Implemented | UUID v4 for request tracing (`common/correlation.py`) |
| PII Redaction | Implemented | Email/phone masking in logs (`common/redaction/`) |

### Correlation IDs

Each request is tagged with a unique correlation ID for tracing:

```python
correlation_id = str(uuid.uuid4())
headers["X-Correlation-ID"] = correlation_id
```

### PII Redaction

Sensitive data is redacted in logs (email/phone masking) via a logging filter
applied at configuration time.

---

## 9. Testing

### Test Structure

```
tests/
├── conftest.py
├── fixtures/          # motus_mocks.py, mock_data.py, ukg_mocks.py
├── unit/
│   ├── test_run_motus_batch.py
│   ├── test_manager_field.py
│   ├── test_leave_status.py
│   ├── test_motus_get_token.py
│   ├── test_upsert_motus_driver.py
│   ├── test_job_code_filter.py
│   └── test_notify.py
└── integration/
    ├── test_api_scenarios.py
    ├── test_debug_api_e2e.py
    ├── test_e2e_extended.py
    ├── test_token_flow.py
    ├── test_eeids.py
    └── test_e2e.py
```

### Running Tests

```bash
# Run all tests (coverage runs automatically via pyproject addopts)
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run a specific test file
pytest tests/unit/test_job_code_filter.py -v
```

Coverage is configured on `src` (`--cov=src`) with an HTML report written to
`htmlcov/` and a `fail_under = 90` threshold.

```bash
open htmlcov/index.html
```

---

## 10. Deployment

### Docker Deployment

#### Build Image

```bash
docker build -t matrix-ukg-motus:latest .
```

#### Dockerfile (as shipped)

```dockerfile
FROM python:3.11-slim
# ... non-root appuser, copies src/, common/, motus-get-token.py, requirements.txt
ENTRYPOINT ["python3", "-m", "src.presentation.cli.batch_runner"]
CMD []
```

Arguments (e.g. `--company-id J9A6Y --dry-run`) are appended at `docker run`.

#### Run Container

```bash
# Standard execution
docker run --rm \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  matrix-ukg-motus:latest \
  --company-id J9A6Y

# Dry run
docker run --rm \
  --env-file .env \
  matrix-ukg-motus:latest \
  --company-id J9A6Y --dry-run
```

### Azure Container Instance

```bash
az container create \
  --resource-group rg-matrix-integrations \
  --name matrix-ukg-motus \
  --image matrixacr.azurecr.io/matrix-ukg-motus:latest \
  --environment-variables \
    COMPANY_ID=J9A6Y \
  --secure-environment-variables \
    UKG_USERNAME=$UKG_USERNAME \
    UKG_PASSWORD=$UKG_PASSWORD \
    UKG_CUSTOMER_API_KEY=$UKG_CUSTOMER_API_KEY \
    MOTUS_LOGIN_ID=$MOTUS_LOGIN_ID \
    MOTUS_PASSWORD=$MOTUS_PASSWORD
```

### Scheduled Execution (Cron)

```bash
# Daily sync at 2 AM
0 2 * * * docker run --rm --env-file /opt/matrix/.env matrix-ukg-motus:latest --company-id J9A6Y >> /var/log/motus-sync.log 2>&1
```

---

## 11. Monitoring & Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed trace information (`DEBUG=1` or `LOG_LEVEL=DEBUG`) |
| INFO | Progress updates, processing stats |
| WARNING | Validation issues, skipped records |
| ERROR | API failures, critical errors |

### Log Format

```
[INFO] companyID=J9A6Y | workers=12 | dry_run=0 | batch_run_days=1
[INFO] Total employees from UKG: 1500
[INFO] Eligible employees (by job code): 450
[INFO] progress: 100/450 | saved=95 | skipped=3 | errors=2
[INFO] done: total=450 | saved=430 | skipped=12 | errors=8
```

### Debug Mode

Enable detailed logging with `DEBUG=1` (or `LOG_LEVEL=DEBUG`):

```
[DEBUG] GET https://service4.ultipro.com/personnel/v1/employment-details -> 200
[DEBUG] supervisor for 12345: Jane Manager
```

---

## 12. Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing UKG_CUSTOMER_API_KEY` | API key not configured | Set the environment variable |
| Token/JWT errors | Motus credentials missing or expired | Run `python motus-get-token.py --force --write-env` |
| `no employment details found` | Employee doesn't exist / outside change window | Verify employeeNumber and `--batch-run-days` |
| `no programId found` | Ineligible job code | Check `JOB_IDS` / eligible job codes |
| `HTTP error 401` | Authentication failed | Verify credentials |
| `HTTP error 429` | Rate limited | System auto-retries with backoff |

### Debugging Steps

1. **Enable debug mode**: Set `DEBUG=1`
2. **Check connectivity**: Verify network access to UKG/Motus
3. **Test one employee**: Use the Debug API `/sync` endpoint with `dry_run: true`
4. **Review logs**: Check for WARNING/ERROR messages
5. **Dry run**: Use `--dry-run` to validate payloads

### FAQ

**Q: Why are employees being skipped?**
A: Employees are skipped if they have ineligible job codes or fall outside the `--batch-run-days` change window.

**Q: How often should the JWT be refreshed?**
A: The client auto-refreshes when needed. Force a refresh only on persistent auth errors: `python motus-get-token.py --force --write-env`.

**Q: Can I run multiple batches in parallel?**
A: Not recommended. Use a single batch with increased `WORKERS` instead.

---

## 13. Security

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Employee PII | Sensitive | Redacted in logs |
| Credentials | Secret | Environment variables only |
| API Keys | Secret | Never logged |

**Note: This integration processes PII only. No PHI (Protected Health Information) is accessed or transmitted.**

### Authentication

| System | Method |
|--------|--------|
| UKG Pro | Basic Auth + Customer API Key header |
| Motus | JWT Bearer Token |

### Secrets Management

- All secrets stored as environment variables
- Never commit `.env` files to version control
- Use Azure Key Vault for production deployments
- Rotate credentials periodically

### Network Security

- All API communication over HTTPS
- TLS 1.2+ required
- No sensitive data in URL parameters

---

## 14. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-01 | Initial release |
| 1.1.0 | 2026-03-26 | Job code eligibility filtering; manager name field; leave-status derivation |
| 1.2.0 | 2026-04-03 | Automatic token refresh; DEV/PROD env separation; Debug API for single-employee troubleshooting |
| 1.3.0 | 2026-04 | Clean-architecture refactor: `python -m src.presentation.cli.batch_runner` entry point; legacy scripts moved to `_deprecated/`; change-window (`--batch-run-days`) filtering |

---

## 15. Support

### Contact

- **Team**: Matrix Medical Integration Team
- **Repository**: vai-matrix-ukg-motus-final

### Resources

- [UKG Pro API Documentation](https://developer.ukg.com/)
- [Motus API Documentation](https://developer.motus.com/)

### Escalation Path

1. Check the troubleshooting section
2. Review logs for error details
3. Contact the integration team
4. Escalate to platform support if needed
