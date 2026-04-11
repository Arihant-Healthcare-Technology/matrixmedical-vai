"""
Unit tests for src/presentation/cli/utils.py.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.presentation.cli.utils import (
    load_json_file,
    load_json_list,
    handle_cli_error,
    print_preview,
    print_sync_result,
    print_step_header,
    print_summary,
    format_currency,
)


class TestLoadJsonFile:
    """Tests for load_json_file function."""

    def test_loads_valid_json(self, tmp_path):
        """Test loading valid JSON file."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"key": "value"}')

        result = load_json_file(file_path)

        assert result == {"key": "value"}

    def test_raises_file_not_found(self):
        """Test raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_json_file("/nonexistent/path.json")

    def test_raises_json_decode_error(self, tmp_path):
        """Test raises JSONDecodeError for invalid JSON."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            load_json_file(file_path)

    def test_accepts_string_path(self, tmp_path):
        """Test accepts string path."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"key": "value"}')

        result = load_json_file(str(file_path))

        assert result == {"key": "value"}


class TestLoadJsonList:
    """Tests for load_json_list function."""

    def test_loads_array_json(self, tmp_path):
        """Test loading JSON array."""
        file_path = tmp_path / "test.json"
        file_path.write_text('[{"id": 1}, {"id": 2}]')

        result = load_json_list(file_path)

        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_loads_object_with_key(self, tmp_path):
        """Test loading object with specified key."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"employees": [{"id": 1}]}')

        result = load_json_list(file_path, key="employees")

        assert len(result) == 1

    def test_loads_object_with_common_key_items(self, tmp_path):
        """Test auto-detects 'items' key."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"items": [{"id": 1}]}')

        result = load_json_list(file_path)

        assert len(result) == 1

    def test_loads_object_with_common_key_data(self, tmp_path):
        """Test auto-detects 'data' key."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"data": [{"id": 1}]}')

        result = load_json_list(file_path)

        assert len(result) == 1

    def test_returns_empty_list_no_match(self, tmp_path):
        """Test returns empty list when no matching key."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"other": "value"}')

        result = load_json_list(file_path)

        assert result == []


class TestHandleCliError:
    """Tests for handle_cli_error decorator."""

    def test_returns_function_result_on_success(self):
        """Test returns function result on success."""

        @handle_cli_error
        def success_func():
            return 0

        assert success_func() == 0

    def test_returns_one_on_file_not_found(self):
        """Test returns 1 on FileNotFoundError."""

        @handle_cli_error
        def error_func():
            raise FileNotFoundError("missing")

        assert error_func() == 1

    def test_returns_one_on_json_decode_error(self):
        """Test returns 1 on JSONDecodeError."""

        @handle_cli_error
        def error_func():
            raise json.JSONDecodeError("error", "doc", 0)

        assert error_func() == 1

    def test_returns_one_on_permission_error(self):
        """Test returns 1 on PermissionError."""

        @handle_cli_error
        def error_func():
            raise PermissionError("denied")

        assert error_func() == 1

    def test_returns_one_on_generic_exception(self):
        """Test returns 1 on generic Exception."""

        @handle_cli_error
        def error_func():
            raise Exception("something wrong")

        assert error_func() == 1

    def test_returns_130_on_keyboard_interrupt(self):
        """Test returns 130 on KeyboardInterrupt."""

        @handle_cli_error
        def interrupt_func():
            raise KeyboardInterrupt()

        assert interrupt_func() == 130


class TestPrintPreview:
    """Tests for print_preview function."""

    def test_prints_items(self, capsys):
        """Test prints items."""
        items = [{"name": "item1"}, {"name": "item2"}]
        print_preview(items, "test items")

        captured = capsys.readouterr()
        assert "test items" in captured.out
        assert "item1" in captured.out or "showing 2" in captured.out

    def test_prints_max_items(self, capsys):
        """Test respects max_items limit."""
        items = [{"name": f"item{i}"} for i in range(20)]
        print_preview(items, "test items", max_items=5)

        captured = capsys.readouterr()
        assert "showing 5 of 20" in captured.out
        assert "15 more" in captured.out

    def test_uses_custom_formatter(self, capsys):
        """Test uses custom formatter."""
        items = [1, 2, 3]
        print_preview(items, "numbers", formatter=lambda x: f"Number: {x}")

        captured = capsys.readouterr()
        assert "Number: 1" in captured.out

    def test_formats_invoice_like_object(self, capsys):
        """Test formats invoice-like objects."""

        class MockInvoice:
            invoice_number = "INV-001"
            total_amount = 100.00

        print_preview([MockInvoice()], "invoices")

        captured = capsys.readouterr()
        assert "INV-001" in captured.out

    def test_formats_employee_like_object(self, capsys):
        """Test formats employee-like objects."""

        class MockEmployee:
            email = "test@example.com"
            full_name = "Test User"

        print_preview([MockEmployee()], "employees")

        captured = capsys.readouterr()
        assert "test@example.com" in captured.out

    def test_formats_vendor_like_object(self, capsys):
        """Test formats vendor-like objects."""

        class MockVendor:
            name = "Acme Corp"
            email = "billing@acme.com"

        print_preview([MockVendor()], "vendors")

        captured = capsys.readouterr()
        assert "Acme Corp" in captured.out


class TestPrintSyncResult:
    """Tests for print_sync_result function."""

    def test_prints_result_stats(self, capsys):
        """Test prints result statistics."""
        mock_result = MagicMock()
        mock_result.total = 10
        mock_result.created = 5
        mock_result.updated = 3
        mock_result.skipped = 2
        mock_result.errors = 0
        mock_result.success_rate = 100.0
        mock_result.duration = 5.5
        mock_result.correlation_id = "test-123"
        mock_result.results = []

        print_sync_result(mock_result, "TEST SYNC")

        captured = capsys.readouterr()
        assert "TEST SYNC" in captured.out
        assert "10" in captured.out
        assert "100.0%" in captured.out

    def test_prints_errors(self, capsys):
        """Test prints errors when present."""

        class MockError:
            action = "error"
            entity_id = "entity-1"
            message = "Something failed"

        class MockResult:
            total = 10
            created = 9
            updated = 0
            skipped = 0
            errors = 1
            success_rate = 90.0
            duration = 1.5
            correlation_id = "test-123"
            results = [MockError()]

        print_sync_result(MockResult())

        captured = capsys.readouterr()
        assert "Errors:" in captured.out
        assert "entity-1" in captured.out
        assert "Something failed" in captured.out

    def test_limits_errors_shown(self, capsys):
        """Test limits number of errors shown."""

        class MockError:
            action = "error"
            entity_id = "entity"
            message = "Error"

        class MockResult:
            total = 20
            created = 0
            updated = 0
            skipped = 0
            errors = 20
            success_rate = 0.0
            duration = 2.0
            correlation_id = "test"
            results = [MockError() for _ in range(20)]

        print_sync_result(MockResult(), max_errors=5)

        captured = capsys.readouterr()
        assert "15 more errors" in captured.out

    def test_handles_missing_duration(self, capsys):
        """Test handles missing duration attribute."""
        mock_result = MagicMock()
        mock_result.total = 10
        mock_result.created = 10
        mock_result.updated = 0
        mock_result.skipped = 0
        mock_result.errors = 0
        mock_result.success_rate = 100.0
        mock_result.correlation_id = "test"
        mock_result.results = []
        del mock_result.duration  # Remove duration

        print_sync_result(mock_result)

        captured = capsys.readouterr()
        assert "Duration" not in captured.out


class TestPrintStepHeader:
    """Tests for print_step_header function."""

    def test_prints_header(self, capsys):
        """Test prints step header."""
        print_step_header(1, "Vendor Sync")

        captured = capsys.readouterr()
        assert "Step 1: Vendor Sync" in captured.out
        assert "=" in captured.out


class TestPrintSummary:
    """Tests for print_summary function."""

    def test_prints_summary(self, capsys):
        """Test prints batch summary."""
        results = [
            ("Vendors", 0),
            ("Invoices", 0),
            ("Payments", 1),
        ]
        print_summary(results, "BATCH SUMMARY")

        captured = capsys.readouterr()
        assert "BATCH SUMMARY" in captured.out
        assert "Vendors: SUCCESS" in captured.out
        assert "Invoices: SUCCESS" in captured.out
        assert "Payments: FAILED" in captured.out


class TestFormatCurrency:
    """Tests for format_currency function."""

    def test_formats_positive_amount(self):
        """Test formats positive amount."""
        assert format_currency(1234.56) == "$1,234.56"

    def test_formats_zero(self):
        """Test formats zero."""
        assert format_currency(0) == "$0.00"

    def test_formats_large_amount(self):
        """Test formats large amounts with commas."""
        assert format_currency(1234567.89) == "$1,234,567.89"

    def test_formats_small_decimal(self):
        """Test formats small decimal amounts."""
        assert format_currency(0.99) == "$0.99"
