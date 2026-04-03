# UKG Pro to Motus Driver Sync

Enterprise integration pipeline for synchronizing employee data from UKG Pro to Motus mileage reimbursement platform.

---

## Table of Contents

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

## 1. Overview

### Purpose

This integration automates the synchronization of employee data from UKG Pro (Ultimate Kronos Group) to Motus, a mileage reimbursement platform. It supports two reimbursement programs:

| Program | Program ID | Description |
|---------|------------|-------------|
| FAVR | 21232 | Fixed and Variable Rate reimbursement |
| CPM | 21233 | Cents Per Mile reimbursement |

### Key Features

- **Job Code Eligibility Filtering**: Only sync employees with eligible job codes
- **Employment Status Derivation**: Track Active, Leave, and Terminated status
- **Manager/Supervisor Tracking**: Include supervisor name in driver payload
- **Wave-Based Deployments**: Filter by US states for phased rollouts
- **Parallel Processing**: ThreadPoolExecutor for high-throughput batch operations
- **Dry-Run Mode**: Validate payloads without making API calls

---

## 2. Architecture

### Data Flow

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────┐     ┌─────────────┐
│   UKG Pro   │────▶│ build-motus-driver.py│────▶│upsert-motus-driver.py│────▶│   Motus API │
│     API     │     │   (Payload Builder)  │     │    (API Upserter)   │     │             │
└─────────────┘     └──────────────────────┘     └─────────────────────┘     └─────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │  run-motus-batch.py  │
                    │    (Orchestrator)    │
                    │                      │
                    │  ┌────────────────┐  │
                    │  │ThreadPoolExecutor│ │
                    │  │  (12 workers)  │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
```

### Self-Contained Repository

This repository is **fully self-contained** with all dependencies included locally for easy Azure deployment:

```
vai-matrix-ukg-motus-final/
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
├── build-motus-driver.py     # Build Motus driver payload from UKG
├── upsert-motus-driver.py    # Create/update Motus driver
├── run-motus-batch.py        # Batch orchestrator
├── motus-get-token.py        # JWT token management
├── Dockerfile                # Container definition
└── requirements.txt          # Python dependencies
```

All scripts import from the local `./common/` package:

```python
from common import (
    get_secrets_manager,
    get_rate_limiter,
    generate_correlation_id,
    redact_pii,
    # ... other imports
)
```

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| Payload Builder | `build-motus-driver.py` | Extracts UKG data and builds Motus driver payloads |
| API Upserter | `upsert-motus-driver.py` | Handles JWT auth, POST/PUT logic, retries |
| Batch Orchestrator | `run-motus-batch.py` | Parallel processing, state filtering, progress tracking |
| Token Manager | `motus-get-token.py` | JWT authentication and token refresh |

---

## 3. Business Logic

### 3.1 Job Code Eligibility (Pre-filter)

Only employees with eligible job codes are synchronized to Motus:

| Program | Job Codes | Count |
|---------|-----------|-------|
| FAVR (21232) | 1103, 4165, 4166, 1102, 1106, 4197, 4196 | 7 |
| CPM (21233) | 2817, 4121, 2157 | 3 |

**Total Eligible Job Codes: 10**

Employees with ineligible job codes are skipped during batch processing.

### 3.2 Program ID Mapping

Job codes map to Motus Program IDs:

```python
JOBCODE_TO_PROGRAM = {
    # FAVR (21232)
    "1103": 21232, "4165": 21232, "4166": 21232,
    "1102": 21232, "1106": 21232, "4197": 21232, "4196": 21232,
    # CPM (21233)
    "4154": 21233, "4152": 21233, "2817": 21233,
    "4121": 21233, "2157": 21233,
}
```

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

### 3.6 Wave-Based State Filtering

Supports phased deployments by US state:

| Wave | States | Example Start Date |
|------|--------|-------------------|
| 1 | FL, MS, NJ | Nov 1, 2025 |
| 2 | GA, KY, NC | Dec 1, 2025 |
| 3 | NY, MA, PA | Dec 15, 2025 |

---

## 4. Prerequisites

### System Requirements

- Python 3.11 or higher
- pip (Python package manager)
- Docker (for containerized deployment)

### Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
requests==2.31.0
python-dotenv==1.0.1
```

### Access Requirements

- UKG Pro API credentials (Basic Auth + Customer API Key)
- Motus API credentials (Login ID + Password for JWT)
- Network access to both UKG and Motus API endpoints

---

## 5. Configuration

### Environment Variables

Create a `.env` file or set environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKG_BASE_URL` | Yes | `https://service4.ultipro.com` | UKG Pro API base URL |
| `UKG_USERNAME` | Yes | - | UKG API username |
| `UKG_PASSWORD` | Yes | - | UKG API password |
| `UKG_CUSTOMER_API_KEY` | Yes | - | UKG Customer API Key header |
| `UKG_BASIC_B64` | No | - | Pre-encoded Base64 auth token |
| `MOTUS_LOGIN_ID` | Yes | - | Motus login ID |
| `MOTUS_PASSWORD` | Yes | - | Motus password |
| `MOTUS_API_BASE` | Yes | - | Motus API base URL |
| `MOTUS_JWT` | Yes | - | Motus JWT token (auto-generated) |
| `MOTUS_ENV` | No | `dev` | Environment: `dev` or `prod` |
| `COMPANY_ID` | Yes | `J9A6Y` | UKG Company ID |
| `STATES` | No | - | Comma-separated state filter |
| `WORKERS` | No | `12` | Thread pool size |
| `DEBUG` | No | `0` | Enable debug logging (0/1) |
| `DRY_RUN` | No | `0` | Validate only, no API calls (0/1) |
| `SAVE_LOCAL` | No | `0` | Save payloads to data/ (0/1) |
| `PROBE` | No | `0` | Check Motus before writing (0/1) |

### Example Configuration File

**matrix-ukg-motus.env:**
```bash
# UKG Configuration
UKG_BASE_URL=https://service4.ultipro.com
UKG_USERNAME=your-username
UKG_PASSWORD=your-password
UKG_CUSTOMER_API_KEY=your-customer-api-key

# Motus Configuration
MOTUS_LOGIN_ID=your-login-id
MOTUS_PASSWORD=your-password
MOTUS_API_BASE=https://api.motus.com/v1
MOTUS_JWT=your-jwt-token
MOTUS_ENV=prod

# Batch Configuration
COMPANY_ID=J9A6Y
WORKERS=12
DEBUG=0
```

---

## 6. Usage

### Single Employee Processing

Build a driver payload for one employee:

```bash
python build-motus-driver.py <employeeNumber> <companyID>

# Example
python build-motus-driver.py 12345 J9A6Y
```

Output is saved to `data/motus_driver_<employeeNumber>.json`.

### Batch Processing

Process all eligible employees:

```bash
# Full batch (all states)
python run-motus-batch.py --company-id J9A6Y

# Filter by states (wave deployment)
python run-motus-batch.py --company-id J9A6Y --states FL,MS,NJ

# Dry run (validate only)
python run-motus-batch.py --company-id J9A6Y --dry-run

# Save payloads locally
python run-motus-batch.py --company-id J9A6Y --save-local

# Custom worker count
python run-motus-batch.py --company-id J9A6Y --workers 24

# Combined options
python run-motus-batch.py --company-id J9A6Y --states FL,MS --dry-run --save-local --probe
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--company-id` | UKG Company ID (required) |
| `--states` | Comma-separated US state codes |
| `--workers` | Thread pool size |
| `--dry-run` | Validate without API calls |
| `--save-local` | Save JSON payloads to data/batch/ |
| `--probe` | Check Motus state before writing |

### Token Management

#### Manual Token Generation

Generate a new Motus JWT token:

```bash
# Generate token and print to stdout
python motus-get-token.py

# Generate token and write to .env file
python motus-get-token.py --write-env

# Force refresh (ignore cache)
python motus-get-token.py --force --write-env

# Output as JSON with expiration details
python motus-get-token.py --json
```

#### Automatic Token Refresh

The `MotusClient` automatically refreshes the token when:
- No `MOTUS_JWT` is found on initialization
- A 401/403 authentication error is received

This eliminates the need to manually refresh tokens before batch runs.

```python
# Token is auto-refreshed if missing or expired
from src.infrastructure.adapters.motus import MotusClient
client = MotusClient()  # Auto-refreshes token if needed
```

### Environment-Specific Configuration

The system supports separate configuration files for Development and Production environments.

#### Environment Files

| File | Purpose | Key Settings |
|------|---------|--------------|
| `.env.dev` | Development | `DRY_RUN=1`, `DEBUG=1`, `WORKERS=4` |
| `.env.prod` | Production | `DRY_RUN=0`, `DEBUG=0`, `WORKERS=12` |
| `.env` | Default fallback | Used if no specific env file found |

#### Switching Environments

**Option 1: Using ENV_FILE (Recommended)**

```bash
# Development
ENV_FILE=.env.dev python motus-get-token.py --write-env --env-path .env.dev
ENV_FILE=.env.dev python run-motus-batch.py --company-id J9A6Y

# Production
ENV_FILE=.env.prod python motus-get-token.py --write-env --env-path .env.prod
ENV_FILE=.env.prod python run-motus-batch.py --company-id J9A6Y
```

**Option 2: Using ENV_NAME**

```bash
# Development (auto-selects .env.dev)
ENV_NAME=development python run-motus-batch.py --company-id J9A6Y

# Production (auto-selects .env.prod)
ENV_NAME=production python run-motus-batch.py --company-id J9A6Y
```

#### Environment Priority

The secrets manager loads configuration in this order:
1. `ENV_FILE` environment variable (explicit override)
2. `.env.dev` if `ENV_NAME=development`
3. `.env.prod` if `ENV_NAME=production`
4. `.env` (default fallback)
5. Project-specific files (`matrix-ukg-motus.env`, etc.)

### Debug API

A FastAPI-based debug API is available for testing individual employees and troubleshooting sync issues.

#### Starting the Debug API

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
| `/ukg/employment-details/{emp_num}` | GET | Raw UKG employment data |
| `/ukg/person-details/{emp_id}` | GET | Raw UKG person data |
| `/motus/driver/{emp_num}` | GET | Current Motus driver data |
| `/build-driver` | POST | Build driver payload without syncing |
| `/compare` | POST | Compare UKG vs Motus data |
| `/validate-scenario` | POST | Validate specific scenario |
| `/sync` | POST | Sync single employee (with dry_run option) |

#### Example: Debug Single Employee Sync

```bash
# Dry run - validate without making changes
curl -X POST "http://localhost:8000/sync?include_trace=true" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_number": "12345",
    "company_id": "J9A6Y",
    "dry_run": true
  }'
```

The response includes a detailed trace of:
- All UKG API calls and responses
- Data transformations applied
- Motus API request and response

#### Swagger Documentation

Interactive API docs available at: `http://localhost:8000/docs`

---

## 7. API Reference

### UKG Pro Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/personnel/v1/employment-details` | GET | Employee employment data |
| `/personnel/v1/employee-employment-details` | GET | Employment details with project codes |
| `/personnel/v1/person-details` | GET | Personal information (address, phone) |
| `/personnel/v1/supervisor-details` | GET | Manager/supervisor information |
| `/configuration/v1/locations/{code}` | GET | Location details |

### Motus API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/drivers` | POST | Create new driver |
| `/drivers/{id}` | PUT | Update existing driver |
| `/auth/token` | POST | Obtain JWT token |

### Driver Payload Schema

```json
{
  "clientEmployeeId1": "12345",
  "clientEmployeeId2": null,
  "programId": 21232,
  "firstName": "John",
  "lastName": "Doe",
  "address1": "123 Main St",
  "address2": "Apt 456",
  "city": "Springfield",
  "stateProvince": "IL",
  "country": "US",
  "postalCode": "62701",
  "email": "john.doe@example.com",
  "phone": "555-123-4567",
  "alternatePhone": "555-987-6543",
  "startDate": "03/15/2024",
  "endDate": "",
  "leaveStartDate": "",
  "leaveEndDate": "",
  "annualBusinessMiles": 0,
  "commuteDeductionType": null,
  "commuteDeductionCap": null,
  "customVariables": [
    {"name": "Project Code", "value": "PROJ001"},
    {"name": "Project", "value": "Project Name"},
    {"name": "Job Code", "value": "1103"},
    {"name": "Job", "value": "Sales Representative"},
    {"name": "Location Code", "value": "Main Office"},
    {"name": "Location", "value": "IL"},
    {"name": "Org Level 1 Code", "value": "ORG1"},
    {"name": "Org Level 2 Code", "value": "ORG2"},
    {"name": "Org Level 3 Code", "value": "ORG3"},
    {"name": "Org Level 4 Code", "value": "ORG4"},
    {"name": "Full/Part Time Code", "value": "F"},
    {"name": "Employment Type Code", "value": "REG"},
    {"name": "Employment Status Code", "value": "A"},
    {"name": "Last Hire", "value": "01/15/2020"},
    {"name": "Termination Date", "value": ""},
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
| Rate Limiting | Implemented | Token bucket algorithm in upserter |
| 429 Handling | Implemented | Retry-After header support with backoff |
| Correlation IDs | Implemented | UUID v4 for request tracing |
| PII Redaction | Implemented | Email/phone masking in logs |

### Rate Limiting

The system implements a token bucket algorithm to respect API rate limits:

```python
class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0

    def acquire(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()
```

### 429 Handling

When rate limited, the system respects the `Retry-After` header:

```python
def handle_rate_limit(response):
    retry_after = response.headers.get("Retry-After", 60)
    time.sleep(int(retry_after))
```

### Correlation IDs

Each request includes a unique correlation ID for tracing:

```python
correlation_id = str(uuid.uuid4())
headers["X-Correlation-ID"] = correlation_id
```

### PII Redaction

Sensitive data is redacted in logs:

```python
def redact_email(email):
    # john.doe@example.com → jo***@example.com
    local, domain = email.split('@')
    return f"{local[:2]}***@{domain}"
```

---

## 9. Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── __init__.py
│   ├── test_build_motus_driver.py
│   ├── test_upsert_motus_driver.py
│   ├── test_run_motus_batch.py
│   ├── test_job_code_filter.py
│   ├── test_manager_field.py
│   ├── test_leave_status.py
│   ├── test_rate_limiter.py
│   └── test_notify.py
└── integration/
    ├── __init__.py
    ├── test_e2e.py
    └── test_eeids.py
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
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_job_code_filter.py -v
```

### Test Coverage

| Component | Coverage |
|-----------|----------|
| Overall | 93% |
| src/application/services | 96-99% |
| src/domain/models | 94-100% |
| src/infrastructure/adapters | 89-91% |
| src/presentation/api | 89-91% |

**Total Tests: 819**

Run tests with coverage:
```bash
python -m pytest tests/unit/ -v --cov=src --cov-report=term-missing --cov-fail-under=90
```

### Test EEIDs

Integration tests use real-world test EEIDs:

| Category | EEIDs |
|----------|-------|
| New Hires | 28190, 28203, 28207, 28209, 28210, 28199, 28206, 28189, 28204 |
| Terminations | 26737, 27991, 28069, 23497, 27938, 23463, 26612, 25213, 28010 |
| Manager Changes | 28195 |
| Address/Phone | 25336, 26421, 10858, 22299 |

---

## 10. Deployment

### Docker Deployment

#### Build Image

```bash
docker build -t matrix-ukg-motus:latest .
```

#### Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["python", "run-motus-batch.py"]
CMD []
```

#### Run Container

```bash
# Standard execution
docker run --rm \
  --env-file matrix-ukg-motus.env \
  -v "$(pwd)/data:/app/data" \
  matrix-ukg-motus:latest \
  --company-id J9A6Y

# With state filter
docker run --rm \
  --env-file matrix-ukg-motus.env \
  -v "$(pwd)/data:/app/data" \
  matrix-ukg-motus:latest \
  --company-id J9A6Y --states FL,MS,NJ

# Dry run
docker run --rm \
  --env-file matrix-ukg-motus.env \
  matrix-ukg-motus:latest \
  --company-id J9A6Y --dry-run
```

### Azure Container Instance

```bash
# Create container instance
az container create \
  --resource-group rg-matrix-integrations \
  --name matrix-ukg-motus \
  --image matrixacr.azurecr.io/matrix-ukg-motus:latest \
  --environment-variables \
    COMPANY_ID=J9A6Y \
    MOTUS_ENV=prod \
  --secure-environment-variables \
    UKG_USERNAME=$UKG_USERNAME \
    UKG_PASSWORD=$UKG_PASSWORD \
    UKG_CUSTOMER_API_KEY=$UKG_CUSTOMER_API_KEY \
    MOTUS_JWT=$MOTUS_JWT
```

### Scheduled Execution (Cron)

```bash
# Daily sync at 2 AM
0 2 * * * docker run --rm --env-file /opt/matrix/matrix-ukg-motus.env matrix-ukg-motus:latest --company-id J9A6Y >> /var/log/motus-sync.log 2>&1
```

---

## 11. Monitoring & Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed trace information (requires `DEBUG=1`) |
| INFO | Progress updates, processing stats |
| WARN | Validation issues, skipped records |
| ERROR | API failures, critical errors |

### Log Format

```
[INFO] companyID=J9A6Y | states=FL,MS,NJ | workers=12 | dry_run=0
[INFO] Total employees from UKG: 1500
[INFO] Eligible employees (by job code): 450
[INFO] progress: 100/450 | saved=95 | skipped=3 | errors=2
[INFO] progress: 200/450 | saved=190 | skipped=6 | errors=4
[INFO] done: total=450 | saved=430 | skipped=12 | errors=8
```

### Debug Mode

Enable detailed logging with `DEBUG=1`:

```
[DEBUG] GET https://service4.ultipro.com/personnel/v1/employment-details -> 200
[DEBUG] list len=1500; first keys=['employeeNumber', 'employeeId', ...]
[DEBUG] supervisor for 12345: Jane Manager
[DEBUG] skip emp=12346 state=CA
```

### Progress Reporting

Batch processing reports progress every 100 records:

```
[INFO] progress: 100/450 | saved=95 | skipped=3 | errors=2
```

---

## 12. Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing MOTUS_JWT` | JWT token not set or expired | Run `python motus-get-token.py` |
| `Missing UKG_CUSTOMER_API_KEY` | API key not configured | Set environment variable |
| `no employment details found` | Employee doesn't exist | Verify employeeNumber in UKG |
| `no programId found` | Ineligible job code | Check ELIGIBLE_JOB_CODES |
| `HTTP error 401` | Authentication failed | Verify credentials |
| `HTTP error 429` | Rate limited | System auto-retries |

### Debugging Steps

1. **Enable debug mode**: Set `DEBUG=1`
2. **Check connectivity**: Verify network access to UKG/Motus
3. **Validate credentials**: Test with single employee first
4. **Review logs**: Check for WARN/ERROR messages
5. **Dry run**: Use `--dry-run` to validate payloads

### FAQ

**Q: Why are employees being skipped?**
A: Employees are skipped if they have ineligible job codes or don't match the state filter.

**Q: How often should the JWT be refreshed?**
A: The system now auto-refreshes the JWT token when needed. Manual refresh is only required if you see persistent authentication errors. Run `python motus-get-token.py --write-env --force` to force a refresh.

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
| 1.0.1 | 2025-11-15 | Added state filtering for wave deployments |
| 1.0.2 | 2025-12-01 | Improved error handling and retry logic |
| 1.1.0 | 2026-03-26 | Added job code eligibility filtering |
| 1.1.0 | 2026-03-26 | Added manager/supervisor name field |
| 1.1.0 | 2026-03-26 | Added leave of absence status derivation |
| 1.1.0 | 2026-03-26 | Added comprehensive test suite (235 tests, 91% coverage) |
| 1.2.0 | 2026-04-03 | Added automatic token refresh in MotusClient |
| 1.2.0 | 2026-04-03 | Added DEV/PROD environment separation (.env.dev, .env.prod) |
| 1.2.0 | 2026-04-03 | Added Debug API for single employee troubleshooting |
| 1.2.0 | 2026-04-03 | Enhanced correlation ID logging throughout |
| 1.2.0 | 2026-04-03 | Test coverage improved to 93% (819 tests) |

---

## 15. Support

### Contact

- **Team**: Matrix Medical Integration Team
- **Repository**: vai-matrix-ukg-motus-final

### Resources

- [UKG Pro API Documentation](https://developer.ukg.com/)
- [Motus API Documentation](https://developer.motus.com/)

### Escalation Path

1. Check troubleshooting section
2. Review logs for error details
3. Contact integration team
4. Escalate to platform support if needed
