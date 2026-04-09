"""Tests for Motus Token Service."""

import base64
import json
import os
import time
import pytest
import responses
from unittest.mock import patch

from src.infrastructure.adapters.motus.token_service import (
    MotusTokenService,
    DEFAULT_TOKEN_URL,
    DEFAULT_TTL_SECONDS,
)


class TestMotusTokenService:
    """Test cases for MotusTokenService."""

    @pytest.fixture
    def token_service(self):
        """Create token service with test credentials."""
        return MotusTokenService(
            login_id="test-login",
            password="test-password",
            token_url="https://token.test.com/api",
        )

    @pytest.fixture
    def sample_jwt(self):
        """Create a sample JWT token with expiration."""
        # Header
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS512", "typ": "JWT"}).encode()
        ).decode().rstrip("=")

        # Payload with expiration 1 hour from now
        exp_time = int(time.time()) + 3600
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "123", "exp": exp_time}).encode()
        ).decode().rstrip("=")

        # Signature (mock)
        signature = base64.urlsafe_b64encode(b"mock-signature").decode().rstrip("=")

        return f"{header}.{payload}.{signature}"

    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials."""
        service = MotusTokenService(
            login_id="my-login",
            password="my-password",
            token_url="https://custom.url/token",
        )

        assert service.login_id == "my-login"
        assert service.password == "my-password"
        assert service.token_url == "https://custom.url/token"

    def test_init_from_env_vars(self):
        """Test initialization from environment variables."""
        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "env-login",
            "MOTUS_PASSWORD": "env-password",
            "MOTUS_TOKEN_URL": "https://env.url/token",
        }):
            service = MotusTokenService()

            assert service.login_id == "env-login"
            assert service.password == "env-password"
            assert service.token_url == "https://env.url/token"

    def test_init_default_token_url(self):
        """Test default token URL when not specified."""
        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "login",
            "MOTUS_PASSWORD": "password",
        }, clear=False):
            # Remove MOTUS_TOKEN_URL if it exists
            env = dict(os.environ)
            env.pop("MOTUS_TOKEN_URL", None)
            with patch.dict(os.environ, env, clear=True):
                service = MotusTokenService(login_id="login", password="pass")
                assert service.token_url == DEFAULT_TOKEN_URL

    def test_get_token_missing_credentials(self):
        """Test get_token raises ValueError when credentials missing."""
        service = MotusTokenService(login_id="", password="")

        with pytest.raises(ValueError) as exc_info:
            service.get_token()

        assert "Missing MOTUS_LOGIN_ID or MOTUS_PASSWORD" in str(exc_info.value)

    @responses.activate
    def test_get_token_form_success(self, token_service, sample_jwt):
        """Test successful token generation with form-urlencoded."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        token = token_service.get_token()

        assert token == sample_jwt
        assert token_service._cached_token == sample_jwt
        assert token_service._expires_at is not None

    @responses.activate
    def test_get_token_json_fallback(self, token_service, sample_jwt):
        """Test fallback to JSON format when form fails."""
        # Form request fails
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"error": "Invalid format"},
            status=400,
        )
        # JSON request succeeds
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        token = token_service.get_token()

        assert token == sample_jwt
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_token_with_bearer_token_key(self, token_service, sample_jwt):
        """Test parsing response with bearerToken key."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"bearerToken": sample_jwt, "expiresIn": 3600},
            status=200,
        )

        token = token_service.get_token()

        assert token == sample_jwt

    @responses.activate
    def test_get_token_with_token_key(self, token_service, sample_jwt):
        """Test parsing response with token key."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        token = token_service.get_token()

        assert token == sample_jwt

    @responses.activate
    def test_get_token_extracts_exp_from_jwt(self, token_service, sample_jwt):
        """Test expiration is extracted from JWT when expires_in not provided."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt},  # No expires_in
            status=200,
        )

        token_service.get_token()

        # Should have extracted exp from JWT
        assert token_service._expires_at is not None

    @responses.activate
    def test_get_token_uses_default_ttl(self, token_service):
        """Test default TTL when no expiration info available."""
        # Create a simple token without exp claim
        simple_token = "simple.token.here"

        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": simple_token},  # No expires_in, invalid JWT
            status=200,
        )

        before = int(time.time())
        token_service.get_token()
        after = int(time.time())

        # Should use default TTL
        expected_min = before + DEFAULT_TTL_SECONDS
        expected_max = after + DEFAULT_TTL_SECONDS
        assert expected_min <= token_service._expires_at <= expected_max

    @responses.activate
    def test_get_token_caches_result(self, token_service, sample_jwt):
        """Test that token is cached and reused."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        # First call - makes API request
        token1 = token_service.get_token()

        # Second call - should use cache
        token2 = token_service.get_token()

        assert token1 == token2
        assert len(responses.calls) == 1  # Only one API call

    @responses.activate
    def test_get_token_force_refresh(self, token_service, sample_jwt):
        """Test force_refresh bypasses cache."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": "new-token.is.here", "expires_in": 3600},
            status=200,
        )

        # First call
        token1 = token_service.get_token()

        # Force refresh
        token2 = token_service.get_token(force_refresh=True)

        assert token1 != token2
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_token_refreshes_expired_cache(self, token_service, sample_jwt):
        """Test that expired cached token triggers refresh."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": "refreshed.token.here", "expires_in": 3600},
            status=200,
        )

        # First call
        token_service.get_token()

        # Manually expire the token
        token_service._expires_at = int(time.time()) - 100

        # Second call should refresh
        token2 = token_service.get_token()

        assert token2 == "refreshed.token.here"
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_token_api_error(self, token_service):
        """Test error handling when API fails."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"error": "Invalid credentials"},
            status=401,
        )
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"error": "Invalid credentials"},
            status=401,
        )

        with pytest.raises(RuntimeError) as exc_info:
            token_service.get_token()

        assert "Token request failed: 401" in str(exc_info.value)

    @responses.activate
    def test_get_token_plain_text_response(self, token_service):
        """Test handling of plain text token response."""
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            body="plain-text-token",
            status=200,
            content_type="text/plain",
        )

        token = token_service.get_token()

        assert token == "plain-text-token"

    def test_is_token_valid_no_token(self, token_service):
        """Test _is_token_valid returns False when no token."""
        assert token_service._is_token_valid() is False

    def test_is_token_valid_no_expiry(self, token_service):
        """Test _is_token_valid returns False when no expiry."""
        token_service._cached_token = "some-token"
        token_service._expires_at = None

        assert token_service._is_token_valid() is False

    def test_is_token_valid_expired(self, token_service):
        """Test _is_token_valid returns False when expired."""
        token_service._cached_token = "some-token"
        token_service._expires_at = int(time.time()) - 100  # Expired

        assert token_service._is_token_valid() is False

    def test_is_token_valid_within_safety_margin(self, token_service):
        """Test _is_token_valid returns False within 60s safety margin."""
        token_service._cached_token = "some-token"
        token_service._expires_at = int(time.time()) + 30  # 30s from now

        assert token_service._is_token_valid() is False

    def test_is_token_valid_true(self, token_service):
        """Test _is_token_valid returns True for valid token."""
        token_service._cached_token = "some-token"
        token_service._expires_at = int(time.time()) + 3600  # 1 hour from now

        assert token_service._is_token_valid() is True

    def test_extract_exp_from_jwt_valid(self, sample_jwt):
        """Test extracting expiration from valid JWT."""
        exp = MotusTokenService._extract_exp_from_jwt(sample_jwt)

        assert exp is not None
        assert isinstance(exp, int)
        assert exp > int(time.time())

    def test_extract_exp_from_jwt_invalid_format(self):
        """Test extracting expiration from invalid JWT format."""
        exp = MotusTokenService._extract_exp_from_jwt("not.a.valid.jwt.token")
        assert exp is None

    def test_extract_exp_from_jwt_no_exp_claim(self):
        """Test extracting expiration when no exp claim."""
        # Create JWT without exp
        header = base64.urlsafe_b64encode(b'{"alg":"RS512"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(b'{"sub":"123"}').decode().rstrip("=")
        signature = base64.urlsafe_b64encode(b"sig").decode().rstrip("=")
        jwt = f"{header}.{payload}.{signature}"

        exp = MotusTokenService._extract_exp_from_jwt(jwt)
        assert exp is None

    def test_extract_exp_from_jwt_malformed(self):
        """Test extracting expiration from malformed JWT."""
        exp = MotusTokenService._extract_exp_from_jwt("only-one-part")
        assert exp is None

    def test_now_ts(self):
        """Test _now_ts returns current UTC timestamp."""
        before = int(time.time())
        result = MotusTokenService._now_ts()
        after = int(time.time())

        assert before <= result <= after


class TestMotusTokenServiceIntegration:
    """Integration-style tests for MotusTokenService."""

    @responses.activate
    def test_full_token_lifecycle(self):
        """Test complete token lifecycle: get, cache, expire, refresh."""
        service = MotusTokenService(
            login_id="test-login",
            password="test-password",
            token_url="https://token.test.com/api",
        )

        # Create tokens
        token1 = "first.token.jwt"
        token2 = "second.token.jwt"

        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": token1, "expires_in": 3600},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": token2, "expires_in": 3600},
            status=200,
        )

        # 1. Get initial token
        result1 = service.get_token()
        assert result1 == token1

        # 2. Cached token returned
        result2 = service.get_token()
        assert result2 == token1
        assert len(responses.calls) == 1

        # 3. Expire token
        service._expires_at = int(time.time()) - 100

        # 4. Auto-refresh on next call
        result3 = service.get_token()
        assert result3 == token2
        assert len(responses.calls) == 2

    @responses.activate
    def test_multiple_format_attempts(self):
        """Test service tries multiple formats before failing."""
        service = MotusTokenService(
            login_id="test-login",
            password="test-password",
            token_url="https://token.test.com/api",
        )

        # Both form and JSON fail
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"error": "Bad request"},
            status=400,
        )
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"error": "Bad request"},
            status=400,
        )

        with pytest.raises(RuntimeError):
            service.get_token()

        # Should have tried both formats
        assert len(responses.calls) == 2
