"""
Notifier factory.

Provides factory function to create the appropriate notifier based on configuration.
"""

import logging
from typing import Optional

from .aws_ses import AWSESNotifier
from .base import Notifier
from .config import NotificationConfig
from .noop import NoOpNotifier
from .sendgrid import SendGridNotifier
from .smtp import SMTPNotifier

logger = logging.getLogger(__name__)


def get_notifier(config: Optional[NotificationConfig] = None) -> Notifier:
    """
    Get the appropriate notifier based on configuration.

    Args:
        config: Optional configuration (defaults to from_env())

    Returns:
        Configured Notifier instance
    """
    config = config or NotificationConfig.from_env()

    if not config.enabled:
        return NoOpNotifier(config)

    provider = config.provider.lower()

    if provider == 'smtp':
        return SMTPNotifier(config)
    elif provider == 'ses':
        return AWSESNotifier(config)
    elif provider == 'sendgrid':
        return SendGridNotifier(config)
    else:
        logger.warning(f"Unknown provider '{provider}', using NoOp notifier")
        return NoOpNotifier(config)
