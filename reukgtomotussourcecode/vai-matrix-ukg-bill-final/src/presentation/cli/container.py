"""
Dependency injection container for CLI commands.

Provides factory methods to create properly configured service instances
with all their dependencies wired up.
"""

import logging
import time
import threading
from typing import Any, Callable, Dict, Optional

from src.infrastructure.config.settings import Settings, get_settings


logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, calls_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            calls_per_minute: Maximum calls allowed per minute.
        """
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire permission to make a call, blocking if necessary."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()


class Container:
    """
    Dependency injection container.

    Manages creation and lifecycle of service instances.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize container.

        Args:
            settings: Application settings. Uses default if not provided.
        """
        self.settings = settings or get_settings()
        self._instances: Dict[str, Any] = {}

    def _get_or_create(self, key: str, factory: Callable) -> Any:
        """Get cached instance or create new one."""
        if key not in self._instances:
            self._instances[key] = factory()
        return self._instances[key]

    # Rate Limiter

    def rate_limiter(self) -> SimpleRateLimiter:
        """Get rate limiter."""
        def factory():
            return SimpleRateLimiter(
                calls_per_minute=getattr(self.settings, 'rate_limit_calls_per_minute', 60)
            )
        return self._get_or_create("rate_limiter", factory)

    # UKG Components

    def ukg_client(self):
        """Get UKG API client."""
        def factory():
            from src.infrastructure.adapters.ukg.client import UKGClient
            return UKGClient(
                base_url=self.settings.ukg_api_base,
                username=self.settings.ukg_username,
                password=self.settings.ukg_password,
                api_key=self.settings.ukg_api_key,
            )
        return self._get_or_create("ukg_client", factory)

    def employee_repository(self):
        """Get UKG employee repository."""
        def factory():
            from src.infrastructure.adapters.ukg.repository import UKGEmployeeRepository
            return UKGEmployeeRepository(client=self.ukg_client())
        return self._get_or_create("employee_repository", factory)

    # BILL Components

    def bill_client(self):
        """Get BILL.com base client."""
        def factory():
            from src.infrastructure.adapters.bill.client import BillClient
            return BillClient(
                base_url=self.settings.bill_api_base,
                api_token=self.settings.bill_api_token,
                org_id=self.settings.bill_org_id,
            )
        return self._get_or_create("bill_client", factory)

    def spend_expense_client(self):
        """Get BILL.com Spend & Expense client."""
        def factory():
            from src.infrastructure.adapters.bill.spend_expense import SpendExpenseClient
            return SpendExpenseClient(
                base_url=self.settings.bill_api_base,
                api_token=self.settings.bill_api_token,
                org_id=self.settings.bill_org_id,
            )
        return self._get_or_create("spend_expense_client", factory)

    def accounts_payable_client(self):
        """Get BILL.com Accounts Payable client."""
        def factory():
            from src.infrastructure.adapters.bill.accounts_payable import AccountsPayableClient
            return AccountsPayableClient(
                base_url=self.settings.bill_api_base,
                api_token=self.settings.bill_api_token,
                org_id=self.settings.bill_org_id,
            )
        return self._get_or_create("accounts_payable_client", factory)

    # Application Services

    def sync_service(self):
        """Get employee sync service."""
        def factory():
            from src.application.services.sync_service import SyncService
            return SyncService(
                employee_repository=self.employee_repository(),
                bill_user_repository=self.spend_expense_client(),
                rate_limiter=self.rate_limiter().acquire,
            )
        return self._get_or_create("sync_service", factory)

    def vendor_service(self):
        """Get vendor service."""
        def factory():
            from src.application.services.vendor_service import VendorService
            return VendorService(
                vendor_repository=self.accounts_payable_client(),
                rate_limiter=self.rate_limiter().acquire,
            )
        return self._get_or_create("vendor_service", factory)

    def invoice_service(self):
        """Get invoice service."""
        def factory():
            from src.application.services.invoice_service import InvoiceService
            return InvoiceService(
                invoice_repository=self.accounts_payable_client(),
                vendor_repository=self.accounts_payable_client(),
                rate_limiter=self.rate_limiter().acquire,
            )
        return self._get_or_create("invoice_service", factory)

    def payment_service(self):
        """Get payment service."""
        def factory():
            from src.application.services.payment_service import PaymentService
            return PaymentService(
                payment_repository=self.accounts_payable_client(),
                invoice_repository=self.accounts_payable_client(),
                rate_limiter=self.rate_limiter().acquire,
                default_funding_account_id=getattr(
                    self.settings, 'bill_default_funding_account', None
                ),
            )
        return self._get_or_create("payment_service", factory)

    def clear(self) -> None:
        """Clear all cached instances."""
        self._instances.clear()


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get or create the global container instance."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    if _container:
        _container.clear()
    _container = None
