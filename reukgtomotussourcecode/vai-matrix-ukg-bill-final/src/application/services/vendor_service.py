"""
Vendor service - Orchestrates vendor management in BILL.com AP.

This service coordinates:
- Vendor creation and updates
- Vendor lookup and deduplication
- Batch vendor operations
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from src.domain.interfaces.services import (
    VendorSyncService,
    SyncResult,
    BatchSyncResult,
)
from src.domain.interfaces.repositories import VendorRepository
from src.domain.models.vendor import Vendor, VendorStatus


logger = logging.getLogger(__name__)


class VendorService(VendorSyncService):
    """
    Implementation of vendor sync service.

    Manages vendor operations in BILL.com Accounts Payable.
    """

    def __init__(
        self,
        vendor_repository: VendorRepository,
        rate_limiter: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize vendor service.

        Args:
            vendor_repository: Repository for vendor data.
            rate_limiter: Optional rate limiter callable.
        """
        self.vendor_repo = vendor_repository
        self.rate_limiter = rate_limiter
        self._vendor_cache: Dict[str, Vendor] = {}

    def sync_vendor(self, vendor: Vendor) -> SyncResult:
        """
        Sync a vendor to BILL.com.

        Args:
            vendor: Vendor to sync.

        Returns:
            SyncResult with operation details.
        """
        if self.rate_limiter:
            self.rate_limiter()

        try:
            # Validate vendor has required data
            if not vendor.name:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=vendor.id,
                    message="Vendor missing name",
                )

            # Check if vendor already exists
            existing = self._find_existing_vendor(vendor)

            if existing:
                return self._update_vendor(existing, vendor)
            else:
                return self._create_vendor(vendor)

        except Exception as e:
            logger.error(f"Error syncing vendor {vendor.name}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=vendor.id,
                message=str(e),
                details={"vendor_name": vendor.name},
            )

    def _find_existing_vendor(self, vendor: Vendor) -> Optional[Vendor]:
        """Find existing vendor by ID, external ID, or name."""
        # Try by BILL vendor ID first
        if vendor.id:
            cached = self._vendor_cache.get(vendor.id)
            if cached:
                return cached

            existing = self.vendor_repo.get_by_id(vendor.id)
            if existing:
                self._vendor_cache[vendor.id] = existing
                return existing

        # Try by external ID
        if vendor.external_id:
            existing = self.vendor_repo.get_by_external_id(vendor.external_id)
            if existing:
                self._vendor_cache[existing.id] = existing
                return existing

        # Try by name (case-insensitive)
        existing = self.vendor_repo.get_by_name(vendor.name)
        if existing:
            self._vendor_cache[existing.id] = existing
            return existing

        return None

    def _create_vendor(self, vendor: Vendor) -> SyncResult:
        """Create a new vendor in BILL.com."""
        try:
            created = self.vendor_repo.create(vendor)
            self._vendor_cache[created.id] = created

            logger.info(f"Created vendor: {created.name} (ID: {created.id})")
            return SyncResult(
                success=True,
                action="create",
                entity_id=created.id,
                message=f"Created vendor {created.name}",
                details={
                    "vendor_name": created.name,
                    "external_id": created.external_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to create vendor {vendor.name}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=vendor.id,
                message=f"Failed to create vendor: {e}",
                details={"vendor_name": vendor.name},
            )

    def _update_vendor(self, existing: Vendor, updated: Vendor) -> SyncResult:
        """Update an existing vendor."""
        try:
            # Check if update is needed
            if self._vendors_match(existing, updated):
                logger.debug(f"Vendor {existing.name} unchanged, skipping")
                return SyncResult(
                    success=True,
                    action="skip",
                    entity_id=existing.id,
                    message="No changes detected",
                    details={"vendor_name": existing.name},
                )

            # Preserve existing ID
            updated.id = existing.id

            result = self.vendor_repo.update(updated)
            self._vendor_cache[result.id] = result

            logger.info(f"Updated vendor: {result.name}")
            return SyncResult(
                success=True,
                action="update",
                entity_id=result.id,
                message=f"Updated vendor {result.name}",
                details={
                    "vendor_name": result.name,
                    "changes": self._get_changes(existing, updated),
                },
            )
        except Exception as e:
            logger.error(f"Failed to update vendor {existing.name}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=existing.id,
                message=f"Failed to update vendor: {e}",
                details={"vendor_name": existing.name},
            )

    def _vendors_match(self, existing: Vendor, updated: Vendor) -> bool:
        """Check if two vendors have matching data."""
        return (
            existing.name == updated.name
            and existing.email == updated.email
            and existing.status == updated.status
            and existing.payment_method == updated.payment_method
        )

    def _get_changes(self, existing: Vendor, updated: Vendor) -> Dict[str, Any]:
        """Get dictionary of changed fields."""
        changes = {}
        if existing.name != updated.name:
            changes["name"] = {"old": existing.name, "new": updated.name}
        if existing.email != updated.email:
            changes["email"] = {"old": existing.email, "new": updated.email}
        if existing.status != updated.status:
            changes["status"] = {
                "old": existing.status.value if existing.status else None,
                "new": updated.status.value if updated.status else None,
            }
        return changes

    def sync_batch(
        self,
        vendors: List[Vendor],
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync multiple vendors to BILL.com.

        Args:
            vendors: List of vendors to sync.
            workers: Number of concurrent workers.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"Starting batch vendor sync of {len(vendors)} vendors "
            f"[correlation_id={correlation_id}]"
        )

        result = BatchSyncResult(
            total=len(vendors),
            correlation_id=correlation_id,
            start_time=datetime.now(),
        )

        if not vendors:
            result.end_time = datetime.now()
            return result

        # Pre-populate cache with existing vendors to reduce API calls
        self._populate_vendor_cache()

        # Process in parallel
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.sync_vendor, vendor): vendor
                for vendor in vendors
            }

            for future in as_completed(futures):
                vendor = futures[future]
                try:
                    sync_result = future.result()
                    result.results.append(sync_result)

                    if sync_result.action == "create":
                        result.created += 1
                    elif sync_result.action == "update":
                        result.updated += 1
                    elif sync_result.action == "skip":
                        result.skipped += 1
                    elif sync_result.action == "error":
                        result.errors += 1

                except Exception as e:
                    logger.error(f"Unexpected error syncing vendor {vendor.name}: {e}")
                    result.errors += 1
                    result.results.append(
                        SyncResult(
                            success=False,
                            action="error",
                            entity_id=vendor.id,
                            message=str(e),
                        )
                    )

        result.end_time = datetime.now()

        logger.info(
            f"Vendor batch sync complete: {result.created} created, "
            f"{result.updated} updated, {result.skipped} skipped, "
            f"{result.errors} errors [correlation_id={correlation_id}]"
        )

        return result

    def _populate_vendor_cache(self) -> None:
        """Pre-populate vendor cache with all existing vendors."""
        try:
            page = 1
            while True:
                vendors = self.vendor_repo.list(page=page, page_size=200)
                if not vendors:
                    break

                for vendor in vendors:
                    self._vendor_cache[vendor.id] = vendor

                if len(vendors) < 200:
                    break
                page += 1

            logger.debug(f"Populated vendor cache with {len(self._vendor_cache)} vendors")
        except Exception as e:
            logger.warning(f"Failed to populate vendor cache: {e}")

    def find_or_create(
        self,
        vendor_name: str,
        vendor_data: Optional[Dict[str, Any]] = None,
    ) -> Vendor:
        """
        Find existing vendor by name or create new one.

        Args:
            vendor_name: Vendor name to search.
            vendor_data: Optional additional data for creation.

        Returns:
            Existing or newly created vendor.
        """
        # Try to find existing
        existing = self.vendor_repo.get_by_name(vendor_name)
        if existing:
            return existing

        # Create new vendor
        vendor = Vendor(
            name=vendor_name,
            status=VendorStatus.ACTIVE,
        )

        if vendor_data:
            if "email" in vendor_data:
                vendor.email = vendor_data["email"]
            if "external_id" in vendor_data:
                vendor.external_id = vendor_data["external_id"]
            if "payment_method" in vendor_data:
                from src.domain.models.common import PaymentMethod
                vendor.payment_method = PaymentMethod(vendor_data["payment_method"])

        created = self.vendor_repo.create(vendor)
        self._vendor_cache[created.id] = created
        return created

    def archive_vendor(self, vendor_id: str) -> SyncResult:
        """
        Archive a vendor (soft delete).

        Args:
            vendor_id: Vendor ID to archive.

        Returns:
            SyncResult with operation details.
        """
        try:
            vendor = self.vendor_repo.get_by_id(vendor_id)
            if not vendor:
                return SyncResult(
                    success=False,
                    action="error",
                    entity_id=vendor_id,
                    message="Vendor not found",
                )

            vendor.status = VendorStatus.ARCHIVED
            updated = self.vendor_repo.update(vendor)

            # Update cache
            if vendor_id in self._vendor_cache:
                del self._vendor_cache[vendor_id]

            logger.info(f"Archived vendor: {updated.name}")
            return SyncResult(
                success=True,
                action="update",
                entity_id=vendor_id,
                message=f"Archived vendor {updated.name}",
            )
        except Exception as e:
            logger.error(f"Failed to archive vendor {vendor_id}: {e}")
            return SyncResult(
                success=False,
                action="error",
                entity_id=vendor_id,
                message=str(e),
            )

    def get_active_vendors(self) -> List[Vendor]:
        """
        Get all active vendors.

        Returns:
            List of active vendors.
        """
        vendors = []
        page = 1

        while True:
            batch = self.vendor_repo.list(
                page=page,
                page_size=200,
                filters={"status": VendorStatus.ACTIVE.value},
            )
            if not batch:
                break

            vendors.extend(batch)

            if len(batch) < 200:
                break
            page += 1

        return vendors
