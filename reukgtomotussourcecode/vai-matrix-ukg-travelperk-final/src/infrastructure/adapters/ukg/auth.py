"""
UKG authentication utilities.

Handles Basic Auth token generation and caching for UKG API.
"""

import base64
import logging
from typing import Optional

from ....domain.exceptions import AuthenticationError


logger = logging.getLogger(__name__)


class UKGAuthenticator:
    """Handles UKG API authentication."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        basic_b64: Optional[str] = None,
        customer_api_key: Optional[str] = None,
    ):
        """
        Initialize authenticator.

        Args:
            username: UKG username
            password: UKG password
            basic_b64: Pre-encoded Basic auth token (alternative to username/password)
            customer_api_key: UKG customer API key
        """
        self.username = username
        self.password = password
        self.basic_b64 = basic_b64
        self.customer_api_key = customer_api_key
        self._cached_token: Optional[str] = None

    def get_token(self) -> str:
        """
        Get HTTP Basic auth token.

        Returns:
            Base64-encoded Basic auth token

        Raises:
            AuthenticationError: If credentials are missing or invalid
        """
        if self._cached_token:
            return self._cached_token

        # Try pre-encoded token first
        if self.basic_b64:
            token = self._validate_b64_token(self.basic_b64)
            if token:
                self._cached_token = token
                return token

        # Fall back to username/password
        if not self.username or not self.password:
            raise AuthenticationError(
                "Missing UKG_USERNAME/UKG_PASSWORD or UKG_BASIC_B64"
            )

        raw = f"{self.username}:{self.password}".encode()
        self._cached_token = base64.b64encode(raw).decode()
        return self._cached_token

    def _validate_b64_token(self, token: str) -> Optional[str]:
        """
        Validate and clean a base64 token.

        Args:
            token: Base64-encoded token string

        Returns:
            Cleaned token if valid, None otherwise
        """
        token = token.strip()
        token = "".join(token.split())  # Remove whitespace

        try:
            base64.b64decode(token, validate=True)
            logger.debug(f"Using UKG_BASIC_B64 (length: {len(token)})")
            return token
        except Exception as error:
            logger.warning(f"UKG_BASIC_B64 is invalid: {error}")
            return None

    def get_headers(self) -> dict:
        """
        Build authentication headers for UKG API requests.

        Returns:
            Dict of authentication headers

        Raises:
            AuthenticationError: If credentials are missing
        """
        if not self.customer_api_key:
            raise AuthenticationError("Missing UKG_CUSTOMER_API_KEY")

        return {
            "Authorization": f"Basic {self.get_token()}",
            "US-CUSTOMER-API-KEY": self.customer_api_key,
            "Accept": "application/json",
        }

    def clear_cache(self) -> None:
        """Clear cached token."""
        self._cached_token = None
