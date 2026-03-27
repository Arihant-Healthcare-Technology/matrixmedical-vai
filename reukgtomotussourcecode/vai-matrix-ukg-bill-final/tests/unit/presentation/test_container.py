"""
Unit tests for dependency injection container.
"""
import pytest
import time
from unittest.mock import MagicMock, patch


class TestSimpleRateLimiter:
    """Tests for SimpleRateLimiter class."""

    def test_init_with_default_calls_per_minute(self):
        """Test initializes with default calls per minute."""
        from src.presentation.cli.container import SimpleRateLimiter

        limiter = SimpleRateLimiter()

        assert limiter.calls_per_minute == 60
        assert limiter.interval == 1.0  # 60/60 = 1 second

    def test_init_with_custom_calls_per_minute(self):
        """Test initializes with custom calls per minute."""
        from src.presentation.cli.container import SimpleRateLimiter

        limiter = SimpleRateLimiter(calls_per_minute=120)

        assert limiter.calls_per_minute == 120
        assert limiter.interval == 0.5  # 60/120 = 0.5 seconds

    def test_acquire_first_call_no_wait(self):
        """Test first acquire call doesn't wait."""
        from src.presentation.cli.container import SimpleRateLimiter

        limiter = SimpleRateLimiter(calls_per_minute=60)

        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        # First call should be nearly instant
        assert elapsed < 0.1

    def test_acquire_respects_rate_limit(self):
        """Test acquire respects rate limit."""
        from src.presentation.cli.container import SimpleRateLimiter

        # 600 calls per minute = 0.1 seconds between calls
        limiter = SimpleRateLimiter(calls_per_minute=600)

        limiter.acquire()
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        # Should wait approximately 0.1 seconds
        assert elapsed >= 0.09


class TestContainer:
    """Tests for Container class."""

    def test_init_with_default_settings(self):
        """Test initializes with default settings."""
        from src.presentation.cli.container import Container

        with patch("src.presentation.cli.container.get_settings") as mock_get:
            mock_settings = MagicMock()
            mock_get.return_value = mock_settings

            container = Container()

            assert container.settings == mock_settings

    def test_init_with_custom_settings(self):
        """Test initializes with custom settings."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        container = Container(settings=mock_settings)

        assert container.settings == mock_settings

    def test_get_or_create_creates_instance(self):
        """Test _get_or_create creates new instance."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        container = Container(settings=mock_settings)

        factory = MagicMock(return_value="created_instance")
        result = container._get_or_create("test_key", factory)

        assert result == "created_instance"
        factory.assert_called_once()

    def test_get_or_create_caches_instance(self):
        """Test _get_or_create caches instance."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        container = Container(settings=mock_settings)

        factory = MagicMock(return_value="created_instance")

        # First call creates
        result1 = container._get_or_create("test_key", factory)
        # Second call returns cached
        result2 = container._get_or_create("test_key", factory)

        assert result1 == result2
        factory.assert_called_once()  # Only called once

    def test_rate_limiter_creates_instance(self):
        """Test rate_limiter creates SimpleRateLimiter."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.rate_limit_calls_per_minute = 100
        container = Container(settings=mock_settings)

        limiter = container.rate_limiter()

        assert limiter.calls_per_minute == 100

    def test_rate_limiter_default_calls_per_minute(self):
        """Test rate_limiter uses default when setting not present."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock(spec=[])  # No rate_limit attribute
        container = Container(settings=mock_settings)

        limiter = container.rate_limiter()

        assert limiter.calls_per_minute == 60

    def test_ukg_client_creates_instance(self):
        """Test ukg_client creates UKGClient."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.ukg_api_base = "https://ukg.example.com"
        mock_settings.ukg_username = "user"
        mock_settings.ukg_password = "pass"
        mock_settings.ukg_api_key = "key123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.ukg.client.UKGClient") as MockClient:
            client = container.ukg_client()

            MockClient.assert_called_once_with(
                base_url="https://ukg.example.com",
                username="user",
                password="pass",
                api_key="key123",
            )

    def test_employee_repository_creates_instance(self):
        """Test employee_repository creates UKGEmployeeRepository."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.ukg_api_base = "https://ukg.example.com"
        mock_settings.ukg_username = "user"
        mock_settings.ukg_password = "pass"
        mock_settings.ukg_api_key = "key123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.ukg.client.UKGClient"):
            with patch("src.infrastructure.adapters.ukg.repository.UKGEmployeeRepository") as MockRepo:
                repo = container.employee_repository()

                MockRepo.assert_called_once()

    def test_bill_client_creates_instance(self):
        """Test bill_client creates BillClient."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.client.BillClient") as MockClient:
            client = container.bill_client()

            MockClient.assert_called_once_with(
                base_url="https://bill.example.com",
                api_token="token123",
                org_id="org123",
            )

    def test_spend_expense_client_creates_instance(self):
        """Test spend_expense_client creates SpendExpenseClient."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.spend_expense.SpendExpenseClient") as MockClient:
            client = container.spend_expense_client()

            MockClient.assert_called_once_with(
                base_url="https://bill.example.com",
                api_token="token123",
                org_id="org123",
            )

    def test_accounts_payable_client_creates_instance(self):
        """Test accounts_payable_client creates AccountsPayableClient."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.accounts_payable.AccountsPayableClient") as MockClient:
            client = container.accounts_payable_client()

            MockClient.assert_called_once_with(
                base_url="https://bill.example.com",
                api_token="token123",
                org_id="org123",
            )

    def test_sync_service_creates_instance(self):
        """Test sync_service creates SyncService."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.ukg_api_base = "https://ukg.example.com"
        mock_settings.ukg_username = "user"
        mock_settings.ukg_password = "pass"
        mock_settings.ukg_api_key = "key123"
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        mock_settings.rate_limit_calls_per_minute = 60
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.ukg.client.UKGClient"), \
             patch("src.infrastructure.adapters.ukg.repository.UKGEmployeeRepository"), \
             patch("src.infrastructure.adapters.bill.spend_expense.SpendExpenseClient"), \
             patch("src.application.services.sync_service.SyncService") as MockService:
            service = container.sync_service()

            MockService.assert_called_once()

    def test_vendor_service_creates_instance(self):
        """Test vendor_service creates VendorService."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        mock_settings.rate_limit_calls_per_minute = 60
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.accounts_payable.AccountsPayableClient"), \
             patch("src.application.services.vendor_service.VendorService") as MockService:
            service = container.vendor_service()

            MockService.assert_called_once()

    def test_invoice_service_creates_instance(self):
        """Test invoice_service creates InvoiceService."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        mock_settings.rate_limit_calls_per_minute = 60
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.accounts_payable.AccountsPayableClient"), \
             patch("src.application.services.invoice_service.InvoiceService") as MockService:
            service = container.invoice_service()

            MockService.assert_called_once()

    def test_payment_service_creates_instance(self):
        """Test payment_service creates PaymentService."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.bill_api_base = "https://bill.example.com"
        mock_settings.bill_api_token = "token123"
        mock_settings.bill_org_id = "org123"
        mock_settings.rate_limit_calls_per_minute = 60
        mock_settings.bill_default_funding_account = "acc123"
        container = Container(settings=mock_settings)

        with patch("src.infrastructure.adapters.bill.accounts_payable.AccountsPayableClient"), \
             patch("src.application.services.payment_service.PaymentService") as MockService:
            service = container.payment_service()

            MockService.assert_called_once()

    def test_clear_removes_cached_instances(self):
        """Test clear removes all cached instances."""
        from src.presentation.cli.container import Container

        mock_settings = MagicMock()
        mock_settings.rate_limit_calls_per_minute = 60
        container = Container(settings=mock_settings)

        # Create some instances
        container.rate_limiter()
        assert len(container._instances) > 0

        # Clear
        container.clear()

        assert len(container._instances) == 0


class TestGlobalContainerFunctions:
    """Tests for global container functions."""

    def test_get_container_creates_instance(self):
        """Test get_container creates new instance."""
        from src.presentation.cli.container import get_container, reset_container

        reset_container()  # Ensure clean state

        with patch("src.presentation.cli.container.Container") as MockContainer:
            container = get_container()

            MockContainer.assert_called_once()

    def test_get_container_returns_same_instance(self):
        """Test get_container returns same instance."""
        from src.presentation.cli.container import get_container, reset_container

        reset_container()  # Ensure clean state

        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_reset_container_clears_global(self):
        """Test reset_container clears global instance."""
        from src.presentation.cli.container import get_container, reset_container, _container

        # Create a container
        get_container()

        # Reset
        reset_container()

        # Get container - should create new one
        with patch("src.presentation.cli.container.Container") as MockContainer:
            get_container()
            MockContainer.assert_called_once()

    def test_reset_container_handles_none(self):
        """Test reset_container handles None state."""
        from src.presentation.cli.container import reset_container

        # Reset twice - should not crash
        reset_container()
        reset_container()
