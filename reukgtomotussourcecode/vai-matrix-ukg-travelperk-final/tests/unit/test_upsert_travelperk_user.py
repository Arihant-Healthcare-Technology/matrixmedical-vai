"""
Unit tests for upsert-travelperk-user.py module.
Tests SCIM payload validation, TravelPerk API calls, and upsert logic.
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
        str(Path(__file__).parent.parent.parent / "upsert-travelperk-user.py")
    )
    upserter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upserter)
    return upserter


class TestHeaders:
    """Tests for headers function."""

    def test_headers_contains_api_key(self, monkeypatch):
        """Test headers include ApiKey authorization."""
        upserter = get_upserter_module(monkeypatch)
        h = upserter.headers()
        assert "Authorization" in h
        assert h["Authorization"].startswith("ApiKey ")

    def test_headers_contains_content_type(self, monkeypatch):
        """Test headers include Content-Type."""
        upserter = get_upserter_module(monkeypatch)
        h = upserter.headers()
        assert h["Content-Type"] == "application/json"

    def test_missing_api_key_raises(self, monkeypatch):
        """Test raises SystemExit if API key missing."""
        monkeypatch.setenv("TRAVELPERK_API_KEY", "")

        upserter = get_upserter_module(monkeypatch)
        with pytest.raises(SystemExit) as exc_info:
            upserter.headers()
        assert "TRAVELPERK_API_KEY" in str(exc_info.value)


class TestSafeJson:
    """Tests for safe_json function."""

    def test_parses_valid_json(self, monkeypatch):
        """Test parses valid JSON response."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}

        result = upserter.safe_json(mock_resp)
        assert result == {"status": "ok"}

    def test_returns_text_on_parse_error(self, monkeypatch):
        """Test returns text snippet on JSON parse error."""
        upserter = get_upserter_module(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_resp.text = "Not JSON content"

        result = upserter.safe_json(mock_resp)
        assert result == {"text": "Not JSON content"}


class TestBackoffSleep:
    """Tests for backoff_sleep function."""

    def test_exponential_backoff(self, monkeypatch):
        """Test uses exponential backoff."""
        upserter = get_upserter_module(monkeypatch)

        with patch("time.sleep") as mock_sleep:
            upserter.backoff_sleep(0)
            mock_sleep.assert_called_with(1)  # 2^0 = 1

            upserter.backoff_sleep(1)
            mock_sleep.assert_called_with(2)  # 2^1 = 2

            upserter.backoff_sleep(2)
            mock_sleep.assert_called_with(4)  # 2^2 = 4


class TestValidatePayload:
    """Tests for validate_payload function."""

    def test_valid_payload_passes(self, monkeypatch, sample_travelperk_user_payload):
        """Test valid payload passes validation."""
        upserter = get_upserter_module(monkeypatch)

        # Should not raise
        upserter.validate_payload(sample_travelperk_user_payload)

    def test_missing_user_name_raises(self, monkeypatch, sample_travelperk_user_payload):
        """Test missing userName raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_travelperk_user_payload["userName"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_travelperk_user_payload)
        assert "userName" in str(exc_info.value)

    def test_missing_external_id_raises(self, monkeypatch, sample_travelperk_user_payload):
        """Test missing externalId raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_travelperk_user_payload["externalId"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_travelperk_user_payload)
        assert "externalId" in str(exc_info.value)

    def test_missing_name_raises(self, monkeypatch, sample_travelperk_user_payload):
        """Test missing name raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_travelperk_user_payload["name"] = None
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_travelperk_user_payload)
        assert "name" in str(exc_info.value)

    def test_missing_given_name_raises(self, monkeypatch, sample_travelperk_user_payload):
        """Test missing givenName raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_travelperk_user_payload["name"]["givenName"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_travelperk_user_payload)
        assert "givenName" in str(exc_info.value)

    def test_missing_family_name_raises(self, monkeypatch, sample_travelperk_user_payload):
        """Test missing familyName raises."""
        upserter = get_upserter_module(monkeypatch)

        sample_travelperk_user_payload["name"]["familyName"] = ""
        with pytest.raises(SystemExit) as exc_info:
            upserter.validate_payload(sample_travelperk_user_payload)
        assert "familyName" in str(exc_info.value)


class TestTravelperkApiCalls:
    """Tests for TravelPerk API call functions."""

    @responses.activate
    def test_get_user(self, monkeypatch, sample_travelperk_user_response):
        """Test GET user by ID."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json=sample_travelperk_user_response,
            status=200,
        )

        resp = upserter.travelperk_get_user("tp-user-123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "tp-user-123"

    @responses.activate
    def test_get_user_by_external_id(
        self, monkeypatch, sample_travelperk_scim_list_response
    ):
        """Test GET user by externalId."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )

        result = upserter.travelperk_get_user_by_external_id("12345")
        assert result["externalId"] == "12345"

    @responses.activate
    def test_get_user_by_external_id_not_found(self, monkeypatch):
        """Test GET user by externalId returns None if not found."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json={"Resources": []},
            status=200,
        )

        result = upserter.travelperk_get_user_by_external_id("99999")
        assert result is None

    @responses.activate
    def test_post_user(self, monkeypatch, sample_travelperk_user_payload):
        """Test POST new user."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"id": "new-user-id", "externalId": "12345"},
            status=201,
        )

        resp = upserter.travelperk_post_user(sample_travelperk_user_payload)
        assert resp.status_code == 201

    @responses.activate
    def test_put_user(self, monkeypatch, sample_travelperk_user_payload):
        """Test PUT update user."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.PUT,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        resp = upserter.travelperk_put_user("tp-user-123", sample_travelperk_user_payload)
        assert resp.status_code == 200

    @responses.activate
    def test_patch_user(self, monkeypatch):
        """Test PATCH update user."""
        upserter = get_upserter_module(monkeypatch)

        patch_payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}]
        }

        responses.add(
            responses.PATCH,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        resp = upserter.travelperk_patch_user("tp-user-123", patch_payload)
        assert resp.status_code == 200

    @responses.activate
    def test_get_user_by_user_name(
        self, monkeypatch, sample_travelperk_scim_list_response
    ):
        """Test GET user by userName (email)."""
        upserter = get_upserter_module(monkeypatch)

        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )

        result = upserter.travelperk_get_user_by_user_name("john.doe@example.com")
        assert result["userName"] == "john.doe@example.com"


class TestUpsertUserPayload:
    """Tests for upsert_user_payload function."""

    @responses.activate
    def test_dry_run_mode(self, monkeypatch, sample_travelperk_user_payload):
        """Test dry run mode validates without API calls."""
        upserter = get_upserter_module(monkeypatch)

        result = upserter.upsert_user_payload(sample_travelperk_user_payload, dry_run=True)

        assert result["dry_run"] is True
        assert result["action"] == "validate"
        assert len(responses.calls) == 0

    @responses.activate
    def test_insert_new_user(self, monkeypatch, sample_travelperk_user_payload):
        """Test inserting new user."""
        upserter = get_upserter_module(monkeypatch)

        # User doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json={"Resources": []},
            status=200,
        )
        # Insert succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"id": "new-user-id", "externalId": "12345"},
            status=201,
        )

        result = upserter.upsert_user_payload(sample_travelperk_user_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201
        assert result["id"] == "new-user-id"

    @responses.activate
    def test_update_existing_user(
        self, monkeypatch,
        sample_travelperk_user_payload,
        sample_travelperk_scim_list_response
    ):
        """Test updating existing user."""
        upserter = get_upserter_module(monkeypatch)

        # User exists
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PATCH,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        result = upserter.upsert_user_payload(sample_travelperk_user_payload)

        assert result["action"] == "update"
        assert result["status"] == 200
        assert result["id"] == "tp-user-123"

    @responses.activate
    def test_update_with_supervisor_id(
        self, monkeypatch,
        sample_travelperk_user_payload,
        sample_travelperk_scim_list_response
    ):
        """Test updating user with supervisor ID."""
        upserter = get_upserter_module(monkeypatch)

        # User exists
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Update succeeds
        responses.add(
            responses.PATCH,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        result = upserter.upsert_user_payload(
            sample_travelperk_user_payload,
            supervisor_id="supervisor-tp-id"
        )

        assert result["action"] == "update"

    @responses.activate
    def test_conflict_on_insert_finds_by_username(
        self, monkeypatch,
        sample_travelperk_user_payload,
        sample_travelperk_scim_list_response
    ):
        """Test handles 409 conflict by finding user by userName."""
        upserter = get_upserter_module(monkeypatch)

        # User doesn't exist by externalId
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*filter.*externalId.*"),
            json={"Resources": []},
            status=200,
        )
        # Insert fails with 409
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"error": "Conflict"},
            status=409,
        )
        # Find by userName succeeds
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*filter.*userName.*"),
            json=sample_travelperk_scim_list_response,
            status=200,
        )
        # Patch succeeds
        responses.add(
            responses.PATCH,
            re.compile(r".*/api/v2/scim/Users/tp-user-123.*"),
            json={"id": "tp-user-123"},
            status=200,
        )

        result = upserter.upsert_user_payload(sample_travelperk_user_payload)
        assert result["action"] == "update"

    @responses.activate
    def test_retry_on_5xx(self, monkeypatch, sample_travelperk_user_payload):
        """Test retries on 5xx errors."""
        upserter = get_upserter_module(monkeypatch)

        # User doesn't exist
        responses.add(
            responses.GET,
            re.compile(r".*/api/v2/scim/Users.*"),
            json={"Resources": []},
            status=200,
        )
        # First POST fails with 500
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"error": "Server error"},
            status=500,
        )
        # Second POST succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/api/v2/scim/Users$"),
            json={"id": "new-user-id", "externalId": "12345"},
            status=201,
        )

        with patch.object(upserter, "backoff_sleep"):
            result = upserter.upsert_user_payload(sample_travelperk_user_payload)

        assert result["action"] == "insert"
        assert result["status"] == 201


class TestSupervisorFunctions:
    """Tests for supervisor hierarchy functions."""

    def test_build_supervisor_mapping(self, monkeypatch, sample_supervisor_details):
        """Test builds supervisor mapping."""
        upserter = get_upserter_module(monkeypatch)

        mapping = upserter.build_supervisor_mapping(sample_supervisor_details)

        assert mapping["12345"] == "54321"
        assert mapping["54321"] is None
        assert mapping["67890"] == "54321"

    def test_get_users_without_supervisor(self, monkeypatch, sample_supervisor_details):
        """Test gets users without supervisor."""
        upserter = get_upserter_module(monkeypatch)

        mapping = upserter.build_supervisor_mapping(sample_supervisor_details)
        users = upserter.get_users_without_supervisor(mapping)

        assert "54321" in users
        assert "12345" not in users
        assert "67890" not in users

    def test_get_users_with_supervisor(self, monkeypatch, sample_supervisor_details):
        """Test gets users with supervisor."""
        upserter = get_upserter_module(monkeypatch)

        mapping = upserter.build_supervisor_mapping(sample_supervisor_details)
        users = upserter.get_users_with_supervisor(mapping)

        assert "12345" in users
        assert "67890" in users
        assert "54321" not in users


class TestLoadUserPayload:
    """Tests for load_user_payload function."""

    def test_loads_existing_file(self, monkeypatch, tmp_path, sample_travelperk_user_payload):
        """Test loads existing user payload file."""
        upserter = get_upserter_module(monkeypatch)

        # Create test file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        user_file = data_dir / "travelperk_user_12345.json"
        user_file.write_text(json.dumps(sample_travelperk_user_payload))

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = upserter.load_user_payload("12345")
            assert result["externalId"] == "12345"
        finally:
            os.chdir(original_cwd)

    def test_file_not_found_raises(self, monkeypatch, tmp_path):
        """Test missing file raises SystemExit."""
        upserter = get_upserter_module(monkeypatch)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                upserter.load_user_payload("99999")
            assert "not found" in str(exc_info.value).lower()
        finally:
            os.chdir(original_cwd)

    def test_handles_list_payload(self, monkeypatch, tmp_path, sample_travelperk_user_payload):
        """Test handles payload wrapped in list."""
        upserter = get_upserter_module(monkeypatch)

        # Create test file with list
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        user_file = data_dir / "travelperk_user_12345.json"
        user_file.write_text(json.dumps([sample_travelperk_user_payload]))

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = upserter.load_user_payload("12345")
            assert result["externalId"] == "12345"
        finally:
            os.chdir(original_cwd)
