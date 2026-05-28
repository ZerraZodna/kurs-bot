"""Message formatting and sending helpers for scheduler."""

import asyncio
import logging

from sqlalchemy.orm import Session


# Use dynamic lookup for send_message so tests can monkeypatch the package symbol
from src.models.database import MessageLog, User
from src.services.traffic_tracker import record_traffic_event

logger = logging.getLogger(__name__)


async def _send_telegram_message(chat_id: int, text: str) -> None:
    """Send a telegram message using the already-running event loop."""
    from src import scheduler as _scheduler_pkg

    await _scheduler_pkg.send_message(chat_id, text)
    record_traffic_event()


def send_outbound_message(db: Session, user: User, text: str) -> None:
    """Send an outbound message to a user.

    Detects whether we are inside a running event loop (async context, e.g.
    uvicorn request handler) or not (sync context, e.g. APScheduler job)
    and dispatches accordingly.
    """
    status = "sent"
    error = None
    try:
        if user.channel == "telegram":
            try:
                # Try to get the running loop — if it exists we are in async context
                loop = asyncio.get_running_loop()
                # Schedule the async send on the existing loop
                loop.create_task(_send_telegram_message(int(user.external_id), text))
            except RuntimeError:
                # No running loop — we are in a sync context, use asyncio.run
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
