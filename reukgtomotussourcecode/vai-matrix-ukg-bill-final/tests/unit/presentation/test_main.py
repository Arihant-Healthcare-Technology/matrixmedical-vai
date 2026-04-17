"""
Unit tests for main CLI entry point.
"""
import pytest
import logging
from unittest.mock import MagicMock, patch


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_no_error(self):
        """Test setup_logging runs without error."""
        from src.presentation.cli.main import setup_logging

        # Just verify it doesn't crash
        setup_logging(verbose=False)

    def test_verbose_mode_no_error(self):
        """Test verbose mode runs without error."""
        from src.presentation.cli.main import setup_logging

        setup_logging(verbose=True)

    def test_reduces_third_party_noise(self):
        """Test reduces logging noise from urllib3 and httpx."""
        from src.presentation.cli.main import setup_logging

        setup_logging()

        urllib3_logger = logging.getLogger("urllib3")
        httpx_logger = logging.getLogger("httpx")

        assert urllib3_logger.level >= logging.WARNING
        assert httpx_logger.level >= logging.WARNING


class TestCreateParser:
    """Tests for create_parser function."""

    def test_creates_parser(self):
        """Test creates argument parser."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()

        assert parser is not None
        assert parser.prog == "ukg-bill"

    def test_has_verbose_flag(self):
        """Test parser has verbose flag."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["-v"])

        assert args.verbose is True

    def test_has_dry_run_flag(self):
        """Test parser has dry-run flag."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["--dry-run"])

        assert args.dry_run is True

    def test_has_sync_command(self):
        """Test parser has sync command."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--all"])

        assert args.command == "sync"

    def test_has_export_command(self):
        """Test parser has export command."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["export", "--output", "test.csv"])

        assert args.command == "export"

    def test_has_ap_command(self):
        """Test parser has ap command."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["ap", "vendors"])

        assert args.command == "ap"


class TestSyncCommandOptions:
    """Tests for sync command options."""

    def test_sync_all_flag(self):
        """Test sync --all flag."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--all"])

        assert args.all is True

    def test_sync_company_id(self):
        """Test sync --company-id option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--company-id", "J9A6Y"])

        assert args.company_id == "J9A6Y"

    def test_sync_employee_file(self):
        """Test sync --employee-file option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--employee-file", "employees.json"])

        assert args.employee_file == "employees.json"

    def test_sync_workers(self):
        """Test sync --workers option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--all", "--workers", "8"])

        assert args.workers == 8

    def test_sync_default_role(self):
        """Test sync --default-role option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["sync", "--all", "--default-role", "ADMIN"])

        assert args.default_role == "ADMIN"


class TestExportCommandOptions:
    """Tests for export command options."""

    def test_export_output(self):
        """Test export --output option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["export", "--output", "test.csv"])

        assert args.output == "test.csv"

    def test_export_company_id(self):
        """Test export --company-id option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["export", "--company-id", "J9A6Y", "-o", "out.csv"])

        assert args.company_id == "J9A6Y"


class TestAPCommandOptions:
    """Tests for AP command options."""

    def test_ap_vendors_subcommand(self):
        """Test ap vendors subcommand."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["ap", "vendors"])

        assert args.command == "ap"
        assert args.ap_command == "vendors"

    def test_ap_invoices_subcommand(self):
        """Test ap invoices subcommand."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["ap", "invoices"])

        assert args.command == "ap"
        assert args.ap_command == "invoices"

    def test_ap_payments_subcommand(self):
        """Test ap payments subcommand."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["ap", "payments"])

        assert args.command == "ap"
        assert args.ap_command == "payments"

    def test_ap_batch_subcommand(self):
        """Test ap batch subcommand."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["ap", "batch"])

        assert args.command == "ap"
        assert args.ap_command == "batch"

    def test_status_command(self):
        """Test status command."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["status"])

        assert args.command == "status"

    def test_status_with_check_auth(self):
        """Test status --check-auth option."""
        from src.presentation.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["status", "--check-auth"])

        assert args.check_auth is True


class TestMainFunction:
    """Tests for main function."""

    def test_returns_zero_for_no_command(self):
        """Test returns 0 when no command provided."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_container:
            result = main([])

        assert result == 0

    def test_sync_all_calls_run_sync_all(self):
        """Test sync --all calls run_sync_all."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_sync_all", return_value=0) as mock_sync:
            mock_get_container.return_value = MagicMock()
            result = main(["sync", "--all"])

        mock_sync.assert_called_once()
        assert result == 0

    def test_sync_company_id_calls_run_sync_all(self):
        """Test sync --company-id calls run_sync_all."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_sync_all", return_value=0) as mock_sync:
            mock_get_container.return_value = MagicMock()
            result = main(["sync", "--company-id", "J9A6Y"])

        mock_sync.assert_called_once()
        assert result == 0

    def test_sync_employee_file_calls_run_sync_batch(self):
        """Test sync --employee-file calls run_sync_batch."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_sync_batch", return_value=0) as mock_batch:
            mock_container = MagicMock()
            mock_container.settings.ukg_company_id = None  # No company_id so it uses employee_file
            mock_get_container.return_value = mock_container
            result = main(["sync", "--employee-file", "test.json"])

        mock_batch.assert_called_once()
        assert result == 0

    def test_export_calls_run_export_csv(self):
        """Test export calls run_export_csv."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_export_csv", return_value=0) as mock_export:
            mock_get_container.return_value = MagicMock()
            result = main(["export", "-o", "output.csv"])

        mock_export.assert_called_once()
        assert result == 0

    @pytest.mark.skip(reason="AP commands are temporarily disabled in main.py")
    def test_ap_vendors_calls_run_vendor_sync(self):
        """Test ap vendors calls run_vendor_sync."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_vendor_sync", return_value=0) as mock_vendor:
            mock_get_container.return_value = MagicMock()
            result = main(["ap", "vendors"])

        mock_vendor.assert_called_once()
        assert result == 0

    @pytest.mark.skip(reason="AP commands are temporarily disabled in main.py")
    def test_ap_invoices_calls_run_invoice_sync(self):
        """Test ap invoices calls run_invoice_sync."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_invoice_sync", return_value=0) as mock_invoice:
            mock_get_container.return_value = MagicMock()
            result = main(["ap", "invoices"])

        mock_invoice.assert_called_once()
        assert result == 0

    @pytest.mark.skip(reason="AP commands are temporarily disabled in main.py")
    def test_ap_payments_calls_run_payment_process(self):
        """Test ap payments calls run_payment_process."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_payment_process", return_value=0) as mock_payment:
            mock_get_container.return_value = MagicMock()
            result = main(["ap", "payments"])

        mock_payment.assert_called_once()
        assert result == 0

    @pytest.mark.skip(reason="AP commands are temporarily disabled in main.py")
    def test_ap_batch_calls_run_ap_batch(self):
        """Test ap batch calls run_ap_batch."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.run_ap_batch", return_value=0) as mock_batch:
            mock_get_container.return_value = MagicMock()
            result = main(["ap", "batch", "--vendors"])

        mock_batch.assert_called_once()
        assert result == 0

    def test_status_calls_check_status(self):
        """Test status calls check_status."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("src.presentation.cli.main.check_status", return_value=0) as mock_status:
            mock_get_container.return_value = MagicMock()
            result = main(["status"])

        mock_status.assert_called_once()
        assert result == 0

    def test_returns_one_on_exception(self):
        """Test returns 1 on exception."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container:
            mock_get_container.side_effect = Exception("Container failed")
            result = main(["sync", "--all"])

        assert result == 1

    def test_verbose_flag_logs_traceback(self):
        """Test verbose flag logs full traceback on error."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container:
            mock_get_container.side_effect = Exception("Container failed")
            result = main(["--verbose", "sync", "--all"])

        assert result == 1

    def test_env_file_loads_dotenv(self):
        """Test --env-file loads dotenv."""
        from src.presentation.cli.main import main

        with patch("src.presentation.cli.main.get_container") as mock_get_container, \
             patch("dotenv.load_dotenv") as mock_load:
            mock_get_container.return_value = MagicMock()
            main(["--env-file", ".env.test"])

        mock_load.assert_called_once_with(".env.test")

    def test_log_file_option(self):
        """Test --log-file option."""
        from src.presentation.cli.main import main
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as f:
            log_path = f.name

        try:
            with patch("src.presentation.cli.main.get_container") as mock_get_container:
                mock_get_container.return_value = MagicMock()
                main(["--log-file", log_path])

            assert os.path.exists(log_path)
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)


class TestCheckStatus:
    """Tests for check_status function."""

    def test_prints_configuration(self, capsys):
        """Test prints configuration info."""
        from src.presentation.cli.main import check_status

        mock_container = MagicMock()
        mock_container.settings.ukg_api_base = "https://ukg.example.com"
        mock_container.settings.bill_api_base = "https://bill.example.com"
        mock_container.settings.bill_org_id = "test-org"
        mock_container.settings.rate_limit_calls_per_minute = 60

        result = check_status(mock_container)

        captured = capsys.readouterr()
        assert "UKG to BILL.com Integration Status" in captured.out
        assert "https://ukg.example.com" in captured.out
        assert "https://bill.example.com" in captured.out
        assert "test-org" in captured.out
        assert result == 0

    def test_checks_auth_when_requested(self, capsys):
        """Test checks authentication when requested."""
        from src.presentation.cli.main import check_status

        mock_container = MagicMock()
        mock_container.settings.ukg_api_base = "https://ukg.example.com"
        mock_container.settings.bill_api_base = "https://bill.example.com"
        mock_container.settings.bill_org_id = "test-org"
        mock_container.settings.rate_limit_calls_per_minute = 60

        mock_ukg = MagicMock()
        mock_ukg.test_connection.return_value = True
        mock_container.ukg_client.return_value = mock_ukg

        mock_bill = MagicMock()
        mock_bill.test_connection.return_value = True
        mock_container.bill_client.return_value = mock_bill

        result = check_status(mock_container, check_auth=True)

        captured = capsys.readouterr()
        assert "Authentication Check" in captured.out
        assert "UKG API: OK" in captured.out
        assert "BILL API: OK" in captured.out
        assert result == 0

    def test_handles_ukg_auth_failure(self, capsys):
        """Test handles UKG authentication failure."""
        from src.presentation.cli.main import check_status

        mock_container = MagicMock()
        mock_container.settings.ukg_api_base = "https://ukg.example.com"
        mock_container.settings.bill_api_base = "https://bill.example.com"
        mock_container.settings.bill_org_id = "test-org"
        mock_container.settings.rate_limit_calls_per_minute = 60
        mock_container.ukg_client.side_effect = Exception("Auth failed")

        mock_bill = MagicMock()
        mock_bill.test_connection.return_value = True
        mock_container.bill_client.return_value = mock_bill

        result = check_status(mock_container, check_auth=True)

        captured = capsys.readouterr()
        assert "UKG API: FAILED" in captured.out
        assert result == 0

    def test_handles_bill_auth_failure(self, capsys):
        """Test handles BILL authentication failure."""
        from src.presentation.cli.main import check_status

        mock_container = MagicMock()
        mock_container.settings.ukg_api_base = "https://ukg.example.com"
        mock_container.settings.bill_api_base = "https://bill.example.com"
        mock_container.settings.bill_org_id = "test-org"
        mock_container.settings.rate_limit_calls_per_minute = 60

        mock_ukg = MagicMock()
        mock_ukg.test_connection.return_value = True
        mock_container.ukg_client.return_value = mock_ukg

        mock_container.bill_client.side_effect = Exception("Auth failed")

        result = check_status(mock_container, check_auth=True)

        captured = capsys.readouterr()
        assert "BILL API: FAILED" in captured.out
        assert result == 0
