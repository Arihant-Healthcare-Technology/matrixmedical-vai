# Architecture Documentation

## Overview

This document describes the architecture of the UKG to BILL.com integration system. The codebase follows **Clean Architecture** (also known as Hexagonal Architecture or Ports and Adapters) to achieve:

- **Separation of Concerns**: Business logic is isolated from external dependencies
- **Testability**: Domain and application layers can be tested without external services
- **Flexibility**: External adapters can be swapped without changing core logic
- **Maintainability**: Clear boundaries make code easier to understand and modify

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                           │
│                    (CLI, API, UI)                               │
├─────────────────────────────────────────────────────────────────┤
│                    Application Layer                            │
│                    (Use Cases, Services)                        │
├─────────────────────────────────────────────────────────────────┤
│                    Domain Layer                                 │
│                    (Entities, Interfaces)                       │
├─────────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                         │
│                    (Adapters, External Systems)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency Rule

Dependencies point inward:
- **Presentation** → Application → Domain
- **Infrastructure** → Domain (implements interfaces)

The Domain layer has no dependencies on outer layers.

## Layer Details

### 1. Domain Layer (`src/domain/`)

The innermost layer containing business entities and rules.

#### Models (`src/domain/models/`)

| Model | Purpose |
|-------|---------|
| `Employee` | UKG employee data with validation |
| `BillUser` | BILL.com S&E user entity |
| `Vendor` | AP vendor/supplier entity |
| `Invoice` | AP bill/invoice entity |
| `Payment` | AP payment entity |

#### Interfaces (`src/domain/interfaces/`)

Abstract repository and service interfaces that define contracts for external interactions:

```python
# Example: Repository interface
class EmployeeRepository(ABC):
    @abstractmethod
    def get_active_employees(self, company_id: str) -> List[Employee]:
        pass
```

#### Exceptions (`src/domain/exceptions/`)

Domain-specific exceptions:
- `IntegrationError`: Base exception for all integration errors
- `ValidationError`: Data validation failures
- `RateLimitError`: API rate limit exceeded
- `AuthenticationError`: Authentication failures

### 2. Application Layer (`src/application/`)

Contains business use cases and orchestration logic.

#### Services (`src/application/services/`)

| Service | Purpose |
|---------|---------|
| `SyncService` | Orchestrates employee → BILL user synchronization |
| `VendorService` | Manages vendor CRUD operations |
| `InvoiceService` | Manages invoice/bill operations |
| `PaymentService` | Processes payments |

Services implement business logic by:
1. Receiving domain objects
2. Applying business rules
3. Coordinating with repositories
4. Returning results

```python
class SyncService:
    def __init__(
        self,
        employee_repository: EmployeeRepository,
        bill_user_repository: BillUserRepository,
        rate_limiter: Callable,
    ):
        ...

    def sync_employees(self, employees: List[Employee]) -> BatchResult:
        """Sync employees to BILL.com users."""
        ...
```

### 3. Infrastructure Layer (`src/infrastructure/`)

Implements interfaces and provides external integrations.

#### Configuration (`src/infrastructure/config/`)

- `settings.py`: Pydantic-based settings management
- `constants.py`: Application constants (rate limits, timeouts)
- `selectors.py`: UI selectors for browser automation

#### HTTP Utilities (`src/infrastructure/http/`)

- `client.py`: Base HTTP client with retry logic
- `retry.py`: Configurable retry strategies
- `response.py`: Response handling utilities

#### Adapters (`src/infrastructure/adapters/`)

##### UKG Adapter (`adapters/ukg/`)
- `client.py`: UKG Pro API client
- `repository.py`: Implements `EmployeeRepository`
- `mappers.py`: UKG data transformations

##### BILL Adapters (`adapters/bill/`)
- `client.py`: Base BILL API client
- `spend_expense.py`: S&E API implementation
- `accounts_payable.py`: AP API implementation
- `mappers.py`: BILL data transformations

##### Scraping Adapter (`adapters/scraping/`)
Page Object Model for browser automation:
- `base_page.py`: Common page interactions
- `login_page.py`: Login automation
- `company_page.py`: Company selection
- `import_page.py`: CSV import automation

### 4. Presentation Layer (`src/presentation/`)

User interface components.

#### CLI (`src/presentation/cli/`)

- `main.py`: Entry point with argparse configuration
- `container.py`: Dependency injection container
- `batch_commands.py`: S&E sync commands
- `ap_commands.py`: AP operation commands

## Key Design Patterns

### 1. Dependency Injection

Services receive their dependencies through constructor injection:

```python
class Container:
    def sync_service(self) -> SyncService:
        return SyncService(
            employee_repository=self.employee_repository(),
            bill_user_repository=self.bill_user_repository(),
            rate_limiter=self.rate_limiter().acquire,
        )
```

### 2. Repository Pattern

Data access is abstracted behind repository interfaces:

```python
# Interface (Domain layer)
class VendorRepository(ABC):
    @abstractmethod
    def create(self, vendor: Vendor) -> Vendor: pass
    @abstractmethod
    def update(self, vendor: Vendor) -> Vendor: pass
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Vendor]: pass

# Implementation (Infrastructure layer)
class BillVendorRepository(VendorRepository):
    def __init__(self, client: BillClient):
        self.client = client

    def create(self, vendor: Vendor) -> Vendor:
        payload = VendorMapper.to_api_payload(vendor)
        response = self.client.post("/vendors", payload)
        return VendorMapper.from_api_response(response)
```

### 3. Strategy Pattern (Rate Limiting)

Rate limiting is injected as a callable:

```python
class SyncService:
    def __init__(self, rate_limiter: Callable):
        self._rate_limit = rate_limiter

    def _process_one(self, employee: Employee):
        self._rate_limit()  # Wait if necessary
        # Proceed with API call
```

### 4. Page Object Model

Browser automation uses POM for maintainability:

```python
class LoginPage(BasePage):
    def login(self, email: str, password: str) -> "CompanyPage":
        self.fill(self.selectors.email_input, email)
        self.fill(self.selectors.password_input, password)
        self.click(self.selectors.submit_button)
        return CompanyPage(self.page)
```

## Data Flow

### S&E Sync Flow

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐
│   CLI   │───▶│ SyncService │───▶│ EmployeeRepo │───▶│  UKG API   │
└─────────┘    └─────────────┘    └─────────────┘    └────────────┘
                     │
                     │  ┌──────────────┐    ┌────────────┐
                     └─▶│ BillUserRepo │───▶│ BILL S&E   │
                        └──────────────┘    └────────────┘
```

### AP Payment Flow

```
┌─────────┐    ┌────────────────┐    ┌─────────────┐
│   CLI   │───▶│ PaymentService │───▶│ InvoiceRepo │
└─────────┘    └────────────────┘    └─────────────┘
                     │
                     │  ┌─────────────┐    ┌────────────┐
                     └─▶│ PaymentRepo │───▶│ BILL AP    │
                        └─────────────┘    └────────────┘
```

## Error Handling

### Exception Hierarchy

```
IntegrationError (base)
├── ConfigurationError
├── ValidationError
├── ApiError
│   ├── AuthenticationError
│   ├── RateLimitError
│   └── ResourceNotFoundError
└── ScrapingError
```

### Error Handling Strategy

1. **Domain Layer**: Raises domain exceptions
2. **Application Layer**: Catches and wraps with context
3. **Infrastructure Layer**: Converts external errors
4. **Presentation Layer**: Formats for user display

## Testing Strategy

### Unit Tests (`tests/unit/`)

- Test domain models in isolation
- Test services with mocked repositories
- Test mappers with sample data

### Integration Tests (`tests/integration/`)

- Test CLI command parsing
- Test data loading functions
- Test with mocked HTTP responses

### End-to-End Tests

- Run against staging APIs
- Verify full workflow completion
- Use dry-run mode for safety

## Configuration Management

### Environment Variables

Configuration is loaded via Pydantic Settings:

```python
class Settings(BaseSettings):
    ukg_api_base: str
    ukg_username: str
    bill_api_base: str
    bill_api_token: SecretStr

    class Config:
        env_file = ".env"
        env_prefix = ""
```

### Secrets Handling

- Sensitive values use `SecretStr` type
- Never logged or printed
- Loaded from environment or secrets manager

## Scalability Considerations

### Rate Limiting

Token bucket algorithm with configurable limits:

```python
class SimpleRateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.interval = 60.0 / calls_per_minute
```

### Concurrent Processing

Services support concurrent workers:

```python
def sync_batch(self, employees: List[Employee], workers: int = 12):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(self._sync_one, emp) for emp in employees]
```

### Retry Strategy

Configurable retry with exponential backoff:

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
```

## Future Considerations

1. **Async/Await**: Convert to async for better concurrency
2. **Event Sourcing**: Track all changes for audit
3. **Webhooks**: Real-time updates from BILL.com
4. **Caching**: Redis for frequently accessed data
5. **Monitoring**: Prometheus metrics, distributed tracing
