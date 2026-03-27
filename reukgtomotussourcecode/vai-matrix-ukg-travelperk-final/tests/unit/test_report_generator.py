"""
Unit tests for report_generator module.
Tests for SOW Requirements 4.7, 7.3, 10.4 - Report generation.
"""
import os
import sys
import json
import pytest
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.report_generator import ReportGenerator


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    def test_init_creates_output_dir(self, tmp_path):
        """Test initialization creates output directory."""
        output_dir = tmp_path / "reports"
        generator = ReportGenerator(output_dir=str(output_dir))

        assert output_dir.exists()
        assert generator.output_dir == output_dir

    def test_generate_run_report_json(self, tmp_path):
        """Test JSON report generation."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "bill",
            "run_id": "run-123",
            "correlation_id": "corr-456",
            "company_id": "COMP001",
            "start_time": "2024-01-01T10:00:00",
            "end_time": "2024-01-01T10:05:00",
            "duration_seconds": 300,
            "stats": {
                "total_processed": 100,
                "created": 50,
                "updated": 45,
                "skipped": 3,
                "errors": 2
            },
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["json"])

        assert "json" in outputs
        json_path = Path(outputs["json"])
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert data["project"] == "bill"
        assert data["run_id"] == "run-123"

    def test_generate_run_report_html(self, tmp_path):
        """Test HTML report generation."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "motus",
            "run_id": "run-456",
            "correlation_id": "corr-789",
            "stats": {
                "total_processed": 50,
                "created": 25,
                "updated": 20,
                "skipped": 3,
                "errors": 2
            },
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["html"])

        assert "html" in outputs
        html_path = Path(outputs["html"])
        assert html_path.exists()

        content = html_path.read_text()
        assert "MOTUS" in content
        assert "run-456" in content
        assert "corr-789" in content

    def test_generate_run_report_markdown(self, tmp_path):
        """Test Markdown report generation."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "travelperk",
            "run_id": "run-789",
            "correlation_id": "corr-012",
            "stats": {
                "total_processed": 200,
                "created": 100,
                "updated": 90,
                "skipped": 5,
                "errors": 5
            },
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["md"])

        assert "md" in outputs
        md_path = Path(outputs["md"])
        assert md_path.exists()

        content = md_path.read_text()
        assert "TRAVELPERK" in content
        assert "run-789" in content
        assert "| Total Processed |" in content

    def test_generate_run_report_all_formats(self, tmp_path):
        """Test generating all formats at once."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "test",
            "run_id": "run-all",
            "stats": {"total_processed": 10, "errors": 0},
            "errors": []
        }

        outputs = generator.generate_run_report(run_context)

        assert "json" in outputs
        assert "html" in outputs
        assert "md" in outputs
        assert all(Path(p).exists() for p in outputs.values())

    def test_generate_run_report_with_errors(self, tmp_path):
        """Test report generation includes errors."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "bill",
            "run_id": "run-err",
            "stats": {"total_processed": 10, "errors": 2},
            "errors": [
                {"identifier": "EMP001", "error": "Invalid email", "timestamp": "2024-01-01T10:01:00"},
                {"identifier": "EMP002", "error": "Missing name", "timestamp": "2024-01-01T10:02:00"}
            ]
        }

        outputs = generator.generate_run_report(run_context, formats=["html", "md"])

        html_content = Path(outputs["html"]).read_text()
        md_content = Path(outputs["md"]).read_text()

        assert "EMP001" in html_content
        assert "Invalid email" in html_content
        assert "EMP001" in md_content

    def test_calculate_success_rate_zero_total(self, tmp_path):
        """Test success rate with zero total."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        rate = generator._calculate_success_rate({"total_processed": 0, "errors": 0})
        assert rate == 100.0

    def test_calculate_success_rate_with_errors(self, tmp_path):
        """Test success rate calculation."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        rate = generator._calculate_success_rate({"total_processed": 100, "errors": 5})
        assert rate == 95.0

    def test_calculate_success_rate_all_errors(self, tmp_path):
        """Test success rate with all errors."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        rate = generator._calculate_success_rate({"total_processed": 10, "errors": 10})
        assert rate == 0.0


class TestValidationReport:
    """Tests for validation report generation."""

    def test_generate_validation_report_passing(self, tmp_path):
        """Test validation report for passing run."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "bill",
            "run_id": "val-pass",
            "stats": {"total_processed": 1000, "errors": 5},
            "errors": [],
            "duration_seconds": 120
        }

        result = generator.generate_validation_report(run_context, target_success_rate=99.0)

        assert result["passed"] is True
        assert result["success_rate"] == 99.5
        assert "json" in result
        assert "md" in result

        json_path = Path(result["json"])
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert data["passed"] is True
        assert data["target_success_rate"] == 99.0
        assert data["actual_success_rate"] == 99.5

    def test_generate_validation_report_failing(self, tmp_path):
        """Test validation report for failing run."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "motus",
            "run_id": "val-fail",
            "stats": {"total_processed": 100, "errors": 10},
            "errors": []
        }

        result = generator.generate_validation_report(run_context, target_success_rate=95.0)

        assert result["passed"] is False
        assert result["success_rate"] == 90.0

    def test_validation_report_includes_criteria(self, tmp_path):
        """Test validation report includes all criteria."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "travelperk",
            "run_id": "val-criteria",
            "stats": {"total_processed": 50, "errors": 0},
            "errors": []
        }

        result = generator.generate_validation_report(run_context)

        json_path = Path(result["json"])
        with open(json_path) as f:
            data = json.load(f)

        criteria = data["criteria_results"]
        assert "success_rate_met" in criteria
        assert "no_duplicate_creations" in criteria
        assert "errors_reported_with_detail" in criteria

    def test_validation_markdown_content(self, tmp_path):
        """Test validation markdown has proper content."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "bill",
            "run_id": "val-md",
            "stats": {"total_processed": 100, "created": 50, "updated": 48, "skipped": 0, "errors": 2},
            "errors": [],
            "duration_seconds": 60
        }

        result = generator.generate_validation_report(run_context, target_success_rate=98.0)

        md_path = Path(result["md"])
        content = md_path.read_text()

        assert "SOW Validation Report" in content
        assert "BILL" in content
        assert ">= 98.0%" in content
        assert "98.0%" in content  # Actual rate


class TestErrorReport:
    """Tests for error report generation."""

    def test_generate_error_template(self, tmp_path):
        """Test error template generation."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        errors = [
            {"identifier": "EMP001", "error": "Invalid email format"},
            {"identifier": "EMP002", "error": "Missing required field: lastName"},
            {"identifier": "EMP003", "error": "Invalid email format"},
            {"identifier": "EMP004", "error": "Invalid state code"},
        ]

        path = generator.generate_error_template("bill", errors)

        assert Path(path).exists()

        with open(path) as f:
            data = json.load(f)

        assert data["report_type"] == "error_report"
        assert data["project"] == "bill"
        assert data["total_errors"] == 4
        assert "Invalid email format" in data["errors_by_type"]
        assert data["errors_by_type"]["Invalid email format"] == 2

    def test_generate_error_template_limits_errors(self, tmp_path):
        """Test error template limits to 100 errors."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        errors = [
            {"identifier": f"EMP{i:03d}", "error": f"Error {i}"}
            for i in range(150)
        ]

        path = generator.generate_error_template("motus", errors)

        with open(path) as f:
            data = json.load(f)

        assert data["total_errors"] == 150
        assert len(data["errors"]) == 100  # Limited to first 100

    def test_generate_error_template_groups_by_type(self, tmp_path):
        """Test error template groups errors by type."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        errors = [
            {"identifier": "E1", "error": "Type A error"},
            {"identifier": "E2", "error": "Type A error"},
            {"identifier": "E3", "error": "Type B error"},
            {"identifier": "E4", "error": "Type C error"},
            {"identifier": "E5", "error": "Type C error"},
            {"identifier": "E6", "error": "Type C error"},
        ]

        path = generator.generate_error_template("test", errors)

        with open(path) as f:
            data = json.load(f)

        assert data["errors_by_type"]["Type A error"] == 2
        assert data["errors_by_type"]["Type B error"] == 1
        assert data["errors_by_type"]["Type C error"] == 3


class TestHTMLReportContent:
    """Tests for HTML report content details."""

    def test_html_success_color_green(self, tmp_path):
        """Test HTML uses green for high success rate."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "test",
            "run_id": "run-green",
            "stats": {"total_processed": 100, "errors": 0},
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["html"])
        content = Path(outputs["html"]).read_text()

        assert "#28a745" in content  # Green color

    def test_html_warning_color_yellow(self, tmp_path):
        """Test HTML uses yellow for medium success rate."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "test",
            "run_id": "run-yellow",
            "stats": {"total_processed": 100, "errors": 5},
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["html"])
        content = Path(outputs["html"]).read_text()

        assert "#ffc107" in content  # Yellow color

    def test_html_error_color_red(self, tmp_path):
        """Test HTML uses red for low success rate."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "test",
            "run_id": "run-red",
            "stats": {"total_processed": 100, "errors": 20},
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["html"])
        content = Path(outputs["html"]).read_text()

        assert "#dc3545" in content  # Red color

    def test_html_limits_errors_to_50(self, tmp_path):
        """Test HTML report limits errors to 50."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        errors = [
            {"identifier": f"EMP{i:03d}", "error": f"Error {i}", "timestamp": "2024-01-01"}
            for i in range(75)
        ]

        run_context = {
            "project": "test",
            "run_id": "run-many-errors",
            "stats": {"total_processed": 100, "errors": 75},
            "errors": errors
        }

        outputs = generator.generate_run_report(run_context, formats=["html"])
        content = Path(outputs["html"]).read_text()

        # Should show first 50 errors
        assert "EMP049" in content
        assert "EMP074" not in content
        assert "75 total" in content


class TestMarkdownReportContent:
    """Tests for Markdown report content details."""

    def test_markdown_table_format(self, tmp_path):
        """Test Markdown has proper table format."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        run_context = {
            "project": "bill",
            "run_id": "run-table",
            "stats": {"total_processed": 100, "created": 50, "updated": 45, "skipped": 3, "errors": 2},
            "errors": []
        }

        outputs = generator.generate_run_report(run_context, formats=["md"])
        content = Path(outputs["md"]).read_text()

        # Check table structure
        assert "| Field | Value |" in content
        assert "|-------|-------|" in content
        assert "| Metric | Count |" in content

    def test_markdown_limits_errors_to_20(self, tmp_path):
        """Test Markdown limits errors to 20."""
        generator = ReportGenerator(output_dir=str(tmp_path))

        errors = [
            {"identifier": f"EMP{i:03d}", "error": f"Error {i}", "timestamp": "2024-01-01"}
            for i in range(30)
        ]

        run_context = {
            "project": "test",
            "run_id": "run-md-errors",
            "stats": {"total_processed": 100, "errors": 30},
            "errors": errors
        }

        outputs = generator.generate_run_report(run_context, formats=["md"])
        content = Path(outputs["md"]).read_text()

        # Should show first 20 errors
        assert "EMP019" in content
        assert "EMP029" not in content
        assert "30 total" in content
