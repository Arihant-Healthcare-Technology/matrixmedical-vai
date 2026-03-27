"""
Domain interfaces - Abstract repository and service contracts.

This module exports all abstract interfaces that define the contracts
for data access and business operations.
"""

from src.domain.interfaces.repositories import (
    BillUserRepository,
    EmployeeRepository,
    InvoiceRepository,
    PaymentRepository,
    Repository,
    UnitOfWork,
    VendorRepository,
)
from src.domain.interfaces.services import (
    BatchSyncResult,
    CsvExportService,
    EmployeeSyncService,
    InvoiceSyncService,
    NotificationService,
    PaymentService,
    SyncResult,
    VendorSyncService,
)

__all__ = [
    # Base repository
    "Repository",
    # Entity repositories
    "BillUserRepository",
    "EmployeeRepository",
    "InvoiceRepository",
    "PaymentRepository",
    "VendorRepository",
    # Unit of Work
    "UnitOfWork",
    # Sync services
    "EmployeeSyncService",
    "InvoiceSyncService",
    "PaymentService",
    "VendorSyncService",
    # Support services
    "CsvExportService",
    "NotificationService",
    # Result types
    "BatchSyncResult",
    "SyncResult",
]
