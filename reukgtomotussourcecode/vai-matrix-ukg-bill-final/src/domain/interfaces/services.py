"""
Service interfaces - Abstract business operation contracts.

These interfaces define the contracts for business operations
that orchestrate work across multiple repositories.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.domain.models.employee import Employee
from src.domain.models.bill_user import BillUser, BillRole
from src.domain.models.vendor import Vendor
from src.domain.models.invoice import Invoice
from src.domain.models.payment import Payment


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    action: str  # 'create', 'update', 'skip', 'error'
    entity_id: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action": self.action,
            "entity_id": self.entity_id,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class BatchSyncResult:
    """Result of a batch sync operation."""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    results: List[SyncResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    correlation_id: str = ""

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total == 0:
            return 0.0
        return ((self.created + self.updated + self.skipped) / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "correlation_id": self.correlation_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class EmployeeSyncService(ABC):
    """
    Service interface for syncing employees from UKG to BILL.

    Orchestrates the process of reading employees from UKG
    and creating/updating them in BILL.com.
    """

    @abstractmethod
    def sync_employee(
        self,
        employee: Employee,
        default_role: BillRole = BillRole.MEMBER,
    ) -> SyncResult:
        """
        Sync a single employee to BILL.

        Args:
            employee: Employee to sync
            default_role: Default role for new users

        Returns:
            Sync result
        """
        pass

    @abstractmethod
    def sync_batch(
        self,
        employees: List[Employee],
        default_role: BillRole = BillRole.MEMBER,
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync multiple employees to BILL.

        Args:
            employees: Employees to sync
            default_role: Default role for new users
            workers: Number of concurrent workers

        Returns:
            Batch sync result
        """
        pass

    @abstractmethod
    def sync_all(
        self,
        company_id: Optional[str] = None,
        default_role: BillRole = BillRole.MEMBER,
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync all active employees from UKG to BILL.

        Args:
            company_id: Optional company filter
            default_role: Default role for new users
            workers: Number of concurrent workers

        Returns:
            Batch sync result
        """
        pass

    @abstractmethod
    def resolve_supervisor_email(
        self,
        employee: Employee,
    ) -> Optional[str]:
        """
        Resolve supervisor email for an employee.

        Implements fallback strategies:
        1. Direct supervisorEmailAddress field
        2. Supervisor employee ID -> person details
        3. Supervisor employee number -> person details

        Args:
            employee: Employee to resolve supervisor for

        Returns:
            Supervisor email or None
        """
        pass


class VendorSyncService(ABC):
    """
    Service interface for vendor management.

    Orchestrates vendor CRUD operations in BILL.com.
    """

    @abstractmethod
    def sync_vendor(self, vendor: Vendor) -> SyncResult:
        """
        Sync a vendor to BILL.

        Args:
            vendor: Vendor to sync

        Returns:
            Sync result
        """
        pass

    @abstractmethod
    def sync_batch(
        self,
        vendors: List[Vendor],
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync multiple vendors to BILL.

        Args:
            vendors: Vendors to sync
            workers: Number of concurrent workers

        Returns:
            Batch sync result
        """
        pass

    @abstractmethod
    def find_or_create(
        self,
        vendor_name: str,
        vendor_data: Optional[Dict[str, Any]] = None,
    ) -> Vendor:
        """
        Find existing vendor or create new one.

        Args:
            vendor_name: Vendor name to search
            vendor_data: Optional data for creation

        Returns:
            Existing or newly created vendor
        """
        pass


class InvoiceSyncService(ABC):
    """
    Service interface for invoice/bill management.

    Orchestrates invoice CRUD operations in BILL.com.
    """

    @abstractmethod
    def sync_invoice(
        self,
        invoice: Invoice,
        vendor_mapping: Optional[Dict[str, str]] = None,
    ) -> SyncResult:
        """
        Sync an invoice to BILL.

        Args:
            invoice: Invoice to sync
            vendor_mapping: Optional external vendor ID to BILL vendor ID mapping

        Returns:
            Sync result
        """
        pass

    @abstractmethod
    def sync_batch(
        self,
        invoices: List[Invoice],
        vendor_mapping: Optional[Dict[str, str]] = None,
        workers: int = 12,
    ) -> BatchSyncResult:
        """
        Sync multiple invoices to BILL.

        Args:
            invoices: Invoices to sync
            vendor_mapping: Optional vendor ID mapping
            workers: Number of concurrent workers

        Returns:
            Batch sync result
        """
        pass

    @abstractmethod
    def get_payable_invoices(
        self,
        vendor_id: Optional[str] = None,
    ) -> List[Invoice]:
        """
        Get all invoices ready for payment.

        Args:
            vendor_id: Optional vendor filter

        Returns:
            List of payable invoices
        """
        pass


class PaymentService(ABC):
    """
    Service interface for payment processing.

    Orchestrates payment operations in BILL.com.
    """

    @abstractmethod
    def create_payment(
        self,
        invoice: Invoice,
        amount: Optional[float] = None,
        funding_account_id: Optional[str] = None,
    ) -> SyncResult:
        """
        Create a payment for an invoice.

        Args:
            invoice: Invoice to pay
            amount: Payment amount (defaults to full amount)
            funding_account_id: Funding account to use

        Returns:
            Sync result with payment details
        """
        pass

    @abstractmethod
    def create_bulk_payments(
        self,
        invoices: List[Invoice],
        funding_account_id: Optional[str] = None,
    ) -> BatchSyncResult:
        """
        Create payments for multiple invoices.

        Args:
            invoices: Invoices to pay
            funding_account_id: Funding account to use

        Returns:
            Batch sync result
        """
        pass

    @abstractmethod
    def record_external_payment(
        self,
        bill_id: str,
        amount: float,
        payment_date: str,
        reference: Optional[str] = None,
    ) -> SyncResult:
        """
        Record a payment made outside BILL.

        Args:
            bill_id: BILL invoice ID
            amount: Payment amount
            payment_date: Date payment was made
            reference: External reference number

        Returns:
            Sync result
        """
        pass

    @abstractmethod
    def get_payment_status(self, payment_id: str) -> Payment:
        """
        Get current status of a payment.

        Args:
            payment_id: Payment ID

        Returns:
            Payment with current status
        """
        pass


class CsvExportService(ABC):
    """
    Service interface for CSV export operations.

    Used for exporting data to CSV for BILL.com UI import.
    """

    @abstractmethod
    def export_users_csv(
        self,
        users: List[BillUser],
        output_path: str,
    ) -> str:
        """
        Export users to CSV for BILL.com People import.

        Args:
            users: Users to export
            output_path: Output file path

        Returns:
            Path to created CSV file
        """
        pass

    @abstractmethod
    def export_vendors_csv(
        self,
        vendors: List[Vendor],
        output_path: str,
    ) -> str:
        """
        Export vendors to CSV.

        Args:
            vendors: Vendors to export
            output_path: Output file path

        Returns:
            Path to created CSV file
        """
        pass

    @abstractmethod
    def export_invoices_csv(
        self,
        invoices: List[Invoice],
        output_path: str,
    ) -> str:
        """
        Export invoices to CSV.

        Args:
            invoices: Invoices to export
            output_path: Output file path

        Returns:
            Path to created CSV file
        """
        pass


class NotificationService(ABC):
    """
    Service interface for notifications.

    Handles sending email alerts and reports.
    """

    @abstractmethod
    def send_run_summary(
        self,
        result: BatchSyncResult,
        recipients: List[str],
    ) -> bool:
        """
        Send sync run summary email.

        Args:
            result: Batch sync result
            recipients: Email recipients

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_error_alert(
        self,
        error: Exception,
        context: Dict[str, Any],
        recipients: List[str],
    ) -> bool:
        """
        Send critical error alert.

        Args:
            error: Exception that occurred
            context: Additional context
            recipients: Email recipients

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_payment_confirmation(
        self,
        payments: List[Payment],
        recipients: List[str],
    ) -> bool:
        """
        Send payment confirmation email.

        Args:
            payments: Payments that were processed
            recipients: Email recipients

        Returns:
            True if sent successfully
        """
        pass
