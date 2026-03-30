"""
No-op notifier.

Provides a no-operation notifier for testing or when notifications are disabled.
"""

import logging
from typing import List, Optional

from .base import Notifier

logger = logging.getLogger(__name__)


class NoOpNotifier(Notifier):
    """No-op notifier for testing or when notifications are disabled."""

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
        logger.debug(f"NoOpNotifier: Would send email '{subject}' to {recipients}")
        return True
