"""
Batch processing service.

Handles parallel processing of employee batches with progress tracking.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of batch processing."""

    saved: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run: int = 0
    id_mapping: Dict[str, str] = None

    def __post_init__(self):
        if self.id_mapping is None:
            self.id_mapping = {}

    @property
    def total_processed(self) -> int:
        """Total items processed."""
        return self.saved + self.skipped + self.errors + self.dry_run

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "saved": self.saved,
            "skipped": self.skipped,
            "errors": self.errors,
            "dry_run": self.dry_run,
            "total_processed": self.total_processed,
            "id_mapping_count": len(self.id_mapping),
        }


@dataclass
class ProcessingProgress:
    """Progress tracking for batch processing."""

    total: int
    processed: int = 0
    saved: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total == 0:
            return 100.0
        return (self.processed / self.total) * 100

    def update(
        self,
        status: str,
        employee_number: str,
        travelperk_id: Optional[str] = None,
    ) -> None:
        """Update progress with new result."""
        self.processed += 1

        if status in ("saved", "dry_run"):
            self.saved += 1
        elif status == "error":
            self.errors += 1
        else:
            self.skipped += 1


class BatchProcessor:
    """Handles parallel batch processing of employees."""

    def __init__(
        self,
        workers: int = 4,
        progress_interval: int = 100,
        debug: bool = False,
    ):
        """
        Initialize batch processor.

        Args:
            workers: Number of worker threads
            progress_interval: Log progress every N items
            debug: Enable debug logging
        """
        self.workers = workers
        self.progress_interval = progress_interval
        self.debug = debug

    def process_batch(
        self,
        items: List[Any],
        processor_func: Callable[[Any], Tuple[str, str, str, Optional[str]]],
        phase_name: str = "Processing",
    ) -> BatchResult:
        """
        Process batch of items in parallel.

        Args:
            items: List of items to process
            processor_func: Function that processes a single item
                           Returns: (employee_number, state, status, travelperk_id)
            phase_name: Name for logging

        Returns:
            BatchResult with processing results
        """
        total = len(items)
        result = BatchResult()
        progress = ProcessingProgress(total=total)

        logger.info(f"{phase_name}: Starting with {total} items, {self.workers} workers")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(processor_func, item): item for item in items
            }

            # Process results as they complete
            for future in as_completed(future_to_item):
                try:
                    emp_number, state, status, travelperk_id = future.result()

                    progress.update(status, emp_number, travelperk_id)

                    if status in ("saved", "dry_run"):
                        if status == "saved":
                            result.saved += 1
                        else:
                            result.dry_run += 1
                        if travelperk_id:
                            result.id_mapping[emp_number] = travelperk_id
                    elif status == "error":
                        result.errors += 1
                    else:
                        result.skipped += 1

                    # Log progress periodically
                    if (
                        progress.processed % self.progress_interval == 0
                        or progress.processed == total
                    ):
                        logger.info(
                            f"{phase_name} Progress: {progress.processed}/{total} | "
                            f"saved={result.saved} skipped={result.skipped} errors={result.errors}"
                        )

                except Exception as e:
                    result.errors += 1
                    progress.errors += 1
                    progress.processed += 1
                    logger.error(f"{phase_name} error processing item: {e}")

        logger.info(
            f"{phase_name} Complete: saved={result.saved} skipped={result.skipped} "
            f"errors={result.errors} dry_run={result.dry_run}"
        )

        return result

    def process_with_context(
        self,
        items: List[Any],
        processor_func: Callable[[Any, Dict], Tuple[str, str, str, Optional[str]]],
        context: Dict[str, Any],
        phase_name: str = "Processing",
    ) -> BatchResult:
        """
        Process batch with shared context.

        Args:
            items: List of items to process
            processor_func: Function that takes (item, context) and returns result tuple
            context: Shared context dictionary
            phase_name: Name for logging

        Returns:
            BatchResult with processing results
        """

        def wrapped_processor(item: Any) -> Tuple[str, str, str, Optional[str]]:
            return processor_func(item, context)

        return self.process_batch(items, wrapped_processor, phase_name)
