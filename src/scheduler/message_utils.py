"""Message formatting and sending helpers for scheduler."""

import asyncio
import logging

from sqlalchemy.orm import Session

from src.config import settings

# Use dynamic lookup for send_message so tests can monkeypatch the package symbol
from src.models.database import MessageLog, User
from src.services.traffic_tracker import record_traffic_event

logger = logging.getLogger(__name__)

def translate_text_sync(text: str, language: str) -> str:
    print("Translate to lng=%s", str)
    try:
        prompt = (
            f"Translate the following text to {language}. "
            "Preserve paragraph breaks and meaning. Return only the translation.\n\n"
            f"{text}"
        )
        model = settings.OLLAMA_MODEL
        # Lazy import to avoid circular imports at module import time
        from src.services.dialogue.ollama_client import call_ollama
        resp = asyncio.run(call_ollama(prompt, model=model))
        return resp or text
    except Exception as e:
        logger.warning(f"Translation failed, sending original text: {e}")
        return text


def send_outbound_message(db: Session, user: User, text: str) -> None:
    status = "sent"
    error = None
    try:
        if user.channel == "telegram":
            from src import scheduler as _scheduler_pkg
            asyncio.run(_scheduler_pkg.send_message(int(user.external_id), text))
            record_traffic_event()
        else:
            logger.warning(f"Unsupported channel for scheduled send: {user.channel}")
            status = "failed"
    except Exception as e:
        status = "failed"
        error = str(e)
        logger.error(f"Error sending scheduled message: {e}")

    # Log outbound message
    log = MessageLog(
        user_id=user.user_id,
        direction="outbound",
        channel=user.channel,
        external_message_id=None,
        content=text,
        status=status,
        error_message=error,
    )
    log.message_role = "assistant"
    db.add(log)
    db.commit()
