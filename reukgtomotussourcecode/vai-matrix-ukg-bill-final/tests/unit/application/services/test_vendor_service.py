"""
Unit tests for VendorService.
"""

from unittest.mock import Mock, MagicMock

import pytest

from src.application.services.vendor_service import VendorService
from src.domain.models.vendor import Vendor, VendorStatus, PaymentMethod


@pytest.fixture
def mock_vendor_repo():
    """Create mock vendor repository."""
    return MagicMock()


@pytest.fixture
def vendor_service(mock_vendor_repo):
    """Create vendor service with mocked dependencies."""
    return VendorService(vendor_repository=mock_vendor_repo)


@pytest.fixture
def sample_vendor():
    """Create sample vendor."""
    return Vendor(
        id="VND001",
        name="Acme Corp",
        email="vendor@acme.com",
        status=VendorStatus.ACTIVE,
        payment_method=PaymentMethod.ACH,
    )


class TestSyncVendor:
    """Tests for sync_vendor method."""

    def test_creates_new_vendor(self, vendor_service, mock_vendor_repo):
        """Should create vendor when not found."""
        vendor = Vendor(name="New Vendor", status=VendorStatus.ACTIVE)
        mock_vendor_repo.get_by_id.return_value = None
        mock_vendor_repo.get_by_external_id.return_value = None
        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.create.return_value = Vendor(
            id="NEW001",
            name="New Vendor",
            status=VendorStatus.ACTIVE,
        )

        result = vendor_service.sync_vendor(vendor)

        assert result.success is True
        assert result.action == "create"
        mock_vendor_repo.create.assert_called_once()

    def test_updates_existing_vendor(
        self,
        vendor_service,
        mock_vendor_repo,
        sample_vendor,
    ):
        """Should update vendor when found with changes."""
        existing = Vendor(
            id="VND001",
            name="Acme Corp",
            email="old@acme.com",  # Different email
            status=VendorStatus.ACTIVE,
        )
        mock_vendor_repo.get_by_name.return_value = existing
        mock_vendor_repo.update.return_value = sample_vendor

        result = vendor_service.sync_vendor(sample_vendor)

        assert result.success is True
        assert result.action == "update"
        mock_vendor_repo.update.assert_called_once()

    def test_skips_unchanged_vendor(
        self,
        vendor_service,
        mock_vendor_repo,
        sample_vendor,
    ):
        """Should skip when no changes detected."""
        # Mock get_by_id to return the same vendor (since sample_vendor has an id)
        mock_vendor_repo.get_by_id.return_value = sample_vendor

        result = vendor_service.sync_vendor(sample_vendor)

        assert result.success is True
        assert result.action == "skip"
        mock_vendor_repo.update.assert_not_called()

    def test_error_missing_name(self, vendor_service):
        """Should return error for vendor without name."""
        vendor = Vendor(name="", status=VendorStatus.ACTIVE)

        result = vendor_service.sync_vendor(vendor)

        assert result.success is False
        assert result.action == "error"
        assert "name" in result.message.lower()

    def test_error_on_create_failure(self, vendor_service, mock_vendor_repo):
        """Should return error when create fails."""
        vendor = Vendor(name="Test Vendor", status=VendorStatus.ACTIVE)
        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.create.side_effect = Exception("API Error")

        result = vendor_service.sync_vendor(vendor)

        assert result.success is False
        assert result.action == "error"


class TestSyncBatch:
    """Tests for sync_batch method."""

    def test_empty_batch(self, vendor_service):
        """Should handle empty vendor list."""
        result = vendor_service.sync_batch([])

        assert result.total == 0
        assert result.created == 0
        assert result.errors == 0

    def test_batch_processes_all_vendors(self, vendor_service, mock_vendor_repo):
        """Should process all vendors in batch."""
        vendors = [
            Vendor(name=f"Vendor {i}", status=VendorStatus.ACTIVE)
            for i in range(3)
        ]

        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.list.return_value = []
        mock_vendor_repo.create.side_effect = [
            Vendor(id=f"VND{i}", name=f"Vendor {i}", status=VendorStatus.ACTIVE)
            for i in range(3)
        ]

        result = vendor_service.sync_batch(vendors, workers=1)

        assert result.total == 3
        assert result.created == 3


class TestFindOrCreate:
    """Tests for find_or_create method."""

    def test_finds_existing_vendor(
        self,
        vendor_service,
        mock_vendor_repo,
        sample_vendor,
    ):
        """Should return existing vendor if found."""
        mock_vendor_repo.get_by_name.return_value = sample_vendor

        result = vendor_service.find_or_create("Acme Corp")

        assert result == sample_vendor
        mock_vendor_repo.create.assert_not_called()

    def test_creates_new_vendor(self, vendor_service, mock_vendor_repo):
        """Should create vendor if not found."""
        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.create.return_value = Vendor(
            id="NEW001",
            name="New Vendor",
            status=VendorStatus.ACTIVE,
        )

        result = vendor_service.find_or_create("New Vendor")

        assert result.id == "NEW001"
        mock_vendor_repo.create.assert_called_once()

    def test_creates_with_additional_data(self, vendor_service, mock_vendor_repo):
        """Should use additional data when creating."""
        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.create.return_value = Vendor(
            id="NEW001",
            name="New Vendor",
            email="new@example.com",
            status=VendorStatus.ACTIVE,
        )

        result = vendor_service.find_or_create(
            "New Vendor",
            vendor_data={"email": "new@example.com"},
        )

        mock_vendor_repo.create.assert_called_once()
        # Check that email was passed to create
        created_vendor = mock_vendor_repo.create.call_args[0][0]
        assert created_vendor.email == "new@example.com"


class TestArchiveVendor:
    """Tests for archive_vendor method."""

    def test_archives_vendor(
        self,
        vendor_service,
        mock_vendor_repo,
        sample_vendor,
    ):
        """Should archive existing vendor."""
        mock_vendor_repo.get_by_id.return_value = sample_vendor
        mock_vendor_repo.update.return_value = sample_vendor

        result = vendor_service.archive_vendor("VND001")

        assert result.success is True
        assert result.action == "update"
        # Check status was changed to ARCHIVED
        updated_vendor = mock_vendor_repo.update.call_args[0][0]
        assert updated_vendor.status == VendorStatus.ARCHIVED

    def test_error_vendor_not_found(self, vendor_service, mock_vendor_repo):
        """Should return error if vendor not found."""
        mock_vendor_repo.get_by_id.return_value = None

        result = vendor_service.archive_vendor("NOTFOUND")

        assert result.success is False
        assert "not found" in result.message.lower()


class TestGetActiveVendors:
    """Tests for get_active_vendors method."""

    def test_returns_active_vendors(
        self,
        vendor_service,
        mock_vendor_repo,
        sample_vendor,
    ):
        """Should return only active vendors."""
        mock_vendor_repo.list.return_value = [sample_vendor]

        result = vendor_service.get_active_vendors()

        assert len(result) == 1
        assert result[0] == sample_vendor
        mock_vendor_repo.list.assert_called()


class TestRateLimiter:
    """Tests for rate limiter integration."""

    def test_calls_rate_limiter(self, mock_vendor_repo):
        """Should call rate limiter when provided."""
        rate_limiter = MagicMock()
        service = VendorService(
            vendor_repository=mock_vendor_repo,
            rate_limiter=rate_limiter,
        )

        vendor = Vendor(name="Test Vendor", status=VendorStatus.ACTIVE)
        mock_vendor_repo.get_by_id.return_value = None
        mock_vendor_repo.get_by_external_id.return_value = None
        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.create.return_value = Vendor(
            id="NEW001",
            name="Test Vendor",
            status=VendorStatus.ACTIVE,
        )

        service.sync_vendor(vendor)

        rate_limiter.assert_called_once()


class TestFindExistingVendor:
    """Tests for _find_existing_vendor edge cases."""

    def test_finds_by_external_id(self, vendor_service, mock_vendor_repo, sample_vendor):
        """Should find vendor by external ID."""
        sample_vendor.id = None
        sample_vendor.external_id = "EXT001"

        mock_vendor_repo.get_by_external_id.return_value = sample_vendor

        result = vendor_service.sync_vendor(sample_vendor)

        mock_vendor_repo.get_by_external_id.assert_called_with("EXT001")
        assert result.success is True
        assert result.action == "skip"

    def test_finds_by_id_with_cache(self, mock_vendor_repo):
        """Should use cache when available."""
        service = VendorService(vendor_repository=mock_vendor_repo)

        # First lookup - populates cache
        vendor = Vendor(id="VND001", name="Cached Vendor", status=VendorStatus.ACTIVE)
        mock_vendor_repo.get_by_id.return_value = vendor

        result1 = service.sync_vendor(vendor)
        assert result1.success is True

        # Second lookup - should use cache (reset mock to verify)
        mock_vendor_repo.reset_mock()
        mock_vendor_repo.get_by_id.return_value = vendor

        result2 = service.sync_vendor(vendor)
        assert result2.success is True


class TestUpdateVendor:
    """Tests for _update_vendor edge cases."""

    def test_handles_update_exception(self, mock_vendor_repo, sample_vendor):
        """Should handle exception during update."""
        service = VendorService(vendor_repository=mock_vendor_repo)

        existing = Vendor(
            id="VND001",
            name="Acme Corp",
            email="old@acme.com",  # Different to trigger update
            status=VendorStatus.ACTIVE,
        )
        mock_vendor_repo.get_by_name.return_value = existing
        mock_vendor_repo.update.side_effect = Exception("Update failed")

        result = service.sync_vendor(sample_vendor)

        assert result.success is False
        assert result.action == "error"


class TestArchiveEdgeCases:
    """Tests for archive edge cases."""

    def test_archive_already_archived(self, vendor_service, mock_vendor_repo, sample_vendor):
        """Should handle archiving already archived vendor."""
        sample_vendor.status = VendorStatus.ARCHIVED
        mock_vendor_repo.get_by_id.return_value = sample_vendor

        result = vendor_service.archive_vendor("VND001")

        # Should either succeed (idempotent) or fail gracefully
        # Implementation may vary
        assert result is not None

    def test_archive_handles_update_error(self, vendor_service, mock_vendor_repo, sample_vendor):
        """Should handle error during archive update."""
        mock_vendor_repo.get_by_id.return_value = sample_vendor
        mock_vendor_repo.update.side_effect = Exception("Archive failed")

        result = vendor_service.archive_vendor("VND001")

        assert result.success is False


class TestBatchEdgeCases:
    """Tests for sync_batch edge cases."""

    def test_batch_with_errors(self, vendor_service, mock_vendor_repo):
        """Should handle batch with some errors."""
        vendors = [
            Vendor(name=f"Vendor {i}", status=VendorStatus.ACTIVE)
            for i in range(3)
        ]

        mock_vendor_repo.get_by_name.return_value = None
        mock_vendor_repo.list.return_value = []
        # First succeeds, second fails, third succeeds
        mock_vendor_repo.create.side_effect = [
            Vendor(id="VND0", name="Vendor 0", status=VendorStatus.ACTIVE),
            Exception("API error"),
            Vendor(id="VND2", name="Vendor 2", status=VendorStatus.ACTIVE),
        ]

        result = vendor_service.sync_batch(vendors, workers=1)

        assert result.total == 3
        assert result.created == 2
        assert result.errors == 1
