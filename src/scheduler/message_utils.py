"""Message formatting and sending helpers for scheduler."""

import asyncio
import logging

from sqlalchemy.orm import Session


# Use dynamic lookup for send_message so tests can monkeypatch the package symbol
from src.models.database import MessageLog, User
from src.services.traffic_tracker import record_traffic_event

logger = logging.getLogger(__name__)


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
