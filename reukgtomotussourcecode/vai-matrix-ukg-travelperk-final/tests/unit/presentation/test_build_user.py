"""Tests for build user CLI."""

import json
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.presentation.cli.build_user import main


class TestMain:
    """Test cases for build_user main function."""

    @pytest.fixture
    def mock_ukg_client(self):
        """Create mock UKG client."""
        with patch("src.presentation.cli.build_user.UKGClient") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_builder_service(self):
        """Create mock builder service."""
        with patch("src.presentation.cli.build_user.UserBuilderService") as mock_class:
            mock_instance = MagicMock()
            mock_user = MagicMock()
            mock_user.to_api_payload.return_value = {
                "externalId": "12345",
                "userName": "john@example.com",
                "name": {"givenName": "John", "familyName": "Doe"},
            }
            mock_instance.build_user.return_value = mock_user
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_main_success(self, mock_ukg_client, mock_builder_service, tmp_path, monkeypatch):
        """Test main function executes successfully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        with patch.object(sys, "argv", ["build_user.py", "12345", "J9A6Y"]):
            main()

        mock_builder_service.build_user.assert_called_once_with("12345", "J9A6Y")

        # Check file was created
        output_file = tmp_path / "data" / "travelperk_user_12345.json"
        assert output_file.exists()

    def test_main_missing_arguments(self, mock_ukg_client, mock_builder_service):
        """Test main fails without required arguments."""
        with patch.object(sys, "argv", ["build_user.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_main_missing_company_id(self, mock_ukg_client, mock_builder_service):
        """Test main fails without company ID."""
        with patch.object(sys, "argv", ["build_user.py", "12345"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_main_with_debug(self, mock_builder_service, tmp_path, monkeypatch):
        """Test main with debug enabled."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        monkeypatch.setenv("DEBUG", "1")

        with patch("src.presentation.cli.build_user.UKGClient") as mock_ukg:
            mock_ukg.return_value = MagicMock()

            with patch.object(sys, "argv", ["build_user.py", "12345", "J9A6Y"]):
                main()

            mock_ukg.assert_called_once_with(debug=True)

    def test_main_creates_data_directory(self, mock_ukg_client, mock_builder_service, tmp_path, monkeypatch):
        """Test main creates data directory if missing."""
        monkeypatch.chdir(tmp_path)

        with patch.object(sys, "argv", ["build_user.py", "12345", "J9A6Y"]):
            main()

        assert (tmp_path / "data").exists()

    def test_main_outputs_path(self, mock_ukg_client, mock_builder_service, tmp_path, monkeypatch, capsys):
        """Test main outputs file path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        with patch.object(sys, "argv", ["build_user.py", "12345", "J9A6Y"]):
            main()

        captured = capsys.readouterr()
        assert "travelperk_user_12345.json" in captured.out

    def test_main_writes_valid_json(self, mock_ukg_client, mock_builder_service, tmp_path, monkeypatch):
        """Test main writes valid JSON to file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        with patch.object(sys, "argv", ["build_user.py", "12345", "J9A6Y"]):
            main()

        output_file = tmp_path / "data" / "travelperk_user_12345.json"
        with output_file.open() as f:
            data = json.load(f)

        assert data["externalId"] == "12345"
        assert data["userName"] == "john@example.com"
