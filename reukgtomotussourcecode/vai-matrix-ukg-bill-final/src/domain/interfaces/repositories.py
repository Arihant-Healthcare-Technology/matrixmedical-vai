"""
Repository interfaces - Abstract data access contracts.

These interfaces define the contracts for data access operations.
Implementations can use different data sources (API, database, file, etc.)
without affecting the business logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar

from src.domain.models.employee import Employee
from src.domain.models.bill_user import BillUser
from src.domain.models.vendor import Vendor
from src.domain.models.invoice import Invoice
from src.domain.models.payment import Payment, ExternalPayment

# Generic type for entities
T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """
    Base repository interface.

    Defines common CRUD operations for all repositories.
    """

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            entity_id: Entity identifier

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[T]:
        """
        List entities with pagination and optional filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            filters: Optional filter criteria

        Returns:
            List of entities
        """
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with ID assigned
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: Entity with updated data

        Returns:
            Updated entity
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            True if deleted, False if not found
        """
        pass


class EmployeeRepository(Repository[Employee], ABC):
    """
    Repository interface for UKG Pro employees.

    Provides access to employee data from UKG Pro.
    """

    @abstractmethod
    def get_by_employee_number(self, employee_number: str) -> Optional[Employee]:
        """
        Get employee by employee number.

        Args:
            employee_number: Human-readable employee number

        Returns:
            Employee if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Employee]:
        """
        Get employee by email address.

        Args:
            email: Employee email

        Returns:
            Employee if found, None otherwise
        """
        pass

    @abstractmethod
    def get_active_employees(
        self,
        company_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Employee]:
        """
        Get all active employees.

        Args:
            company_id: Optional company filter
            page: Page number
            page_size: Page size

        Returns:
            List of active employees
        """
        pass

    @abstractmethod
    def get_employees_with_supervisor(
        self,
        supervisor_id: str,
    ) -> List[Employee]:
        """
        Get employees reporting to a supervisor.

        Args:
            supervisor_id: Supervisor's employee ID

        Returns:
            List of direct reports
        """
        pass

    @abstractmethod
    def get_person_details(self, employee_id: str) -> Dict[str, Any]:
        """
        Get additional person details from UKG.

        Args:
            employee_id: Employee ID

        Returns:
            Person details dictionary
        """
        pass


class BillUserRepository(Repository[BillUser], ABC):
    """
    Repository interface for BILL.com Spend & Expense users.

    Provides CRUD operations for BILL S&E users.
    """

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[BillUser]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            BillUser if found, None otherwise
        """
        pass

    @abstractmethod
    def get_active_users(self) -> List[BillUser]:
        """
        Get all active (non-retired) users.

        Returns:
            List of active users
        """
        pass

    @abstractmethod
    def retire_user(self, user_id: str) -> bool:
        """
        Retire (deactivate) a user.

        Args:
            user_id: User ID to retire

        Returns:
            True if retired, False if not found or already retired
        """
        pass

    @abstractmethod
    def upsert(self, user: BillUser) -> BillUser:
        """
        Create or update a user based on email lookup.

        Args:
            user: User data

        Returns:
            Created or updated user
        """
        pass


class VendorRepository(Repository[Vendor], ABC):
    """
    Repository interface for BILL.com Accounts Payable vendors.

    Provides CRUD operations for AP vendors.
    """

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Vendor]:
        """
        Get vendor by name (exact match).

        Args:
            name: Vendor name

        Returns:
            Vendor if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> Optional[Vendor]:
        """
        Get vendor by external ID.

        Args:
            external_id: External identifier

        Returns:
            Vendor if found, None otherwise
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Vendor]:
        """
        Search vendors by name or other criteria.

        Args:
            query: Search query
            page: Page number
            page_size: Page size

        Returns:
            Matching vendors
        """
        pass

    @abstractmethod
    def get_active_vendors(self) -> List[Vendor]:
        """
        Get all active vendors.

        Returns:
            List of active vendors
        """
        pass

    @abstractmethod
    def upsert(self, vendor: Vendor) -> Vendor:
        """
        Create or update a vendor based on name/external_id lookup.

        Args:
            vendor: Vendor data

        Returns:
            Created or updated vendor
        """
        pass


class InvoiceRepository(Repository[Invoice], ABC):
    """
    Repository interface for BILL.com Accounts Payable invoices/bills.

    Provides CRUD operations for AP bills.
    """

    @abstractmethod
    def get_by_invoice_number(
        self,
        invoice_number: str,
        vendor_id: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Get invoice by invoice number.

        Args:
            invoice_number: Vendor's invoice number
            vendor_id: Optional vendor filter

        Returns:
            Invoice if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> Optional[Invoice]:
        """
        Get invoice by external ID.

        Args:
            external_id: External identifier

        Returns:
            Invoice if found, None otherwise
        """
        pass

    @abstractmethod
    def get_invoices_for_vendor(
        self,
        vendor_id: str,
        status: Optional[str] = None,
    ) -> List[Invoice]:
        """
        Get all invoices for a vendor.

        Args:
            vendor_id: Vendor ID
            status: Optional status filter

        Returns:
            List of invoices
        """
        pass

    @abstractmethod
    def get_unpaid_invoices(
        self,
        vendor_id: Optional[str] = None,
    ) -> List[Invoice]:
        """
        Get all unpaid invoices.

        Args:
            vendor_id: Optional vendor filter

        Returns:
            List of unpaid invoices
        """
        pass

    @abstractmethod
    def get_overdue_invoices(self) -> List[Invoice]:
        """
        Get all overdue invoices.

        Returns:
            List of invoices past due date
        """
        pass

    @abstractmethod
    def upsert(self, invoice: Invoice) -> Invoice:
        """
        Create or update an invoice based on invoice_number lookup.

        Args:
            invoice: Invoice data

        Returns:
            Created or updated invoice
        """
        pass


class PaymentRepository(Repository[Payment], ABC):
    """
    Repository interface for BILL.com Accounts Payable payments.

    Provides operations for payment processing.
    """

    @abstractmethod
    def get_payments_for_bill(self, bill_id: str) -> List[Payment]:
        """
        Get all payments for a specific bill.

        Args:
            bill_id: Bill ID

        Returns:
            List of payments
        """
        pass

    @abstractmethod
    def get_payments_by_status(
        self,
        status: str,
        page: int = 1,
        page_size: int = 200,
    ) -> List[Payment]:
        """
        Get payments by status.

        Args:
            status: Payment status
            page: Page number
            page_size: Page size

        Returns:
            List of payments
        """
        pass

    @abstractmethod
    def get_payment_options(self, bill_id: str) -> Dict[str, Any]:
        """
        Get available payment options for a bill.

        Args:
            bill_id: Bill ID

        Returns:
            Payment options including available methods and funding accounts
        """
        pass

    @abstractmethod
    def create_bulk(self, payments: List[Payment]) -> List[Payment]:
        """
        Create multiple payments in bulk.

        Args:
            payments: List of payments to create

        Returns:
            List of created payments
        """
        pass

    @abstractmethod
    def record_external_payment(self, payment: ExternalPayment) -> Payment:
        """
        Record an external payment made outside BILL.

        Args:
            payment: External payment details

        Returns:
            Recorded payment
        """
        pass

    @abstractmethod
    def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancel a pending payment.

        Args:
            payment_id: Payment ID to cancel

        Returns:
            True if cancelled, False if not cancellable
        """
        pass


class UnitOfWork(ABC):
    """
    Unit of Work pattern interface.

    Provides transaction-like behavior for coordinating
    multiple repository operations.
    """

    employees: EmployeeRepository
    bill_users: BillUserRepository
    vendors: VendorRepository
    invoices: InvoiceRepository
    payments: PaymentRepository

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        """Enter context manager."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit all changes."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback all changes."""
        pass
