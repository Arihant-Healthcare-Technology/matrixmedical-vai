"""
Secrets Manager Module - SOW Requirement 2.6

Provides a unified interface for secrets management across different providers.
Supports environment variables (development), AWS Secrets Manager (production),
and HashiCorp Vault (alternative).

Usage:
    from common.secrets_manager import get_secrets_manager

    secrets = get_secrets_manager()  # Auto-detects based on SECRETS_PROVIDER env
    api_key = secrets.get_secret("UKG_API_KEY")
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretsManager(ABC):
    """Abstract base class for secrets management."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a secret value by key.

        Args:
            key: The secret key/name to retrieve

        Returns:
            The secret value or None if not found
        """
        pass

    @abstractmethod
    def get_secrets_batch(self, keys: list) -> Dict[str, Optional[str]]:
        """
        Retrieve multiple secrets at once.

        Args:
            keys: List of secret keys to retrieve

        Returns:
            Dictionary mapping keys to their values
        """
        pass

    def get_secret_required(self, key: str) -> str:
        """
        Retrieve a secret that must exist.

        Args:
            key: The secret key/name to retrieve

        Returns:
            The secret value

        Raises:
            ValueError: If the secret is not found
        """
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found")
        return value


class EnvSecretsManager(SecretsManager):
    """
    Environment variable-based secrets manager for development.

    Reads secrets from environment variables. Optionally supports
    loading from a .env file.
    """

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize the environment secrets manager.

        Args:
            env_file: Optional path to .env file to load
        """
        self._cache: Dict[str, str] = {}

        if env_file and os.path.exists(env_file):
            self._load_env_file(env_file)
            logger.info(f"Loaded secrets from env file: {env_file}")

    def _load_env_file(self, env_file: str) -> None:
        """Load environment variables from a file."""
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        self._cache[key] = value
                        # Also set in environment for subprocess compatibility
                        if key not in os.environ:
                            os.environ[key] = value

            # Log MOTUS credentials for debugging
            motus_login_id = self._cache.get('MOTUS_LOGIN_ID', os.environ.get('MOTUS_LOGIN_ID', ''))
            motus_password = self._cache.get('MOTUS_PASSWORD', os.environ.get('MOTUS_PASSWORD', ''))
            motus_token_url = self._cache.get('MOTUS_TOKEN_URL', os.environ.get('MOTUS_TOKEN_URL', ''))
            motus_jwt = self._cache.get('MOTUS_JWT', os.environ.get('MOTUS_JWT', ''))

            logger.info(f"ENV CONFIG LOADED | File: {env_file}")
            logger.info(f"ENV CONFIG | MOTUS_LOGIN_ID: {motus_login_id}")
            logger.info(f"ENV CONFIG | MOTUS_PASSWORD: {motus_password}")
            logger.info(f"ENV CONFIG | MOTUS_TOKEN_URL: {motus_token_url}")
            logger.info(f"ENV CONFIG | MOTUS_JWT: {motus_jwt[:50]}..." if motus_jwt and len(motus_jwt) > 50 else f"ENV CONFIG | MOTUS_JWT: {motus_jwt}")

        except Exception as e:
            logger.warning(f"Failed to load env file {env_file}: {e}")

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        # Check cache first (from .env file)
        if key in self._cache:
            return self._cache[key]
        # Then check actual environment
        return os.environ.get(key)

    def get_secrets_batch(self, keys: list) -> Dict[str, Optional[str]]:
        """Get multiple secrets from environment."""
        return {key: self.get_secret(key) for key in keys}


class AWSSecretsManager(SecretsManager):
    """
    AWS Secrets Manager integration for production deployments.

    Requires boto3 and appropriate AWS credentials/IAM role.
    Supports caching to minimize API calls.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        secret_prefix: str = "",
        cache_ttl: int = 300
    ):
        """
        Initialize AWS Secrets Manager client.

        Args:
            region_name: AWS region (defaults to AWS_REGION env var)
            secret_prefix: Optional prefix for all secret names
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self._region = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        self._prefix = secret_prefix
        self._cache: Dict[str, str] = {}
        self._cache_ttl = cache_ttl
        self._client = None

        logger.info(f"Initialized AWS Secrets Manager (region: {self._region})")

    def _get_client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    'secretsmanager',
                    region_name=self._region
                )
            except ImportError:
                raise ImportError(
                    "boto3 is required for AWS Secrets Manager. "
                    "Install with: pip install boto3"
                )
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        """
        Get secret from AWS Secrets Manager.

        Handles both single-value secrets and JSON secrets.
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        secret_name = f"{self._prefix}{key}" if self._prefix else key

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_name)

            # Handle string or binary secret
            if 'SecretString' in response:
                secret_value = response['SecretString']

                # Try to parse as JSON (common pattern for grouped secrets)
                try:
                    secret_dict = json.loads(secret_value)
                    if isinstance(secret_dict, dict):
                        # Cache all keys from the JSON
                        for k, v in secret_dict.items():
                            self._cache[k] = str(v)
                        # Return specific key if it exists
                        if key in secret_dict:
                            return str(secret_dict[key])
                        # Otherwise return the raw value
                        return secret_value
                except json.JSONDecodeError:
                    pass

                self._cache[key] = secret_value
                return secret_value
            else:
                # Binary secret
                import base64
                secret_value = base64.b64decode(response['SecretBinary']).decode('utf-8')
                self._cache[key] = secret_value
                return secret_value

        except Exception as e:
            logger.warning(f"Failed to get secret '{secret_name}' from AWS: {e}")
            return None

    def get_secrets_batch(self, keys: list) -> Dict[str, Optional[str]]:
        """Get multiple secrets from AWS."""
        # AWS Secrets Manager doesn't have a native batch get,
        # but we can leverage caching and grouped secrets
        results = {}
        for key in keys:
            results[key] = self.get_secret(key)
        return results


class VaultSecretsManager(SecretsManager):
    """
    HashiCorp Vault integration for enterprise deployments.

    Requires hvac library and Vault authentication configured.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        mount_point: str = "secret",
        path_prefix: str = ""
    ):
        """
        Initialize Vault client.

        Args:
            url: Vault server URL (defaults to VAULT_ADDR env var)
            token: Vault token (defaults to VAULT_TOKEN env var)
            mount_point: KV secrets engine mount point
            path_prefix: Optional prefix for all secret paths
        """
        self._url = url or os.environ.get('VAULT_ADDR', 'http://localhost:8200')
        self._token = token or os.environ.get('VAULT_TOKEN')
        self._mount_point = mount_point
        self._path_prefix = path_prefix
        self._client = None
        self._cache: Dict[str, str] = {}

        logger.info(f"Initialized Vault Secrets Manager (url: {self._url})")

    def _get_client(self):
        """Lazy-load hvac client."""
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(url=self._url, token=self._token)
                if not self._client.is_authenticated():
                    raise ValueError("Vault client is not authenticated")
            except ImportError:
                raise ImportError(
                    "hvac is required for HashiCorp Vault. "
                    "Install with: pip install hvac"
                )
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from Vault KV store."""
        if key in self._cache:
            return self._cache[key]

        path = f"{self._path_prefix}/{key}" if self._path_prefix else key

        try:
            client = self._get_client()

            # Try KV v2 first, then v1
            try:
                response = client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self._mount_point
                )
                data = response.get('data', {}).get('data', {})
            except Exception:
                response = client.secrets.kv.v1.read_secret(
                    path=path,
                    mount_point=self._mount_point
                )
                data = response.get('data', {})

            # Handle both single-value and dict secrets
            if 'value' in data:
                secret_value = str(data['value'])
            elif key in data:
                secret_value = str(data[key])
            elif len(data) == 1:
                secret_value = str(list(data.values())[0])
            else:
                # Cache all keys and return JSON
                for k, v in data.items():
                    self._cache[k] = str(v)
                secret_value = json.dumps(data)

            self._cache[key] = secret_value
            return secret_value

        except Exception as e:
            logger.warning(f"Failed to get secret '{path}' from Vault: {e}")
            return None

    def get_secrets_batch(self, keys: list) -> Dict[str, Optional[str]]:
        """Get multiple secrets from Vault."""
        return {key: self.get_secret(key) for key in keys}


class CompositeSecretsManager(SecretsManager):
    """
    Composite secrets manager that tries multiple providers in order.

    Useful for fallback scenarios (e.g., try Vault, fall back to AWS,
    fall back to environment).
    """

    def __init__(self, managers: list):
        """
        Initialize with a list of secrets managers to try in order.

        Args:
            managers: List of SecretsManager instances
        """
        self._managers = managers

    def get_secret(self, key: str) -> Optional[str]:
        """Try each manager in order until secret is found."""
        for manager in self._managers:
            try:
                value = manager.get_secret(key)
                if value is not None:
                    return value
            except Exception as e:
                logger.debug(f"Manager {type(manager).__name__} failed for {key}: {e}")
                continue
        return None

    def get_secrets_batch(self, keys: list) -> Dict[str, Optional[str]]:
        """Get secrets, trying each manager for missing keys."""
        results: Dict[str, Optional[str]] = {key: None for key in keys}
        remaining_keys = set(keys)

        for manager in self._managers:
            if not remaining_keys:
                break

            try:
                batch_results = manager.get_secrets_batch(list(remaining_keys))
                for key, value in batch_results.items():
                    if value is not None:
                        results[key] = value
                        remaining_keys.discard(key)
            except Exception as e:
                logger.debug(f"Manager {type(manager).__name__} batch failed: {e}")
                continue

        return results


@lru_cache(maxsize=1)
def get_secrets_manager(provider: Optional[str] = None) -> SecretsManager:
    """
    Factory function to get the appropriate secrets manager.

    Auto-detects based on SECRETS_PROVIDER environment variable:
    - "env" or not set: EnvSecretsManager
    - "aws": AWSSecretsManager
    - "vault": VaultSecretsManager
    - "composite": CompositeSecretsManager (tries aws -> vault -> env)

    Args:
        provider: Override the provider selection

    Returns:
        Configured SecretsManager instance
    """
    provider = provider or os.environ.get('SECRETS_PROVIDER', 'env').lower()

    if provider == 'env':
        # Check for project-specific env files
        # Priority: ENV_FILE > ENV_NAME-based > default .env > project-specific
        env_name = os.environ.get('ENV_NAME', '').lower()
        env_files = [
            os.environ.get('ENV_FILE'),  # Explicit override (highest priority)
            '.env.dev' if env_name == 'development' else None,
            '.env.prod' if env_name == 'production' else None,
            '.env',  # Default fallback
            'matrix-ukg-bill.env',
            'matrix-ukg-motus.env',
            'matrix-ukg-tp.env',
        ]
        for env_file in env_files:
            if env_file and os.path.exists(env_file):
                logger.info(f"Using environment file: {env_file}")
                return EnvSecretsManager(env_file=env_file)
        return EnvSecretsManager()

    elif provider == 'aws':
        return AWSSecretsManager(
            region_name=os.environ.get('AWS_REGION'),
            secret_prefix=os.environ.get('AWS_SECRET_PREFIX', 'ukg-integration/')
        )

    elif provider == 'vault':
        return VaultSecretsManager(
            url=os.environ.get('VAULT_ADDR'),
            token=os.environ.get('VAULT_TOKEN'),
            path_prefix=os.environ.get('VAULT_SECRET_PATH', 'ukg-integration')
        )

    elif provider == 'composite':
        managers = []
        # Try AWS first in production
        try:
            managers.append(AWSSecretsManager())
        except Exception:
            pass
        # Then Vault
        try:
            managers.append(VaultSecretsManager())
        except Exception:
            pass
        # Always have env as fallback
        managers.append(EnvSecretsManager())
        return CompositeSecretsManager(managers)

    else:
        raise ValueError(f"Unknown secrets provider: {provider}")


# Convenience function for quick secret access
def get_secret(key: str, required: bool = False) -> Optional[str]:
    """
    Quick access to get a single secret.

    Args:
        key: Secret key to retrieve
        required: If True, raises ValueError when not found

    Returns:
        Secret value or None
    """
    manager = get_secrets_manager()
    if required:
        return manager.get_secret_required(key)
    return manager.get_secret(key)
