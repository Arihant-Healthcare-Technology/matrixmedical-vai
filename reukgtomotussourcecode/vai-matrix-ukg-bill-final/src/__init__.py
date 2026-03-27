"""
UKG to BILL.com Integration Suite.

This package provides enterprise-grade integration between UKG Pro and BILL.com,
supporting both Spend & Expense (S&E) and Accounts Payable (AP) modules.

Architecture follows Clean Architecture / Hexagonal Architecture principles:
- domain/: Core business entities and interfaces (innermost layer)
- application/: Use cases and business logic orchestration
- infrastructure/: External adapters (APIs, databases, scraping)
- presentation/: CLI and output formatting
"""

__version__ = "2.0.0"
__author__ = "VAI Consulting"
