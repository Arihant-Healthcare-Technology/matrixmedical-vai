"""Tests for BatchProcessor service."""

import pytest
from unittest.mock import MagicMock, patch

from src.application.services.batch_processor import (
    BatchProcessor,
    BatchResult,
    ProcessingProgress,
)


class TestBatchResult:
    """Test cases for BatchResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = BatchResult()
        assert result.saved == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.dry_run == 0
        assert result.id_mapping == {}

    def test_init_with_values(self):
        """Test initialization with custom values."""
        result = BatchResult(saved=5, skipped=2, errors=1, dry_run=3)
        assert result.saved == 5
        assert result.skipped == 2
        assert result.errors == 1
        assert result.dry_run == 3

    def test_total_processed(self):
        """Test total_processed property."""
        result = BatchResult(saved=5, skipped=2, errors=1, dry_run=3)
        assert result.total_processed == 11

    def test_to_dict(self):
        """Test to_dict method."""
        result = BatchResult(saved=5, skipped=2, errors=1, dry_run=3)
        result.id_mapping = {"12345": "tp-123", "12346": "tp-124"}

        d = result.to_dict()

        assert d["saved"] == 5
        assert d["skipped"] == 2
        assert d["errors"] == 1
        assert d["dry_run"] == 3
        assert d["total_processed"] == 11
        assert d["id_mapping_count"] == 2

    def test_id_mapping_none_becomes_dict(self):
        """Test that None id_mapping becomes empty dict."""
        result = BatchResult(id_mapping=None)
        assert result.id_mapping == {}


class TestProcessingProgress:
    """Test cases for ProcessingProgress dataclass."""

    def test_default_values(self):
        """Test default values."""
        progress = ProcessingProgress(total=100)
        assert progress.total == 100
        assert progress.processed == 0
        assert progress.saved == 0
        assert progress.skipped == 0
        assert progress.errors == 0

    def test_percentage_zero_total(self):
        """Test percentage returns 100 when total is 0."""
        progress = ProcessingProgress(total=0)
        assert progress.percentage == 100.0

    def test_percentage_calculation(self):
        """Test percentage calculation."""
        progress = ProcessingProgress(total=100, processed=50)
        assert progress.percentage == 50.0

    def test_update_saved(self):
        """Test update with saved status."""
        progress = ProcessingProgress(total=10)
        progress.update("saved", "12345", "tp-123")

        assert progress.processed == 1
        assert progress.saved == 1
        assert progress.skipped == 0
        assert progress.errors == 0

    def test_update_dry_run(self):
        """Test update with dry_run status."""
        progress = ProcessingProgress(total=10)
        progress.update("dry_run", "12345", "tp-123")

        assert progress.processed == 1
        assert progress.saved == 1  # dry_run counts as saved
        assert progress.errors == 0

    def test_update_error(self):
        """Test update with error status."""
        progress = ProcessingProgress(total=10)
        progress.update("error", "12345")

        assert progress.processed == 1
        assert progress.errors == 1
        assert progress.saved == 0

    def test_update_skipped(self):
        """Test update with skipped/other status."""
        progress = ProcessingProgress(total=10)
        progress.update("skipped", "12345")

        assert progress.processed == 1
        assert progress.skipped == 1
        assert progress.saved == 0
        assert progress.errors == 0


class TestBatchProcessor:
    """Test cases for BatchProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create batch processor for testing."""
        return BatchProcessor(workers=2, progress_interval=1, debug=False)

    def test_init(self):
        """Test batch processor initialization."""
        processor = BatchProcessor(workers=4, progress_interval=50, debug=True)
        assert processor.workers == 4
        assert processor.progress_interval == 50
        assert processor.debug is True

    def test_process_batch_empty_items(self, processor):
        """Test processing empty items list."""
        def mock_processor(item):
            return ("12345", "FL", "saved", "tp-123")

        result = processor.process_batch([], mock_processor, "Test")

        assert result.total_processed == 0
        assert result.saved == 0

    def test_process_batch_single_item(self, processor):
        """Test processing single item."""
        def mock_processor(item):
            return (item["employeeNumber"], "FL", "saved", "tp-123")

        items = [{"employeeNumber": "12345"}]
        result = processor.process_batch(items, mock_processor, "Test")

        assert result.saved == 1
        assert result.id_mapping == {"12345": "tp-123"}

    def test_process_batch_multiple_items(self, processor):
        """Test processing multiple items."""
        def mock_processor(item):
            return (item["employeeNumber"], "FL", "saved", f"tp-{item['employeeNumber']}")

        items = [
            {"employeeNumber": "12345"},
            {"employeeNumber": "12346"},
            {"employeeNumber": "12347"},
        ]
        result = processor.process_batch(items, mock_processor, "Test")

        assert result.saved == 3
        assert len(result.id_mapping) == 3

    def test_process_batch_mixed_results(self, processor):
        """Test processing with mixed results."""
        def mock_processor(item):
            emp_num = item["employeeNumber"]
            if emp_num == "12345":
                return (emp_num, "FL", "saved", "tp-123")
            elif emp_num == "12346":
                return (emp_num, "CA", "skipped", None)
            else:
                return (emp_num, "TX", "error", None)

        items = [
            {"employeeNumber": "12345"},
            {"employeeNumber": "12346"},
            {"employeeNumber": "12347"},
        ]
        result = processor.process_batch(items, mock_processor, "Test")

        assert result.saved == 1
        assert result.skipped == 1
        assert result.errors == 1

    def test_process_batch_dry_run(self, processor):
        """Test processing with dry_run status."""
        def mock_processor(item):
            return (item["employeeNumber"], "FL", "dry_run", "tp-123")

        items = [{"employeeNumber": "12345"}]
        result = processor.process_batch(items, mock_processor, "Test")

        assert result.dry_run == 1
        assert result.saved == 0
        assert result.id_mapping == {"12345": "tp-123"}

    def test_process_batch_exception_handling(self, processor):
        """Test exception handling during processing."""
        def mock_processor(item):
            if item["employeeNumber"] == "12346":
                raise ValueError("Test error")
            return (item["employeeNumber"], "FL", "saved", "tp-123")

        items = [
            {"employeeNumber": "12345"},
            {"employeeNumber": "12346"},
        ]
        result = processor.process_batch(items, mock_processor, "Test")

        assert result.saved == 1
        assert result.errors == 1

    def test_process_with_context(self, processor):
        """Test processing with shared context."""
        def mock_processor(item, context):
            return (item["employeeNumber"], "FL", "saved", context["prefix"] + "-123")

        items = [{"employeeNumber": "12345"}]
        context = {"prefix": "tp"}
        result = processor.process_with_context(items, mock_processor, context, "Test")

        assert result.saved == 1
        assert result.id_mapping == {"12345": "tp-123"}
