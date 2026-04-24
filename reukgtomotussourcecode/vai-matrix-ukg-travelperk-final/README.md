# UKG Pro to TravelPerk SCIM User Sync

Enterprise integration pipeline for provisioning and synchronizing employee data from UKG Pro to TravelPerk travel management platform using SCIM 2.0 protocol.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Business Logic](#3-business-logic)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start - Local Development](#5-quick-start---local-development)
6. [Configuration](#6-configuration)
7. [Usage](#7-usage)
8. [API Reference](#8-api-reference)
9. [SOW Compliance](#9-sow-compliance)
10. [Testing](#10-testing)
11. [Deployment](#11-deployment)
12. [Monitoring & Logging](#12-monitoring--logging)
13. [Troubleshooting](#13-troubleshooting)
14. [Security](#14-security)
15. [Change Log](#15-change-log)
16. [Support](#16-support)

---

## 1. Overview

### Purpose

This integration automates the provisioning and synchronization of employee data from UKG Pro (Ultimate Kronos Group) to TravelPerk, a corporate travel management platform. It uses the SCIM 2.0 (System for Cross-domain Identity Management) protocol for standardized user management.

### Key Features

- **SCIM 2.0 Compliance**: Standard protocol for user provisioning
- **Two-Phase Supervisor Hierarchy**: Handle manager relationships correctly
- **User Deactivation**: Automatic deactivation on termination
- **Rate Limiting**: Built-in rate limiting with 429 handling
- **Parallel Processing**: ThreadPoolExecutor for high-throughput batch operations
- **Dry-Run Mode**: Validate payloads without making API calls

### Protocol

TravelPerk implements SCIM 2.0 (RFC 7644) for user provisioning:
- Standard user schema with enterprise extensions
- Filter-based user lookup
- PATCH operations for partial updates

---

## 2. Architecture

### Data Flow

```
┌─────────────┐     ┌────────────────────────┐     ┌───────────────────────┐     ┌───────────────┐
│   UKG Pro   │────▶│build-travelperk-user.py│────▶│upsert-travelperk-user.py│────▶│TravelPerk SCIM│
│     API     │     │   (Payload Builder)    │     │     (SCIM Upserter)   │     │      API      │
└─────────────┘     └────────────────────────┘     └───────────────────────┘     └───────────────┘
                              │
                              ▼
                    ┌────────────────────────┐
                    │ run-travelperk-batch.py│
                    │     (Orchestrator)     │
                    │                        │
                    │  ┌──────────────────┐  │
                    │  │  Phase 1: Insert │  │
                    │  │  (no supervisor) │  │
                    │  └──────────────────┘  │
                    │           ↓            │
                    │  ┌──────────────────┐  │
                    │  │  Phase 2: Update │  │
                    │  │ (with manager.value)│
                    │  └──────────────────┘  │
                    └────────────────────────┘
```

### Self-Contained Repository

This repository is **fully self-contained** with all dependencies included locally for easy Azure deployment:

```
vai-matrix-ukg-travelperk-final/
├── common/                       # Shared utility modules (local copy)
│   ├── __init__.py
│   ├── secrets_manager.py        # SOW 2.6 - Secrets management
│   ├── rate_limiter.py           # SOW 5.1, 5.2 - Rate limiting
│   ├── correlation.py            # SOW 7.2 - Correlation IDs & logging
│   ├── notifications.py          # SOW 4.6 - Email notifications
│   ├── metrics.py                # SOW 4.7, 7.3 - Metrics collection
│   ├── report_generator.py       # SOW 4.7, 7.3, 10.4 - Report generation
│   ├── redaction.py              # SOW 7.4, 7.5, 9.4 - PII redaction
│   └── validators.py             # SOW 3.6, 3.7 - Input validation
├── build-travelperk-user.py      # Build SCIM user payload from UKG
├── upsert-travelperk-user.py     # Create/update TravelPerk user
├── run-travelperk-batch.py       # Two-phase batch orchestrator
├── Dockerfile                    # Container definition
└── requirements.txt              # Python dependencies
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
| Payload Builder | `build-travelperk-user.py` | Builds SCIM-compliant user payloads from UKG data |
| SCIM Upserter | `upsert-travelperk-user.py` | Handles SCIM API operations with retry logic |
| Batch Orchestrator | `run-travelperk-batch.py` | Two-phase batch processing with parallel execution |

---

## 3. Business Logic

### 3.1 SCIM Operations

| Operation | HTTP Method | Endpoint | Description |
|-----------|-------------|----------|-------------|
| Create User | POST | `/api/v2/scim/Users` | Create new user in TravelPerk |
| Update User | PATCH | `/api/v2/scim/Users/{id}` | Partial update existing user |
| Get User | GET | `/api/v2/scim/Users/{id}` | Retrieve user by ID |
| Search Users | GET | `/api/v2/scim/Users?filter=` | Search users by attribute |

### 3.2 Two-Phase Supervisor Hierarchy

TravelPerk requires the manager's TravelPerk ID (not employee number) for the `manager.value` field. This requires a two-phase approach:

**Phase 1: Insert Users Without Supervisor**
1. Fetch all employees from UKG
2. Build SCIM payloads (without manager reference)
3. Create users in TravelPerk
4. Build mapping: `employeeNumber` → `TravelPerk ID`

**Phase 2: Update Users With Supervisor**
1. For each user with a supervisor in UKG
2. Look up supervisor's TravelPerk ID from Phase 1 mapping
3. PATCH user with `manager.value` = supervisor's TravelPerk ID

### 3.3 User Deactivation

When an employee is terminated in UKG:
- The `terminationDate` field is set
- System sets `active: false` in TravelPerk
- User can no longer book travel

**Note**: TravelPerk SCIM does not support `endDate`. Termination is handled via the `active` boolean.

### 3.4 Field Mapping

| UKG Field | UKG Endpoint | TravelPerk SCIM Field |
|-----------|--------------|----------------------|
| `employeeNumber` | employee-employment-details | `externalId` |
| `emailAddress` | person-details | `userName` |
| `firstName` | person-details | `name.givenName` |
| `lastName` | person-details | `name.familyName` |
| `primaryProjectCode` | employee-employment-details | `urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:costCenter` |
| `terminationDate` | employment-details | `active` (boolean, inverted) |
| `supervisorEmployeeNumber` | supervisor-details | `urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:manager.value` |

### 3.5 SCIM Payload Schema

```json
{
  "schemas": [
    "urn:ietf:params:scim:schemas:core:2.0:User",
    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
  ],
  "userName": "john.doe@example.com",
  "externalId": "12345",
  "name": {
    "givenName": "John",
    "familyName": "Doe"
  },
  "active": true,
  "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
    "costCenter": "PROJ001",
    "manager": {
      "value": "tp-user-id-of-manager"
    }
  }
}
```

---

## 4. Prerequisites

### System Requirements

- Python 3.11 or higher
- pip (Python package manager)
- Docker (for containerized deployment, optional)

### Access Requirements

- UKG Pro API credentials (Basic Auth + Customer API Key)
- TravelPerk API key (Admin access required)
- Network access to both UKG and TravelPerk API endpoints

---

## 5. Quick Start - Local Development

Follow these steps to run the batch from your local machine:

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd vai-matrix-ukg-travelperk-final
```

### Step 2: Create and Activate Virtual Environment

**macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
```

**Required variables in `.env`:**
```bash
# UKG Configuration
UKG_BASE_URL=https://service4.ultipro.com
UKG_USERNAME=your-username
UKG_PASSWORD=your-password
UKG_CUSTOMER_API_KEY=your-customer-api-key

# TravelPerk Configuration
TRAVELPERK_API_BASE=https://app.sandbox-travelperk.com
TRAVELPERK_API_KEY=your-api-key

# Batch Settings
COMPANY_ID=J9A6Y
WORKERS=12
```

### Step 5: Run the Batch

```bash
# Test with dry-run first (validates without making API calls)
python run-travelperk-batch.py --company-id J9A6Y --limit 5 --dry-run

# Run with a small batch
python run-travelperk-batch.py --company-id J9A6Y --limit 10

# Run full batch
python run-travelperk-batch.py --company-id J9A6Y
```

### Quick Reference - CLI Options

| Option | Example | Description |
|--------|---------|-------------|
| `--company-id` | `J9A6Y` | **Required** - UKG Company ID |
| `--dry-run` | - | Validate payloads without API calls |
| `--limit` | `10` | Process only N records (for testing) |
| `--states` | `FL,MS,NJ` | Filter by US state codes |
| `--employee-type-codes` | `FTC,HRC` | Filter by employee types |
| `--workers` | `12` | Thread pool size (default: 12) |
| `--save-local` | - | Save JSON payloads to `data/batch/` |
| `--insert-supervisor` | `004295` | Pre-insert supervisor(s) |

### Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Verify dependencies
pip list | grep -E "requests|python-dotenv"

# Test import
python -c "from src.presentation.cli.batch_runner import main; print('Import OK')"
```

---

## 6. Configuration

### Environment Variables

Create a `matrix-ukg-tp.env` file or set environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKG_BASE_URL` | Yes | `https://service4.ultipro.com` | UKG Pro API base URL |
| `UKG_USERNAME` | Yes | - | UKG API username |
| `UKG_PASSWORD` | Yes | - | UKG API password |
| `UKG_CUSTOMER_API_KEY` | Yes | - | UKG Customer API Key header |
| `UKG_BASIC_B64` | No | - | Pre-encoded Base64 auth token |
| `TRAVELPERK_API_BASE` | Yes | - | TravelPerk API base URL |
| `TRAVELPERK_API_KEY` | Yes | - | TravelPerk API key |
| `COMPANY_ID` | Yes | `J9A6Y` | UKG Company ID |
| `STATES` | No | - | Comma-separated state filter |
| `WORKERS` | No | `12` | Thread pool size |
| `RATE_LIMIT_CALLS_PER_MINUTE` | No | `60` | API rate limit |
| `REDACT_PII` | No | `1` | Redact PII in logs (0/1) |
| `DEBUG` | No | `0` | Enable debug logging (0/1) |
| `MAX_RETRIES` | No | `2` | Max retry attempts |

### Environment URLs

| Environment | URL |
|-------------|-----|
| Sandbox | `https://app.sandbox-travelperk.com` |
| Production | `https://app.travelperk.com` |

### Example Configuration File

**matrix-ukg-tp.env:**
```bash
# UKG Configuration
UKG_BASE_URL=https://service4.ultipro.com
UKG_USERNAME=your-username
UKG_PASSWORD=your-password
UKG_CUSTOMER_API_KEY=your-customer-api-key

# TravelPerk Configuration
TRAVELPERK_API_BASE=https://app.sandbox-travelperk.com
TRAVELPERK_API_KEY=your-api-key

# Compliance Settings
RATE_LIMIT_CALLS_PER_MINUTE=60
REDACT_PII=1

# Batch Configuration
COMPANY_ID=J9A6Y
WORKERS=12
DEBUG=0
```

---

## 7. Usage

### Single Employee Processing

Build a SCIM payload for one employee:

```bash
python build-travelperk-user.py <employeeNumber>

# Example
python build-travelperk-user.py 000479
```

Upsert a single employee to TravelPerk:

```bash
python upsert-travelperk-user.py <employeeNumber> [--dry-run]

# Example
python upsert-travelperk-user.py 000479
python upsert-travelperk-user.py 000479 --dry-run
```

### Batch Processing

Process all employees:

```bash
# Full batch
python run-travelperk-batch.py --company-id J9A6Y

# Limit number of records
python run-travelperk-batch.py --company-id J9A6Y --limit 10

# Filter by states
python run-travelperk-batch.py --company-id J9A6Y --states FL,MS,NJ

# Filter by employee type codes
python run-travelperk-batch.py --company-id J9A6Y --employee-type-codes FTC,HRC,TMC

# Dry run (validate only)
python run-travelperk-batch.py --company-id J9A6Y --dry-run

# Insert supervisor first (for testing)
python run-travelperk-batch.py --company-id J9A6Y --insert-supervisor 004295 --limit 1

# Combined options
python run-travelperk-batch.py --company-id J9A6Y --states FL,MS --limit 50 --dry-run
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--company-id` | UKG Company ID (required) |
| `--limit` | Maximum number of records to process |
| `--states` | Comma-separated US state codes |
| `--employee-type-codes` | Comma-separated employee type filters |
| `--dry-run` | Validate without API calls |
| `--insert-supervisor` | Insert specific supervisor first |

### Recommended Workflow

1. **Test with dry-run**: Validate payloads without API calls
2. **Insert supervisors**: If required, insert managers first
3. **Small batch test**: Run with `--limit 10` to verify
4. **Full batch**: Run complete batch
5. **Validate results**: Check `data/batch/*.json` outputs

---

## 8. API Reference

### UKG Pro Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/personnel/v1/employee-employment-details` | GET | Employment details with project codes |
| `/personnel/v1/person-details` | GET | Personal information (name, email) |
| `/personnel/v1/employee-supervisor-details` | GET | Supervisor relationships |

### TravelPerk SCIM Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/scim/Users` | GET | List/search users |
| `/api/v2/scim/Users` | POST | Create new user |
| `/api/v2/scim/Users/{id}` | GET | Get user by ID |
| `/api/v2/scim/Users/{id}` | PUT | Full user update |
| `/api/v2/scim/Users/{id}` | PATCH | Partial user update |

### SCIM Filter Queries

```bash
# Find user by externalId
GET /api/v2/scim/Users?filter=externalId eq "12345"

# Find user by email
GET /api/v2/scim/Users?filter=userName eq "john.doe@example.com"
```

### PATCH Operations Format

```json
{
  "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
  "Operations": [
    {
      "op": "replace",
      "path": "active",
      "value": false
    },
    {
      "op": "replace",
      "path": "name.givenName",
      "value": "Jonathan"
    },
    {
      "op": "replace",
      "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:manager",
      "value": {"value": "tp-manager-id"}
    }
  ]
}
```

---

## 9. SOW Compliance

### Implemented Features

| Feature | Status | Implementation | Code Location |
|---------|--------|---------------|---------------|
| Rate Limiting | Implemented | Token bucket algorithm | `upsert-travelperk-user.py:39-54` |
| 429 Handling | Implemented | Retry-After header support | `upsert-travelperk-user.py:60-72` |
| Correlation IDs | Implemented | UUID v4 for request tracing | `upsert-travelperk-user.py:75-92` |
| PII Redaction | Implemented | Email masking in logs | `upsert-travelperk-user.py:95-119` |

### Rate Limiting

The system implements a token bucket algorithm to respect API rate limits:

```python
class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0

    def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()
```

### 429 Handling

When rate limited (HTTP 429), the system respects the `Retry-After` header:

```python
def handle_rate_limit(resp: requests.Response) -> int:
    """
    Handle 429 Too Many Requests response.
    Returns the number of seconds to wait before retrying.
    """
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            pass
    # Default: 60 seconds if no Retry-After header
    return 60
```

### Correlation IDs

Each request includes a unique correlation ID (UUID v4) for distributed tracing:

```python
def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())

def _log(msg: str) -> None:
    if DEBUG:
        cid = f"[{_current_correlation_id}] " if _current_correlation_id else ""
        print(f"[DEBUG] {cid}{msg}")
```

### PII Redaction

Sensitive data is automatically redacted in logs:

```python
def redact_email(email: str) -> str:
    """Redact email address for logging."""
    if not email or '@' not in email:
        return "***"
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f"***@{domain}"
    return f"{local[:2]}***@{domain}"

# Example: john.doe@example.com → jo***@example.com
```

---

## 10. Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── __init__.py
│   ├── test_build_travelperk_user.py
│   ├── test_upsert_travelperk_user.py
│   ├── test_run_travelperk_batch.py
│   └── test_rate_limiter.py
└── integration/
    ├── __init__.py
    └── test_e2e.py
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
pytest tests/unit/test_rate_limiter.py -v
```

### Test Categories

| Test File | Coverage |
|-----------|----------|
| `test_rate_limiter.py` | Rate limiting functionality |
| `test_build_travelperk_user.py` | SCIM payload building |
| `test_upsert_travelperk_user.py` | SCIM API operations |
| `test_run_travelperk_batch.py` | Batch orchestration |
| `test_e2e.py` | End-to-end flow |

---

## 11. Deployment

### Docker Deployment

#### Build Image

```bash
docker build -t vai-matrix-ukg-travelperk .
```

#### Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY build-travelperk-user.py upsert-travelperk-user.py run-travelperk-batch.py /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/data

ENTRYPOINT ["python3", "run-travelperk-batch.py"]
CMD []
```

#### Run Container

```bash
# Dry-run with limit
docker run --rm \
  --env-file matrix-ukg-tp.env \
  -v $(pwd)/data:/app/data \
  vai-matrix-ukg-travelperk \
  --company-id J9A6Y --limit 1 --dry-run

# Full batch processing
docker run --rm \
  --env-file matrix-ukg-tp.env \
  -v $(pwd)/data:/app/data \
  vai-matrix-ukg-travelperk \
  --company-id J9A6Y

# With filters
docker run --rm \
  --env-file matrix-ukg-tp.env \
  -v $(pwd)/data:/app/data \
  vai-matrix-ukg-travelperk \
  --company-id J9A6Y --states FL,MS,NJ --employee-type-codes FTC,HRC,TMC

# Insert supervisor first
docker run --rm \
  --env-file matrix-ukg-tp.env \
  vai-matrix-ukg-travelperk \
  --company-id J9A6Y --insert-supervisor 004295 --limit 1
```

### Azure Container Instance

```bash
# Create container instance
az container create \
  --resource-group rg-matrix-integrations \
  --name matrix-ukg-travelperk \
  --image matrixacr.azurecr.io/vai-matrix-ukg-travelperk:latest \
  --environment-variables \
    COMPANY_ID=J9A6Y \
  --secure-environment-variables \
    UKG_USERNAME=$UKG_USERNAME \
    UKG_PASSWORD=$UKG_PASSWORD \
    UKG_CUSTOMER_API_KEY=$UKG_CUSTOMER_API_KEY \
    TRAVELPERK_API_KEY=$TRAVELPERK_API_KEY
```

### Scheduled Execution (Cron)

```bash
# Daily sync at 3 AM
0 3 * * * docker run --rm --env-file /opt/matrix/matrix-ukg-tp.env vai-matrix-ukg-travelperk --company-id J9A6Y >> /var/log/travelperk-sync.log 2>&1
```

---

## 12. Monitoring & Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed trace information (requires `DEBUG=1`) |
| INFO | Progress updates, processing stats |
| WARN | Validation issues, skipped records |
| ERROR | API failures, critical errors |

### Log Format with Correlation ID

```
[DEBUG] [a1b2c3d4-e5f6-7890-abcd-ef1234567890] GET /api/v2/scim/Users?filter=externalId eq "12345"
[DEBUG] [a1b2c3d4-e5f6-7890-abcd-ef1234567890] POST /api/v2/scim/Users
```

### PII Redaction in Logs

With `REDACT_PII=1` (default):
```
[DEBUG] GET /api/v2/scim/Users?filter=userName eq "jo***@example.com"
```

Without redaction (`REDACT_PII=0`):
```
[DEBUG] GET /api/v2/scim/Users?filter=userName eq "john.doe@example.com"
```

### Result Output

Each operation outputs JSON result:

```json
{
  "action": "insert",
  "status": 201,
  "id": "tp-user-id-12345",
  "externalId": "12345",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## 13. Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing TRAVELPERK_API_KEY` | API key not set | Set environment variable |
| `Missing required fields` | Invalid payload | Check UKG data completeness |
| `409 Conflict` | User exists by email | System auto-updates existing user |
| `429 Too Many Requests` | Rate limited | System auto-retries with backoff |
| `401 Unauthorized` | Invalid API key | Verify TRAVELPERK_API_KEY |
| `User created but no id` | Unexpected API response | Check TravelPerk API status |

### Debugging Steps

1. **Enable debug mode**: Set `DEBUG=1`
2. **Disable PII redaction**: Set `REDACT_PII=0` (temporarily)
3. **Test single employee**: Use `upsert-travelperk-user.py` directly
4. **Check correlation ID**: Trace requests through logs
5. **Dry run**: Use `--dry-run` to validate payloads

### 409 Conflict Resolution

When a user already exists by email (userName), the system automatically:
1. Detects the 409 response
2. Searches for existing user by userName
3. Updates the existing user via PATCH
4. Returns success with `action: "update"`

### FAQ

**Q: Why is the manager field empty after insert?**
A: Managers are assigned in Phase 2. Run the full batch to populate manager relationships.

**Q: Can I sync only terminated employees?**
A: Use the employee type code filter or process specific employee numbers.

**Q: What happens if a supervisor doesn't exist in TravelPerk?**
A: The manager field will be empty. Insert supervisors first using `--insert-supervisor`.

---

## 14. Security

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Employee PII | Sensitive | Redacted in logs by default |
| Email Addresses | PII | Masked (jo***@domain.com) |
| API Keys | Secret | Environment variables only |

**Note: This integration processes PII only. No PHI (Protected Health Information) is accessed or transmitted.**

### Authentication

| System | Method |
|--------|--------|
| UKG Pro | Basic Auth + Customer API Key header |
| TravelPerk | API Key in Authorization header |

### TravelPerk Auth Header

```
Authorization: ApiKey your-api-key-here
```

### Secrets Management

- All secrets stored as environment variables
- Never commit `.env` files to version control
- Use Azure Key Vault for production deployments
- PII redaction enabled by default (`REDACT_PII=1`)

### Network Security

- All API communication over HTTPS
- TLS 1.2+ required
- No sensitive data in URL parameters (except filter queries)

---

## 15. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-01 | Initial release |
| 1.0.1 | 2025-12-10 | Added state and employee type filtering |
| 1.1.0 | 2026-03-26 | Added SOW compliance features (rate limiting, 429 handling, correlation IDs, PII redaction) |
| 1.1.0 | 2026-03-26 | Added comprehensive test suite |

---

## 16. Support

### Contact

- **Team**: Matrix Medical Integration Team
- **Repository**: vai-matrix-ukg-travelperk-final

### Sandbox Access

- **URL**: https://app.sandbox-travelperk.com/login
- **API Documentation**: https://developers.travelperk.com/

### Resources

- [TravelPerk SCIM API Documentation](https://developers.travelperk.com/reference/scim-api)
- [SCIM 2.0 Specification (RFC 7644)](https://datatracker.ietf.org/doc/html/rfc7644)
- [UKG Pro API Documentation](https://developer.ukg.com/)

### Escalation Path

1. Check troubleshooting section
2. Review logs with correlation ID
3. Contact integration team
4. Escalate to TravelPerk support if needed
