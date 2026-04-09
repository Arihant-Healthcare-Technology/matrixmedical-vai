"""
Unit tests for motus-get-token.py module.
Tests token acquisition, caching, JWT parsing.
"""
import os
import re
import sys
import json
import pytest
import responses
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_token_module(monkeypatch):
    """Helper to get fresh token module with mocked env vars."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "token",
        str(Path(__file__).parent.parent.parent / "motus-get-token.py")
    )
    token = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(token)
    return token


class TestNowTs:
    """Tests for now_ts function."""

    def test_returns_current_timestamp(self, monkeypatch):
        """Test returns current Unix timestamp."""
        token = get_token_module(monkeypatch)

        result = token.now_ts()
        expected = int(datetime.now(tz=timezone.utc).timestamp())

        # Allow small difference for execution time
        assert abs(result - expected) < 2


class TestCacheManagement:
    """Tests for cache loading/saving."""

    def test_load_cache_nonexistent(self, monkeypatch, tmp_path):
        """Test loading nonexistent cache returns None."""
        token = get_token_module(monkeypatch)

        result = token.load_cache()
        # If no cache exists, should return None
        assert result is None or isinstance(result, dict)

    def test_save_and_load_cache(self, monkeypatch, tmp_path):
        """Test saving and loading cache."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        token = get_token_module(monkeypatch)

        # Manually save cache
        cache_data = {"access_token": "test", "expires_at": 9999999999}
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Update module's CACHE_PATH
        token.CACHE_PATH = str(cache_file)

        result = token.load_cache()
        assert result is not None
        assert result["access_token"] == "test"


class TestCachedOk:
    """Tests for cached_ok validation."""

    def test_valid_cache_returns_true(self, monkeypatch):
        """Test valid cache with future expiry returns True."""
        token = get_token_module(monkeypatch)

        # Expires far in the future
        cache = {
            "access_token": "valid-token",
            "expires_at": token.now_ts() + 3600  # 1 hour from now
        }

        result = token.cached_ok(cache)
        assert result is True

    def test_expired_cache_returns_false(self, monkeypatch):
        """Test expired cache returns False."""
        token = get_token_module(monkeypatch)

        # Already expired
        cache = {
            "access_token": "expired-token",
            "expires_at": token.now_ts() - 100
        }

        result = token.cached_ok(cache)
        assert result is False

    def test_missing_token_returns_false(self, monkeypatch):
        """Test cache without token returns False."""
        token = get_token_module(monkeypatch)

        cache = {"expires_at": token.now_ts() + 3600}

        result = token.cached_ok(cache)
        assert result is False

    def test_none_cache_returns_false(self, monkeypatch):
        """Test None cache returns False."""
        token = get_token_module(monkeypatch)

        result = token.cached_ok(None)
        assert result is False

    def test_empty_cache_returns_false(self, monkeypatch):
        """Test empty cache returns False."""
        token = get_token_module(monkeypatch)

        result = token.cached_ok({})
        assert result is False


class TestTokenHeaders:
    """Tests for token_headers function."""

    def test_contains_accept_header(self, monkeypatch):
        """Test headers include Accept header."""
        token = get_token_module(monkeypatch)

        h = token.token_headers()
        assert "Accept" in h


class TestB64UrlDecode:
    """Tests for b64url_decode_to_bytes function."""

    def test_decodes_base64url(self, monkeypatch):
        """Test base64url decoding."""
        token = get_token_module(monkeypatch)

        # "test" in base64url is "dGVzdA"
        result = token.b64url_decode_to_bytes("dGVzdA")
        assert result == b"test"

    def test_handles_padding(self, monkeypatch):
        """Test handles missing padding."""
        token = get_token_module(monkeypatch)

        # Base64url without padding
        result = token.b64url_decode_to_bytes("dGVzdA")
        assert result == b"test"


class TestInferExpFromJwt:
    """Tests for infer_exp_from_jwt function."""

    def test_extracts_exp_from_jwt(self, monkeypatch):
        """Test extracting exp claim from JWT."""
        token = get_token_module(monkeypatch)

        # Create a mock JWT with exp claim
        # Header: {"alg": "HS256", "typ": "JWT"}
        # Payload: {"exp": 1735689600}  # Some future timestamp
        import base64

        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({"exp": 1735689600}).encode()).decode().rstrip("=")
        sig = "signature"

        jwt = f"{header}.{payload}.{sig}"

        result = token.infer_exp_from_jwt(jwt)
        assert result == 1735689600

    def test_invalid_jwt_returns_none(self, monkeypatch):
        """Test invalid JWT returns None."""
        token = get_token_module(monkeypatch)

        result = token.infer_exp_from_jwt("not-a-jwt")
        assert result is None

    def test_jwt_without_exp_returns_none(self, monkeypatch):
        """Test JWT without exp claim returns None."""
        token = get_token_module(monkeypatch)

        import base64
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "user"}).encode()).decode().rstrip("=")
        sig = "sig"

        jwt = f"{header}.{payload}.{sig}"

        result = token.infer_exp_from_jwt(jwt)
        assert result is None


class TestNormalize:
    """Tests for normalize function."""

    def test_extracts_access_token(self, monkeypatch):
        """Test extracts access_token from response."""
        token = get_token_module(monkeypatch)

        raw = {"access_token": "my-token", "expires_in": 3600}
        result = token.normalize(raw)

        assert result["access_token"] == "my-token"
        assert result["token_type"] == "Bearer"

    def test_handles_token_key(self, monkeypatch):
        """Test handles 'token' key."""
        token = get_token_module(monkeypatch)

        raw = {"token": "my-token", "expiresIn": 3600}
        result = token.normalize(raw)

        assert result["access_token"] == "my-token"

    def test_handles_bearer_token_key(self, monkeypatch):
        """Test handles 'bearerToken' key."""
        token = get_token_module(monkeypatch)

        raw = {"bearerToken": "my-token"}
        result = token.normalize(raw)

        assert result["access_token"] == "my-token"

    def test_handles_raw_text(self, monkeypatch):
        """Test handles raw text token."""
        token = get_token_module(monkeypatch)

        raw = {"raw_text": "plain-text-token"}
        result = token.normalize(raw)

        assert result["access_token"] == "plain-text-token"

    def test_missing_token_raises(self, monkeypatch):
        """Test missing token raises SystemExit."""
        token = get_token_module(monkeypatch)

        raw = {"some_field": "value"}
        with pytest.raises(SystemExit) as exc_info:
            token.normalize(raw)
        assert "missing" in str(exc_info.value).lower()

    def test_uses_default_ttl_when_no_expires(self, monkeypatch):
        """Test uses default TTL when no expiration info."""
        token = get_token_module(monkeypatch)

        raw = {"access_token": "my-token"}  # No expires_in
        result = token.normalize(raw)

        # Should have expires_at set
        assert "expires_at" in result
        assert result["expires_at"] > token.now_ts()


class TestRequestToken:
    """Tests for request_token function."""

    @responses.activate
    def test_form_request_success(self, monkeypatch):
        """Test successful token request via form."""
        token = get_token_module(monkeypatch)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "new-token", "expires_in": 3600},
            status=200,
        )

        result = token.request_token()
        assert result["access_token"] == "new-token"

    @responses.activate
    def test_json_fallback(self, monkeypatch):
        """Test JSON fallback when form fails."""
        token = get_token_module(monkeypatch)

        # First form request fails
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"error": "Bad request"},
            status=400,
        )
        # JSON request succeeds
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "json-token"},
            status=200,
        )

        result = token.request_token()
        assert result["access_token"] == "json-token"

    @responses.activate
    def test_all_methods_fail_raises(self, monkeypatch):
        """Test all methods failing raises SystemExit."""
        token = get_token_module(monkeypatch)

        # Both methods fail
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"error": "Unauthorized"},
            status=401,
        )
        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"error": "Unauthorized"},
            status=401,
        )

        with pytest.raises(SystemExit) as exc_info:
            token.request_token()
        assert "failed" in str(exc_info.value).lower()


class TestGetToken:
    """Tests for get_token function."""

    @responses.activate
    def test_requests_new_token_when_cache_expired(self, monkeypatch, tmp_path):
        """Test requests new token when cache is expired."""
        cache_file = tmp_path / ".motus_token.json"
        token = get_token_module(monkeypatch)

        # Create expired cache
        expired_exp = token.now_ts() - 100
        cache_data = {
            "access_token": "expired-token",
            "expires_at": expired_exp,
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        token.CACHE_PATH = str(cache_file)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "new-token", "expires_in": 3600},
            status=200,
        )

        result = token.get_token()
        assert result["access_token"] == "new-token"


class TestEnvHelpers:
    """Tests for .env file helpers."""

    def test_read_env_lines_nonexistent(self, monkeypatch, tmp_path):
        """Test reading nonexistent file returns empty list."""
        token = get_token_module(monkeypatch)

        result = token.read_env_lines(str(tmp_path / "nonexistent.env"))
        assert result == []

    def test_read_env_lines_existing(self, monkeypatch, tmp_path):
        """Test reading existing file returns lines."""
        token = get_token_module(monkeypatch)

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2")

        result = token.read_env_lines(str(env_file))
        assert len(result) == 2

    def test_write_env_creates_file(self, monkeypatch, tmp_path):
        """Test write_env creates file."""
        token = get_token_module(monkeypatch)

        env_file = tmp_path / ".env"

        token.write_env(str(env_file), {"NEW_VAR": "new_value"})

        content = env_file.read_text()
        assert "NEW_VAR=new_value" in content

    def test_write_env_updates_existing(self, monkeypatch, tmp_path):
        """Test write_env updates existing key."""
        token = get_token_module(monkeypatch)

        env_file = tmp_path / ".env"
        env_file.write_text("OLD_VAR=old_value\nKEEP_VAR=keep")

        token.write_env(str(env_file), {"OLD_VAR": "new_value"})

        content = env_file.read_text()
        assert "OLD_VAR=new_value" in content
        assert "KEEP_VAR=keep" in content

    def test_write_env_preserves_comments(self, monkeypatch, tmp_path):
        """Test write_env preserves comments."""
        token = get_token_module(monkeypatch)

        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nVAR=value")

        token.write_env(str(env_file), {"NEW_VAR": "new"})

        content = env_file.read_text()
        assert "# This is a comment" in content

    def test_write_env_adds_new_key(self, monkeypatch, tmp_path):
        """Test write_env adds new key at end."""
        token = get_token_module(monkeypatch)

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value")

        token.write_env(str(env_file), {"NEW_KEY": "new_value"})

        content = env_file.read_text()
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content


class TestRequestTokenExtended:
    """Extended tests for request_token function."""

    @responses.activate
    def test_returns_raw_text_when_not_json(self, monkeypatch):
        """Test returns raw_text when response is not JSON."""
        token = get_token_module(monkeypatch)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            body="plain-text-token",
            status=200,
            content_type="text/plain",
        )

        result = token.request_token()
        assert result.get("raw_text") == "plain-text-token"

    @responses.activate
    def test_form_request_with_expiry(self, monkeypatch):
        """Test form request includes expires_in."""
        token = get_token_module(monkeypatch)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "tok", "expires_in": 7200},
            status=200,
        )

        result = token.request_token()
        assert result["access_token"] == "tok"
        assert result["expires_in"] == 7200


class TestInferExpFromJwtExtended:
    """Extended tests for infer_exp_from_jwt function."""

    def test_malformed_base64_returns_none(self, monkeypatch):
        """Test malformed base64 in JWT returns None."""
        token = get_token_module(monkeypatch)

        # JWT with invalid base64 payload
        jwt = "header.!!!invalid!!!.signature"

        result = token.infer_exp_from_jwt(jwt)
        assert result is None

    def test_invalid_json_payload_returns_none(self, monkeypatch):
        """Test invalid JSON in payload returns None."""
        token = get_token_module(monkeypatch)

        import base64
        # Create JWT with invalid JSON payload
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(b'not-json').decode().rstrip("=")

        jwt = f"{header}.{payload}.sig"

        result = token.infer_exp_from_jwt(jwt)
        assert result is None

    def test_empty_string_returns_none(self, monkeypatch):
        """Test empty string returns None."""
        token = get_token_module(monkeypatch)

        result = token.infer_exp_from_jwt("")
        assert result is None

    def test_single_part_returns_none(self, monkeypatch):
        """Test single part token returns None."""
        token = get_token_module(monkeypatch)

        result = token.infer_exp_from_jwt("single-part-token")
        assert result is None


class TestNormalizeExtended:
    """Extended tests for normalize function."""

    def test_with_expires_in_calculates_expires_at(self, monkeypatch):
        """Test expires_in is used to calculate expires_at."""
        token = get_token_module(monkeypatch)

        raw = {"access_token": "my-token", "expires_in": 3600}
        result = token.normalize(raw)

        # expires_at should be approximately now + 3600
        expected = token.now_ts() + 3600
        assert abs(result["expires_at"] - expected) < 2

    def test_with_expiresIn_camelCase(self, monkeypatch):
        """Test handles camelCase expiresIn."""
        token = get_token_module(monkeypatch)

        raw = {"access_token": "my-token", "expiresIn": 1800}
        result = token.normalize(raw)

        assert result["expires_in"] == pytest.approx(1800, abs=2)

    def test_fallback_to_default_ttl(self, monkeypatch):
        """Test uses DEFAULT_TTL when no expiry info."""
        token = get_token_module(monkeypatch)

        # Token without expires_in and not a JWT with exp
        raw = {"access_token": "simple-token"}
        result = token.normalize(raw)

        # Should use DEFAULT_TTL_SECONDS (55 * 60 = 3300)
        expected = token.now_ts() + token.DEFAULT_TTL_SECONDS
        assert abs(result["expires_at"] - expected) < 2

    def test_uses_jwt_exp_when_no_expires_in(self, monkeypatch):
        """Test uses JWT exp claim when expires_in missing."""
        token = get_token_module(monkeypatch)

        import base64
        future_exp = token.now_ts() + 7200

        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({"exp": future_exp}).encode()).decode().rstrip("=")
        jwt_token = f"{header}.{payload}.sig"

        raw = {"access_token": jwt_token}
        result = token.normalize(raw)

        assert result["expires_at"] == future_exp


class TestGetTokenExtended:
    """Extended tests for get_token function."""

    @responses.activate
    def test_cache_hit(self, monkeypatch, tmp_path):
        """Test uses cached token when valid."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        token = get_token_module(monkeypatch)

        # Create valid cache
        future_exp = token.now_ts() + 3600
        cache_data = {
            "access_token": "cached-token",
            "expires_at": future_exp,
            "token_type": "Bearer",
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        token.CACHE_PATH = str(cache_file)

        result = token.get_token()
        assert result["access_token"] == "cached-token"

    @responses.activate
    def test_cache_miss_requests_new(self, monkeypatch, tmp_path):
        """Test requests new token when cache is invalid."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        token = get_token_module(monkeypatch)
        token.CACHE_PATH = str(cache_file)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "new-token", "expires_in": 3600},
            status=200,
        )

        # No cache exists, so should request new token
        result = token.get_token()
        assert result["access_token"] == "new-token"

    @responses.activate
    def test_force_refresh_ignores_cache(self, monkeypatch, tmp_path):
        """Test force_refresh ignores valid cache."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        token = get_token_module(monkeypatch)

        # Create valid cache
        future_exp = token.now_ts() + 3600
        cache_data = {
            "access_token": "old-cached-token",
            "expires_at": future_exp,
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        token.CACHE_PATH = str(cache_file)

        responses.add(
            responses.POST,
            re.compile(r".*/tokenservice/token/api.*"),
            json={"access_token": "fresh-token", "expires_in": 3600},
            status=200,
        )

        result = token.get_token(force_refresh=True)
        assert result["access_token"] == "fresh-token"


class TestParseCli:
    """Tests for parse_cli function."""

    def test_default_values(self, monkeypatch):
        """Test default CLI values."""
        monkeypatch.setattr(sys, "argv", ["motus-get-token.py"])
        token = get_token_module(monkeypatch)

        args = token.parse_cli()
        assert args.json is False
        assert args.print_export is False
        assert args.force is False
        assert args.write_env is False
        assert args.env_path == ".env"

    def test_json_flag(self, monkeypatch):
        """Test --json flag."""
        monkeypatch.setattr(sys, "argv", ["motus-get-token.py", "--json"])
        token = get_token_module(monkeypatch)

        args = token.parse_cli()
        assert args.json is True

    def test_force_flag(self, monkeypatch):
        """Test --force flag."""
        monkeypatch.setattr(sys, "argv", ["motus-get-token.py", "--force"])
        token = get_token_module(monkeypatch)

        args = token.parse_cli()
        assert args.force is True

    def test_write_env_flag(self, monkeypatch):
        """Test --write-env flag."""
        monkeypatch.setattr(sys, "argv", ["motus-get-token.py", "--write-env"])
        token = get_token_module(monkeypatch)

        args = token.parse_cli()
        assert args.write_env is True

    def test_env_path_argument(self, monkeypatch):
        """Test --env-path argument."""
        monkeypatch.setattr(sys, "argv", ["motus-get-token.py", "--env-path", "/custom/.env"])
        token = get_token_module(monkeypatch)

        args = token.parse_cli()
        assert args.env_path == "/custom/.env"


class TestDlog:
    """Tests for dlog debug logging function."""

    def test_dlog_only_outputs_when_debug_enabled(self, monkeypatch, capsys):
        """Test dlog function outputs debug message when DEBUG enabled."""
        # Set DEBUG env var BEFORE loading the module
        monkeypatch.setenv("DEBUG", "1")
        token = get_token_module(monkeypatch)

        token.dlog("Test debug message")

        # Logger outputs to stdout with custom format
        captured = capsys.readouterr()
        assert "Test debug message" in captured.out

    def test_dlog_format_includes_debug_prefix(self, monkeypatch, capsys):
        """Test dlog outputs with [DEBUG] prefix."""
        monkeypatch.setenv("DEBUG", "1")
        token = get_token_module(monkeypatch)

        token.dlog("Formatted message")

        # Logger outputs to stdout with [DEBUG] prefix
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out
        assert "Formatted message" in captured.out


class TestSaveCache:
    """Tests for save_cache function."""

    def test_saves_cache_to_file(self, monkeypatch, tmp_path):
        """Test saves cache data to file."""
        cache_file = tmp_path / ".motus_token.json"
        monkeypatch.setenv("MOTUS_TOKEN_CACHE", str(cache_file))

        token = get_token_module(monkeypatch)
        token.CACHE_PATH = str(cache_file)

        cache_data = {"access_token": "test-token", "expires_at": 9999999999}
        token.save_cache(cache_data)

        with open(cache_file) as f:
            saved = json.load(f)

        assert saved["access_token"] == "test-token"
        assert saved["expires_at"] == 9999999999
