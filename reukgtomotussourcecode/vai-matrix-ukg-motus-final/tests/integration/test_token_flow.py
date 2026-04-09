"""
Integration tests for Motus token flow.

Tests the complete token generation and usage flow with mocked APIs.
"""

import os
import base64
import json
import time
import pytest
import responses
from unittest.mock import patch, MagicMock

from src.infrastructure.adapters.motus import MotusClient, MotusTokenService
from src.infrastructure.config.settings import MotusSettings
from src.domain.exceptions import AuthenticationError


class TestTokenGenerationFlow:
    """Integration tests for token generation and API authentication."""

    @pytest.fixture
    def sample_jwt(self):
        """Create a sample JWT token with expiration."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS512", "typ": "JWT"}).encode()
        ).decode().rstrip("=")

        exp_time = int(time.time()) + 3600
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "123", "exp": exp_time}).encode()
        ).decode().rstrip("=")

        signature = base64.urlsafe_b64encode(b"mock-signature").decode().rstrip("=")

        return f"{header}.{payload}.{signature}"

    @responses.activate
    def test_client_generates_token_when_missing(self, sample_jwt):
        """Test MotusClient generates token when MOTUS_JWT is not set."""
        # Mock token generation endpoint
        responses.add(
            responses.POST,
            "https://token.motus.com/tokenservice/token/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        # Mock driver API endpoint
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"clientEmployeeId1": "12345", "firstName": "John"},
            status=200,
        )

        # Set credentials but no JWT
        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "test-login",
            "MOTUS_PASSWORD": "test-password",
            "MOTUS_JWT": "",  # Empty JWT
        }):
            settings = MotusSettings.from_env()
            assert settings.jwt == ""

            # Client should auto-generate token
            client = MotusClient(settings=settings)

            assert client.settings.jwt == sample_jwt
            assert client._token_refreshed is True

            # Should be able to make API calls
            result = client.get_driver("12345")
            assert result["clientEmployeeId1"] == "12345"

    @responses.activate
    def test_client_refreshes_token_on_401(self, sample_jwt):
        """Test MotusClient refreshes token when API returns 401."""
        old_token = "old.expired.token"
        new_token = sample_jwt

        # First request fails with 401
        responses.add(
            responses.GET,
            "https://api.motus.com/v1/drivers/12345",
            json={"error": "Unauthorized"},
            status=401,
        )

        # Token refresh succeeds
        responses.add(
            responses.POST,
            "https://token.motus.com/tokenservice/token/api",
            json={"access_token": new_token, "expires_in": 3600},
            status=200,
        )

        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "test-login",
            "MOTUS_PASSWORD": "test-password",
        }):
            settings = MotusSettings(jwt=old_token)
            client = MotusClient(settings=settings)
            client._token_refreshed = False  # Reset for test

            # Request should fail but trigger refresh
            with pytest.raises(AuthenticationError):
                client.get_driver("12345")

            # Token should be refreshed
            assert client.settings.jwt == new_token
            assert client._token_refreshed is True

    @responses.activate
    def test_token_cached_across_requests(self, sample_jwt):
        """Test token is cached and reused across API requests."""
        # Mock token generation - should only be called once
        responses.add(
            responses.POST,
            "https://token.motus.com/tokenservice/token/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        # Mock multiple driver API calls
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://api.motus.com/v1/drivers/12345",
                json={"clientEmployeeId1": "12345"},
                status=200,
            )

        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "test-login",
            "MOTUS_PASSWORD": "test-password",
            "MOTUS_JWT": "",
        }):
            settings = MotusSettings.from_env()
            client = MotusClient(settings=settings)

            # Make multiple requests
            client.get_driver("12345")
            client.get_driver("12345")
            client.get_driver("12345")

            # Token endpoint should only be called once
            token_calls = [c for c in responses.calls if "token" in c.request.url]
            assert len(token_calls) == 1

    @responses.activate
    def test_token_flow_with_missing_credentials(self):
        """Test proper error handling when credentials are missing."""
        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "",
            "MOTUS_PASSWORD": "",
            "MOTUS_JWT": "",
        }, clear=False):
            settings = MotusSettings.from_env()

            with pytest.raises(AuthenticationError) as exc_info:
                MotusClient(settings=settings)

            assert "missing credentials" in str(exc_info.value).lower()


class TestTokenServiceIntegration:
    """Integration tests for MotusTokenService with real HTTP mocking."""

    @pytest.fixture
    def sample_jwt(self):
        """Create a sample JWT token with expiration."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS512", "typ": "JWT"}).encode()
        ).decode().rstrip("=")

        exp_time = int(time.time()) + 3600
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "123", "exp": exp_time}).encode()
        ).decode().rstrip("=")

        signature = base64.urlsafe_b64encode(b"mock-signature").decode().rstrip("=")

        return f"{header}.{payload}.{signature}"

    @responses.activate
    def test_full_token_lifecycle_with_expiry(self, sample_jwt):
        """Test complete token lifecycle including expiry and refresh."""
        token1 = sample_jwt
        token2 = sample_jwt.replace("mock-signature", "new-signature")

        # First token request
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": token1, "expires_in": 100},
            status=200,
        )

        # Second token request (after expiry)
        responses.add(
            responses.POST,
            "https://token.test.com/api",
            json={"access_token": token2, "expires_in": 3600},
            status=200,
        )

        service = MotusTokenService(
            login_id="test-login",
            password="test-password",
            token_url="https://token.test.com/api",
        )

        # Get initial token
        result1 = service.get_token()
        assert result1 == token1

        # Simulate token expiry
        service._expires_at = int(time.time()) - 100

        # Get new token (should auto-refresh)
        result2 = service.get_token()
        assert result2 == token2

        # Verify two API calls were made
        assert len(responses.calls) == 2

    @responses.activate
    def test_token_generation_retries_json_on_form_failure(self, sample_jwt):
        """Test service retries with JSON format when form fails."""
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

        service = MotusTokenService(
            login_id="test-login",
            password="test-password",
            token_url="https://token.test.com/api",
        )

        token = service.get_token()

        assert token == sample_jwt
        assert len(responses.calls) == 2

        # Verify different content types
        assert "form" in responses.calls[0].request.headers.get("Content-Type", "").lower()
        assert "json" in responses.calls[1].request.headers.get("Content-Type", "").lower()


class TestBatchRunnerTokenIntegration:
    """Integration tests for batch_runner token handling."""

    @pytest.fixture
    def sample_jwt(self):
        """Create a sample JWT token with expiration."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS512", "typ": "JWT"}).encode()
        ).decode().rstrip("=")

        exp_time = int(time.time()) + 3600
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "123", "exp": exp_time}).encode()
        ).decode().rstrip("=")

        signature = base64.urlsafe_b64encode(b"mock-signature").decode().rstrip("=")

        return f"{header}.{payload}.{signature}"

    @responses.activate
    def test_batch_runner_generates_token_at_startup(self, sample_jwt):
        """Test batch_runner generates token when MOTUS_JWT is missing."""
        # Mock token generation
        responses.add(
            responses.POST,
            "https://token.motus.com/tokenservice/token/api",
            json={"access_token": sample_jwt, "expires_in": 3600},
            status=200,
        )

        with patch.dict(os.environ, {
            "MOTUS_LOGIN_ID": "test-login",
            "MOTUS_PASSWORD": "test-password",
            "MOTUS_JWT": "",
            "COMPANY_ID": "TEST",
            "JOB_IDS": "1234",
            "UKG_CUSTOMER_API_KEY": "test-key",
            "UKG_USERNAME": "test-user",
            "UKG_PASSWORD": "test-pass",
        }):
            from src.infrastructure.config.settings import MotusSettings

            settings = MotusSettings.from_env()
            assert settings.jwt == ""

            # Simulate what batch_runner does
            if not settings.jwt:
                token_service = MotusTokenService()
                token = token_service.get_token()
                settings.set_jwt(token)

            assert settings.jwt == sample_jwt
