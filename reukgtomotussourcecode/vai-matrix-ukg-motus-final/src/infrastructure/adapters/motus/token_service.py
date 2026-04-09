"""
In-memory Motus token service.

Handles JWT token generation and caching without file system dependencies.
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_URL = "https://token.motus.com/tokenservice/token/api"
DEFAULT_TTL_SECONDS = 55 * 60  # 55 minutes


class MotusTokenService:
    """Service for generating Motus JWT tokens in memory."""

    def __init__(
        self,
        login_id: Optional[str] = None,
        password: Optional[str] = None,
        token_url: Optional[str] = None,
    ):
        """
        Initialize token service.

        Args:
            login_id: Motus login ID (defaults to MOTUS_LOGIN_ID env var)
            password: Motus password (defaults to MOTUS_PASSWORD env var)
            token_url: Token API URL (defaults to MOTUS_TOKEN_URL env var)
        """
        self.login_id = login_id or os.getenv("MOTUS_LOGIN_ID", "")
        self.password = password or os.getenv("MOTUS_PASSWORD", "")
        self.token_url = token_url or os.getenv("MOTUS_TOKEN_URL", DEFAULT_TOKEN_URL)
        self._cached_token: Optional[str] = None
        self._expires_at: Optional[int] = None

    def get_token(self, force_refresh: bool = False) -> str:
        """
        Get valid JWT token, generating new one if needed.

        Args:
            force_refresh: Force regeneration even if cached token is valid

        Returns:
            Valid JWT token string

        Raises:
            ValueError: If credentials are missing
            RuntimeError: If token request fails
        """
        if not force_refresh and self._is_token_valid():
            logger.debug("Using cached token")
            return self._cached_token

        self._generate_token()
        return self._cached_token

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid (with 60s safety margin)."""
        if not self._cached_token or not self._expires_at:
            return False
        return self._expires_at - self._now_ts() > 60

    def _generate_token(self) -> None:
        """Generate new token from Motus API."""
        if not self.login_id or not self.password:
            raise ValueError(
                "Missing MOTUS_LOGIN_ID or MOTUS_PASSWORD. "
                "Set these environment variables to generate tokens."
            )

        # Log credentials for debugging (password masked for security)
        masked_password = f"{'*' * len(self.password)}" if self.password else "(empty)"
        logger.info(
            f"Requesting new Motus token from {self.token_url} | "
            f"loginId={self.login_id} | password={masked_password} | "
            f"password_length={len(self.password)}"
        )

        # Try form-urlencoded first (primary format per Motus API docs)
        response = self._request_token_form()
        if response.status_code >= 300:
            logger.debug(f"Form request failed ({response.status_code}), trying JSON")
            response = self._request_token_json()

        if response.status_code >= 300:
            error_body = response.text[:500] if response.text else "No response body"
            raise RuntimeError(
                f"Token request failed: {response.status_code} - {error_body}"
            )

        # Parse response
        try:
            data = response.json()
        except json.JSONDecodeError:
            # Handle plain text token response
            self._cached_token = response.text.strip()
            self._expires_at = self._now_ts() + DEFAULT_TTL_SECONDS
            logger.info(f"Generated new Motus token (plain text), expires at {self._expires_at}")
            return

        # Extract token from JSON response
        self._cached_token = (
            data.get("access_token") or
            data.get("token") or
            data.get("bearerToken")
        )

        if not self._cached_token:
            raise RuntimeError(f"No token in response: {json.dumps(data)[:500]}")

        # Determine expiration
        expires_in = data.get("expires_in") or data.get("expiresIn")
        if expires_in:
            self._expires_at = self._now_ts() + int(expires_in)
        else:
            # Try to extract from JWT payload
            exp = self._extract_exp_from_jwt(self._cached_token)
            self._expires_at = exp or (self._now_ts() + DEFAULT_TTL_SECONDS)

        logger.info(f"Generated new Motus token, expires at {self._expires_at}")

    def _request_token_form(self) -> requests.Response:
        """Request token using form-urlencoded format."""
        return requests.post(
            self.token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/plain, */*",
            },
            data={"loginId": self.login_id, "password": self.password},
            timeout=30,
        )

    def _request_token_json(self) -> requests.Response:
        """Request token using JSON format (fallback)."""
        return requests.post(
            self.token_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
            },
            json={"loginId": self.login_id, "password": self.password},
            timeout=30,
        )

    @staticmethod
    def _now_ts() -> int:
        """Get current UTC timestamp."""
        return int(datetime.now(tz=timezone.utc).timestamp())

    @staticmethod
    def _extract_exp_from_jwt(token: str) -> Optional[int]:
        """Extract expiration timestamp from JWT payload."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            payload = parts[1]
            # Add padding for base64 decoding
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            exp = decoded.get("exp")
            return int(exp) if exp else None
        except Exception:
            return None
