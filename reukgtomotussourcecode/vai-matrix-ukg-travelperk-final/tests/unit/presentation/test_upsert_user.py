"""Tests for upsert user CLI."""

import json
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.presentation.cli.upsert_user import (
    load_user_payload,
    payload_to_user,
    main,
)
from src.domain.models import TravelPerkUser


class TestLoadUserPayload:
    """Test cases for load_user_payload function."""

    def test_load_success(self, tmp_path, monkeypatch):
        """Test loading payload successfully."""
        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        payload = {"externalId": "12345", "userName": "john@example.com"}
        payload_file = data_dir / "travelperk_user_12345.json"
        with payload_file.open("w") as f:
            json.dump(payload, f)

        result = load_user_payload("12345")

        assert result["externalId"] == "12345"
        assert result["userName"] == "john@example.com"

    def test_load_file_not_found(self, tmp_path, monkeypatch):
        """Test error when file not found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        with pytest.raises(SystemExit) as exc_info:
            load_user_payload("99999")

        assert "not found" in str(exc_info.value)

    def test_load_list_returns_first(self, tmp_path, monkeypatch):
        """Test loading list payload returns first element."""
        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        payload = [{"externalId": "12345"}, {"externalId": "12346"}]
        payload_file = data_dir / "travelperk_user_12345.json"
        with payload_file.open("w") as f:
            json.dump(payload, f)

        result = load_user_payload("12345")

        assert result["externalId"] == "12345"

    def test_load_invalid_type_returns_empty(self, tmp_path, monkeypatch):
        """Test loading invalid type returns empty dict."""
        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        payload_file = data_dir / "travelperk_user_12345.json"
        with payload_file.open("w") as f:
            json.dump("invalid", f)

        result = load_user_payload("12345")

        assert result == {}


class TestPayloadToUser:
    """Test cases for payload_to_user function."""

    def test_convert_basic(self):
        """Test converting basic payload to user."""
        payload = {
            "externalId": "12345",
            "userName": "john@example.com",
            "name": {"givenName": "John", "familyName": "Doe"},
            "active": True,
        }

        user = payload_to_user(payload)

        assert user.external_id == "12345"
        assert user.user_name == "john@example.com"
        assert user.name.given_name == "John"
        assert user.name.family_name == "Doe"
        assert user.active is True

    def test_convert_with_enterprise_extension(self):
        """Test converting payload with enterprise extension."""
        payload = {
            "externalId": "12345",
            "userName": "john@example.com",
            "name": {"givenName": "John", "familyName": "Doe"},
            "active": True,
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "costCenter": "CC001",
            },
        }

        user = payload_to_user(payload)

        assert user.cost_center == "CC001"

    def test_convert_missing_name(self):
        """Test converting payload with missing name."""
        payload = {
            "externalId": "12345",
            "userName": "john@example.com",
            "active": True,
        }

        user = payload_to_user(payload)

        assert user.name.given_name == ""
        assert user.name.family_name == ""

    def test_convert_defaults(self):
        """Test converting payload uses defaults."""
        payload = {}

        user = payload_to_user(payload)

        assert user.external_id == ""
        assert user.user_name == ""
        assert user.active is True


class TestMain:
    """Test cases for main function."""

    @pytest.fixture
    def sample_payload(self):
        """Sample payload data."""
        return {
            "externalId": "12345",
            "userName": "john@example.com",
            "name": {"givenName": "John", "familyName": "Doe"},
            "active": True,
        }

    @pytest.fixture
    def setup_payload_file(self, tmp_path, sample_payload, monkeypatch):
        """Set up payload file."""
        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        payload_file = data_dir / "travelperk_user_12345.json"
        with payload_file.open("w") as f:
            json.dump(sample_payload, f)

        return tmp_path

    def test_main_missing_arguments(self):
        """Test main fails without required arguments."""
        with patch.object(sys, "argv", ["upsert_user.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_main_dry_run(self, setup_payload_file, capsys):
        """Test main in dry run mode."""
        with patch.object(sys, "argv", ["upsert_user.py", "12345", "--dry-run"]):
            main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["dry_run"] is True
        assert result["action"] == "validate"

    def test_main_success(self, setup_payload_file, capsys):
        """Test main executes successfully."""
        with patch("src.presentation.cli.upsert_user.TravelPerkClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.upsert_user.return_value = {
                "id": "tp-123",
                "action": "insert",
            }
            mock_client.return_value = mock_instance

            with patch.object(sys, "argv", ["upsert_user.py", "12345"]):
                main()

        mock_instance.upsert_user.assert_called_once()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["id"] == "tp-123"

    def test_main_validation_error(self, tmp_path, monkeypatch):
        """Test main fails on validation error."""
        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Create invalid payload (missing required fields)
        payload = {"externalId": "", "userName": ""}
        payload_file = data_dir / "travelperk_user_12345.json"
        with payload_file.open("w") as f:
            json.dump(payload, f)

        with patch.object(sys, "argv", ["upsert_user.py", "12345"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert "Validation failed" in str(exc_info.value)

    def test_main_with_debug(self, setup_payload_file):
        """Test main with debug enabled."""
        with patch("src.presentation.cli.upsert_user.TravelPerkClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.upsert_user.return_value = {"id": "tp-123"}
            mock_client.return_value = mock_instance

            with patch.dict(os.environ, {"DEBUG": "1"}):
                with patch.object(sys, "argv", ["upsert_user.py", "12345"]):
                    main()

            mock_client.assert_called_once_with(debug=True)

    def test_main_file_not_found(self, tmp_path, monkeypatch):
        """Test main fails when payload file not found."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        with patch.object(sys, "argv", ["upsert_user.py", "99999"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert "not found" in str(exc_info.value)
