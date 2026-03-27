"""
Unit tests for upsert-motus-driver.py module.
Tests payload validation, Motus API calls, and upsert logic.
"""
import os
import re
import sys
import json
import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_upserter_module(monkeypatch):
    """Helper to get fresh upserter module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upserter",
        str(Path(__file__).parent.parent.parent / "upsert-motus-driver.py")
    )
    upserter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upserter)
    return upserter


class TestLoadDotenvSimple:
    """Tests for load_dotenv_simple function."""

    def test_load_existing_env_file(self, monkeypatch, tmp_path):
        """Test loading existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\nANOTHER=123")

        upserter = get_upserter_module(monkeypatch)
        upserter.load_dotenv_simple(str(env_file))

        # setdefault only sets if not already set
        if "TEST_VAR" not in os.environ:
            assert os.environ.get("TEST_VAR") == "test_value"

    def test_load_nonexistent_file_does_nothing(self, monkeypatch, tmp_path):
        """Test loading nonexistent file doesn't crash."""
        upserter = get_upserter_module(monkeypatch)
        # Should not raise
        upserter.load_dotenv_simple(str(tmp_path / "nonexistent.env"))

    def test_skip_comments_and_empty_lines(self, monkeypatch, tmp_path):
        """Test comments and empty lines are skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nVALID=yes\n# another comment")

        upserter = get_upserter_module(monkeypatch)
        upserter.load_dotenv_simple(str(env_file))


class TestValidatePayload:
    """Tests for validate_payload function."""

    def test_valid_payload_passes(self, monkeypatch, sample_motus_driver_payload):
        """Test valid payload passes validation."""
        upserter = get_upserter_module(monkeypatch)

        # Should not raise
        upserter.validate_payload(sample_motus_driver_payload)

    def test_missing_client_employee_id_raises(self, monkeypatch, sample_motus_driver_payload):
        """Test missing clientEmployeeId1 raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_motus_driver_payload["clientEmployeeId1"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_motus_driver_payload)
        assert "clientEmployeeId1" in str(exc_info.value)

    def test_missing_program_id_raises(self, monkeypatch, sample_motus_driver_payload):
        """Test missing programId raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_motus_driver_payload["programId"] = None
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_motus_driver_payload)
        assert "programId" in str(exc_info.value)

    def test_missing_first_name_raises(self, monkeypatch, sample_motus_driver_payload):
        """Test missing firstName raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_motus_driver_payload["firstName"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_motus_driver_payload)
        assert "firstName" in str(exc_info.value)

    def test_missing_last_name_raises(self, monkeypatch, sample_motus_driver_payload):
        """Test missing lastName raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_motus_driver_payload["lastName"] = None
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_motus_driver_payload)
        assert "lastName" in str(exc_info.value)

    def test_missing_email_raises(self, monkeypatch, sample_motus_driver_payload):
        """Test missing email raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_motus_driver_payload["email"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_motus_driver_payload)
        assert "email" in str(exc_info.value)


class TestSafeJson:
    """Tests for safe_json function."""

    def test_safe_json_valid_response(self, monkeypatch):
        """Test safe_json parses valid JSON response."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}

        result = upserter.safe_json(mock_resp)
        assert result == {"status": "ok"}

    def test_safe_json_invalid_json_returns_text(self, monkeypatch):
        """Test safe_json returns text snippet on parse error."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_resp.text = "Not JSON content"

        result = upserter.safe_json(mock_resp)
        assert result == {"text": "Not JSON content"}


class TestBackoffSleep:
    """Tests for backoff_sleep function."""

    def test_backoff_sleep_exponential(self, monkeypatch):
        """Test backoff uses exponential delay."""
        upserter = get_upserter_module(monkeypatch)

        with patch("time.sleep") as mock_sleep:
            upserter.backoff_sleep(0)
            mock_sleep.assert_called_with(1)  # 2^0 = 1

            upserter.backoff_sleep(1)
            mock_sleep.assert_called_with(2)  # 2^1 = 2

            upserter.backoff_sleep(2)
            mock_sleep.assert_called_with(4)  # 2^2 = 4


class TestHeaders:
    """Tests for headers function."""

    def test_headers_contains_bearer_token(self, monkeypatch):
        """Test headers include Bearer token."""
        upserter = get_upserter_module(monkeypatch)

        h = upserter.headers()
        assert "Authorization" in h
        assert h["Authorization"].startswith("Bearer ")
        assert "Content-Type" in h
        assert h["Content-Type"] == "application/json"


class TestMotusApiCalls:
    """Tests for Motus API call functions."""

    @responses.activate
    def test_motus_get_driver(self, monkeypatch):
        """Test GET driver by client ID."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/drivers/12345.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        resp = upserter.motus_get_driver("12345")
        assert resp.status_code == 200
        assert resp.json()["clientEmployeeId1"] == "12345"

    @responses.activate
    def test_motus_post_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test POST new driver."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345", "id": "new-id"},
            status=201,
        )

        resp = upserter.motus_post_driver(sample_motus_driver_payload)
        assert resp.status_code == 201

    @responses.activate
    def test_motus_put_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test PUT update driver."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.PUT,
            re.compile(r".*/drivers/12345.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        resp = upserter.motus_put_driver("12345", sample_motus_driver_payload)
        assert resp.status_code == 200


class TestEnsureStartDate:
    """Tests for ensure_start_date_for_insert function."""

    def test_ensures_start_date_when_missing(self, monkeypatch):
        """Test start date is added when missing."""
        upserter = get_upserter_module(monkeypatch)

        payload = {"clientEmployeeId1": "12345"}
        upserter.ensure_start_date_for_insert(payload)

        assert "startDate" in payload
        assert payload["startDate"]  # Should be today's date

    def test_preserves_existing_start_date(self, monkeypatch):
        """Test existing start date is preserved."""
        upserter = get_upserter_module(monkeypatch)

        payload = {"clientEmployeeId1": "12345", "startDate": "2024-01-15"}
        upserter.ensure_start_date_for_insert(payload)

        assert payload["startDate"] == "2024-01-15"


class TestStripStartDate:
    """Tests for strip_start_date_for_update function."""

    def test_removes_start_date(self, monkeypatch):
        """Test start date is removed for updates."""
        upserter = get_upserter_module(monkeypatch)

        payload = {"clientEmployeeId1": "12345", "startDate": "2024-01-15"}
        upserter.strip_start_date_for_update(payload)

        assert "startDate" not in payload

    def test_handles_missing_start_date(self, monkeypatch):
        """Test handles payload without start date."""
        upserter = get_upserter_module(monkeypatch)

        payload = {"clientEmployeeId1": "12345"}
        # Should not raise
        upserter.strip_start_date_for_update(payload)


class TestUpsertDriverPayload:
    """Tests for upsert_driver_payload function."""

    @responses.activate
    def test_dry_run_mode(self, monkeypatch, sample_motus_driver_payload):
        """Test dry run mode validates without API calls."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.upsert_driver_payload(sample_motus_driver_payload, dry_run=True)

        assert result["dry_run"] is True
        assert result["action"] == "validate"
        assert len(responses.calls) == 0  # No API calls made

    @responses.activate
    def test_insert_new_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test inserting new driver."""
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # Insert succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_update_existing_driver(self, monkeypatch, sample_motus_driver_payload):
        """Test updating existing driver."""
        upserter = get_upserter_module(monkeypatch)

        # Driver exists
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PUT,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "update"
        assert result["status"] == 200

    @responses.activate
    def test_handles_payload_as_list(self, monkeypatch, sample_motus_driver_payload):
        """Test handles payload wrapped in list."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.upsert_driver_payload([sample_motus_driver_payload], dry_run=True)

        assert result["dry_run"] is True

    def test_empty_list_raises(self, monkeypatch):
        """Test empty list payload raises."""
        upserter = get_upserter_module(monkeypatch)

        with pytest.raises(SystemExit) as exc_info:
            upserter.upsert_driver_payload([])
        assert "Empty payload" in str(exc_info.value)

    @responses.activate
    def test_retry_on_5xx_error(self, monkeypatch, sample_motus_driver_payload):
        """Test retry on 5xx errors."""
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # First POST fails with 500
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"error": "Server error"},
            status=500,
        )
        # Second POST succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"clientEmployeeId1": "12345"},
            status=201,
        )

        with patch.object(upserter, "backoff_sleep"):
            result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201

    @responses.activate
    def test_insert_failed_handled_gracefully(self, monkeypatch, sample_motus_driver_payload):
        """Test insert failure is handled gracefully."""
        monkeypatch.setenv("MAX_RETRIES", "0")
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )
        # POST fails with 400
        responses.add(
            responses.POST,
            re.compile(r".*/drivers$"),
            json={"error": "Bad request"},
            status=400,
        )

        result = upserter.upsert_driver_payload(sample_motus_driver_payload)

        assert result["action"] == "insert_failed"
        assert result["status"] == 400


class TestUpsertProbeAction:
    """Tests for upsert_probe_action function."""

    @responses.activate
    def test_probe_would_insert(self, monkeypatch, sample_motus_driver_payload):
        """Test probe reports would_insert for new driver."""
        upserter = get_upserter_module(monkeypatch)

        # Driver doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"error": "Not found"},
            status=404,
        )

        result = upserter.upsert_probe_action(sample_motus_driver_payload)

        assert result["dry_run"] is True
        assert result["action"] == "would_insert"

    @responses.activate
    def test_probe_would_update(self, monkeypatch, sample_motus_driver_payload):
        """Test probe reports would_update for existing driver."""
        upserter = get_upserter_module(monkeypatch)

        # Driver exists
        responses.add(
            responses.GET,
            re.compile(r".*/drivers/.*"),
            json={"clientEmployeeId1": "12345"},
            status=200,
        )

        result = upserter.upsert_probe_action(sample_motus_driver_payload)

        assert result["dry_run"] is True
        assert result["action"] == "would_update"


class TestLoadDriverPayload:
    """Tests for load_driver_payload function."""

    def test_load_existing_file(self, monkeypatch, tmp_path, sample_motus_driver_payload):
        """Test loading existing driver payload file."""
        upserter = get_upserter_module(monkeypatch)

        # Create test file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        driver_file = data_dir / "motus_driver_12345.json"
        driver_file.write_text(json.dumps([sample_motus_driver_payload]))

        # Change to tmp_path so the function finds the file
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = upserter.load_driver_payload("12345")
            assert result["clientEmployeeId1"] == "12345"
        finally:
            os.chdir(original_cwd)

    def test_file_not_found_raises(self, monkeypatch, tmp_path):
        """Test missing file raises SystemExit."""
        upserter = get_upserter_module(monkeypatch)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                upserter.load_driver_payload("99999")
            assert "not found" in str(exc_info.value).lower()
        finally:
            os.chdir(original_cwd)
