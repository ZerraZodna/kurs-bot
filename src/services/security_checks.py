from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger(__name__)


def verify_secrets_config() -> None:
    _check("TELEGRAM_BOT_TOKEN", settings.TELEGRAM_BOT_TOKEN, required=False)
    _check("SLACK_BOT_TOKEN", settings.SLACK_BOT_TOKEN, required=False)
    _check("SENDGRID_API_KEY", settings.SENDGRID_API_KEY, required=False)
    _check("GDPR_ADMIN_TOKEN", settings.GDPR_ADMIN_TOKEN, required=True)
    _check("API_AUTH_TOKEN", settings.API_AUTH_TOKEN, required=False)


def _check(name: str, value: str, required: bool) -> None:
    if not value:
        if required:
            logger.warning("%s is not set", name)
        return

    lower = value.lower()
    placeholders = ("your-", "changeme", "example", "test-token", "token")
    if any(p in lower for p in placeholders):
        logger.warning("%s appears to be a placeholder", name)
