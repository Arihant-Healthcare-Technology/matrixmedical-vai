"""
Unit tests for correlation module.
Tests for SOW Requirement 7.2 - Correlation ID generation and propagation.
"""
import sys
import logging
import threading
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.correlation import (
    generate_correlation_id,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    correlation_context,
    with_correlation_id,
    CorrelationLogFilter,
    CorrelationLogFormatter,
)


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id function."""

    def test_generates_uuid(self):
        """Test generates UUID format."""
        cid = generate_correlation_id()
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(cid) == 36
        assert cid.count("-") == 4

    def test_generates_unique_ids(self):
        """Test generates unique IDs."""
        ids = [generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_with_prefix(self):
        """Test generates ID with prefix."""
        cid = generate_correlation_id(prefix="bill")
        assert cid.startswith("bill-")

    def test_without_prefix(self):
        """Test generates ID without prefix."""
        cid = generate_correlation_id()
        assert not cid.startswith("-")


class TestSetGetCorrelationId:
    """Tests for set/get correlation ID functions."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_set_and_get(self):
        """Test setting and getting correlation ID."""
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

    def test_get_returns_none_when_not_set(self):
        """Test returns None when cleared (thread-local set to None)."""
        clear_correlation_id()
        # When cleared, thread-local value is None, so getattr returns None not UNKNOWN
        assert get_correlation_id() is None

    def test_clear_removes_id(self):
        """Test clear removes the ID."""
        set_correlation_id("test-456")
        clear_correlation_id()
        # After clear, thread-local value is None
        assert get_correlation_id() is None

    def test_overwrite_id(self):
        """Test overwriting correlation ID."""
        set_correlation_id("first")
        set_correlation_id("second")
        assert get_correlation_id() == "second"


class TestCorrelationContext:
    """Tests for correlation_context context manager."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_context_generates_new_id(self):
        """Test context generates new ID when none provided."""
        with correlation_context() as cid:
            assert cid is not None
            assert len(cid) == 36  # UUID format
            assert get_correlation_id() == cid

    def test_context_uses_provided_id(self):
        """Test context uses provided ID."""
        with correlation_context("my-custom-id") as cid:
            assert cid == "my-custom-id"
            assert get_correlation_id() == "my-custom-id"

    def test_context_with_prefix(self):
        """Test context generates ID with prefix."""
        with correlation_context(prefix="motus") as cid:
            assert cid.startswith("motus-")

    def test_context_clears_after_exit(self):
        """Test context clears ID after exit."""
        with correlation_context("temp-id"):
            pass
        # After context exit with no previous ID, value is cleared to None
        assert get_correlation_id() is None

    def test_nested_context_restores_previous(self):
        """Test nested contexts restore previous ID."""
        with correlation_context("outer-id") as outer:
            assert get_correlation_id() == outer

            with correlation_context("inner-id") as inner:
                assert get_correlation_id() == inner

            assert get_correlation_id() == outer

    def test_context_handles_exception(self):
        """Test context clears ID even on exception."""
        with pytest.raises(ValueError):
            with correlation_context("exception-test"):
                raise ValueError("Test error")

        # ID should be cleared after exception (set to None)
        assert get_correlation_id() is None


class TestWithCorrelationIdDecorator:
    """Tests for with_correlation_id decorator."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_decorator_generates_id_when_none(self):
        """Test decorator generates ID when none exists."""
        captured_id = None

        @with_correlation_id
        def my_function():
            nonlocal captured_id
            captured_id = get_correlation_id()
            return "result"

        result = my_function()
        assert result == "result"
        assert captured_id is not None
        assert captured_id != "UNKNOWN"

    def test_decorator_uses_existing_id(self):
        """Test decorator uses existing ID."""
        captured_id = None

        @with_correlation_id
        def my_function():
            nonlocal captured_id
            captured_id = get_correlation_id()

        with correlation_context("existing-id"):
            my_function()

        assert captured_id == "existing-id"

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function name."""
        @with_correlation_id
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"


class TestCorrelationLogFilter:
    """Tests for CorrelationLogFilter."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_filter_adds_correlation_id(self):
        """Test filter adds correlation_id to record."""
        set_correlation_id("filter-test-id")

        filter_obj = CorrelationLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = filter_obj.filter(record)

        assert result is True  # Filter always returns True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "filter-test-id"

    def test_filter_returns_none_when_no_id(self):
        """Test filter returns None when no ID set."""
        clear_correlation_id()

        filter_obj = CorrelationLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        filter_obj.filter(record)
        # When cleared, correlation_id is None
        assert record.correlation_id is None


class TestCorrelationLogFormatter:
    """Tests for CorrelationLogFormatter."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_formatter_includes_correlation_id(self):
        """Test formatter includes correlation ID in output."""
        set_correlation_id("formatter-test-id")

        formatter = CorrelationLogFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        assert "formatter-test-id" in output
        assert "[INFO]" in output
        assert "Test message" in output

    def test_formatter_without_module(self):
        """Test formatter without module."""
        set_correlation_id("no-module-id")

        formatter = CorrelationLogFormatter(include_module=False)
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        assert "no-module-id" in output
        assert "[WARNING]" in output

    def test_formatter_custom_format(self):
        """Test formatter with custom format."""
        set_correlation_id("custom-format-id")

        formatter = CorrelationLogFormatter(
            fmt="%(correlation_id)s - %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Custom format test",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        assert output == "custom-format-id - Custom format test"

    def test_formatter_adds_missing_correlation_id(self):
        """Test formatter adds correlation_id if missing from record."""
        set_correlation_id("added-id")

        formatter = CorrelationLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Message",
            args=(),
            exc_info=None
        )

        # Explicitly remove correlation_id if it exists
        if hasattr(record, 'correlation_id'):
            delattr(record, 'correlation_id')

        output = formatter.format(record)

        assert "added-id" in output


class TestThreadSafety:
    """Tests for thread safety of correlation ID."""

    def test_different_threads_have_different_ids(self):
        """Test different threads can have different IDs."""
        results = {}

        def thread_func(thread_id):
            with correlation_context(f"thread-{thread_id}"):
                import time
                time.sleep(0.01)  # Small delay to interleave threads
                results[thread_id] = get_correlation_id()

        threads = [
            threading.Thread(target=thread_func, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have captured its own ID
        for i in range(5):
            assert results[i] == f"thread-{i}"

    def test_thread_isolation(self):
        """Test thread-local storage isolates IDs."""
        main_id = None
        thread_id = None

        def thread_func():
            nonlocal thread_id
            set_correlation_id("thread-specific-id")
            thread_id = get_correlation_id()

        set_correlation_id("main-thread-id")
        main_id = get_correlation_id()

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        # Thread should not affect main thread's ID
        assert get_correlation_id() == "main-thread-id"
        assert thread_id == "thread-specific-id"
