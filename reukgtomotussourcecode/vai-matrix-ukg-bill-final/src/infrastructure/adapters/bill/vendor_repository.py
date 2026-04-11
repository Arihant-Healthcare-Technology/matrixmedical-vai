"""
BILL.com Accounts Payable vendor repository implementation.

This module implements the VendorRepository interface using the AP API client.
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.interfaces.repositories import VendorRepository
from src.domain.models.vendor import Vendor
from src.infrastructure.adapters.bill.accounts_payable_client import AccountsPayableClient

logger = logging.getLogger(__name__)


class VendorRepositoryImpl(VendorRepository):
    """
    BILL.com Accounts Payable vendor repository implementation.

    Implements the VendorRepository interface using the AP API client.
    """

    def __init__(self, client: AccountsPayableClient) -> None:
        """
        Initialize repository.

        Args:
            client: AP API client
        """
        self._client = client
        self._name_cache: Dict[str, str] = {}  # name -> vendor_id
        self._external_id_cache: Dict[str, str] = {}  # external_id -> vendor_id

    def get_by_id(self, entity_id: str) -> Optional[Vendor]:
        """Get vendor by BILL ID."""
        try:
            data = self._client.get_vendor(entity_id)
            if data:
                return Vendor.from_bill_api(data)
        except Exception as e:
            logger.debug(f"Vendor not found by ID {entity_id}: {e}")

        return None

    def get_by_name(self, name: str) -> Optional[Vendor]:
        """Get vendor by name (exact match)."""
        name_lower = name.lower().strip()

        # Check cache
        if name_lower in self._name_cache:
            vendor_id = self._name_cache[name_lower]
            return self.get_by_id(vendor_id)

        # Search via API
        data = self._client.get_vendor_by_name(name)
        if data:
            vendor = Vendor.from_bill_api(data)
            if vendor.id:
                self._name_cache[name_lower] = vendor.id
            return vendor

        return None

    def get_by_external_id(self, external_id: str) -> Optional[Vendor]:
        """Get vendor by external ID."""
        # Check cache
        if external_id in self._external_id_cache:
            vendor_id = self._external_id_cache[external_id]
            return self.get_by_id(vendor_id)

        # Search via API
        data = self._client.get_vendor_by_external_id(external_id)
        if data:
            vendor = Vendor.from_bill_api(data)
            if vendor.id:
                self._external_id_cache[external_id] = vendor.id
            return vendor

        return None

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Vendor]:
        """Search vendors by name."""
        query_lower = query.lower().strip()
        all_vendors = self._client.list_vendors(page=page, page_size=page_size)

        results = []
        for data in all_vendors:
            name = data.get("name", "").lower()
            if query_lower in name:
                results.append(Vendor.from_bill_api(data))

        return results

    def get_active_vendors(self) -> List[Vendor]:
        """Get all active vendors."""
        data = self._client.get_all_vendors(status="active")
        vendors = []

        for item in data:
            vendor = Vendor.from_bill_api(item)
            vendors.append(vendor)
            # Update caches
            if vendor.id:
                if vendor.name:
                    self._name_cache[vendor.name.lower()] = vendor.id
                if vendor.external_id:
                    self._external_id_cache[vendor.external_id] = vendor.id

        return vendors

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Vendor]:
        """List vendors with pagination."""
        filters = filters or {}
        status = filters.get("status")

        data = self._client.list_vendors(
            page=page,
            page_size=page_size,
            status=status,
        )

        return [Vendor.from_bill_api(item) for item in data]

    def create(self, entity: Vendor) -> Vendor:
        """Create new vendor in BILL."""
        payload = entity.to_api_payload()
        data = self._client.create_vendor(payload)
        created = Vendor.from_bill_api(data)

        # Update caches
        if created.id:
            if created.name:
                self._name_cache[created.name.lower()] = created.id
            if created.external_id:
                self._external_id_cache[created.external_id] = created.id

        logger.info(f"Created vendor: {created.name} ({created.id})")
        return created

    def update(self, entity: Vendor) -> Vendor:
        """Update existing vendor in BILL."""
        if not entity.id:
            raise ValueError("Cannot update vendor without ID")

        payload = entity.to_api_payload()
        data = self._client.update_vendor(entity.id, payload)

        if not data:
            data = self._client.get_vendor(entity.id)

        updated = Vendor.from_bill_api(data) if data else entity
        logger.info(f"Updated vendor: {updated.name} ({updated.id})")
        return updated

    def delete(self, entity_id: str) -> bool:
        """Delete operation not typically supported for vendors."""
        raise NotImplementedError("Vendor deletion not supported. Use archive instead.")

    def upsert(self, vendor: Vendor) -> Vendor:
        """Create or update vendor based on name/external_id lookup."""
        existing = None

        # Try external ID first
        if vendor.external_id:
            existing = self.get_by_external_id(vendor.external_id)

        # Fall back to name
        if not existing and vendor.name:
            existing = self.get_by_name(vendor.name)

        if existing:
            if vendor.needs_update(existing):
                vendor.id = existing.id
                return self.update(vendor)
            else:
                logger.debug(f"No changes for vendor: {vendor.name}")
                return existing
        else:
            return self.create(vendor)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._name_cache.clear()
        self._external_id_cache.clear()
