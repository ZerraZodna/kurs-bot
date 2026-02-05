from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.config import settings
from src.integrations.telegram import send_message
from src.services.job_state import get_state, set_state

logger = logging.getLogger(__name__)

_ADMIN_CHAT_ID_KEY = "admin_telegram_chat_id"


def set_admin_chat_id(chat_id: int) -> None:
    set_state(_ADMIN_CHAT_ID_KEY, str(chat_id))


def get_admin_chat_id() -> Optional[int]:
    raw = get_state(_ADMIN_CHAT_ID_KEY)
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def send_admin_notification(message: str) -> bool:
    admin_username = (settings.ADMIN_TELEGRAM_USERNAME or "").lstrip("@").strip()
    if not admin_username:
        return False

    chat_id = get_admin_chat_id()
    if not chat_id:
        logger.warning("Admin chat id not set; unable to send admin notification")
        return False

    try:
        asyncio.run(send_message(chat_id, message))
        return True
    except Exception as e:
        logger.warning("Failed to send admin notification: %s", e)
        return False
