"""Telegram long-polling service.

Alternative to ngrok/webhook for local development.
"""
import asyncio
import logging
from typing import Set, Optional

import httpx

from src.config import settings
from src.integrations.telegram import (
    TelegramHandler,
    send_typing_action,
    TELEGRAM_BOT_TOKEN,
    API_BASE,
)
from src.models.database import SessionLocal, User, MessageLog, BatchLock
from src.services.admin_notifier import send_admin_notification

logger = logging.getLogger(__name__)

# In-memory store for processed update IDs (single instance only)
_processed_updates: Set[int] = set()


async def poll_updates(offset: int = 0) -> list[dict]:
    """Fetch updates from Telegram using long-polling."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("[polling] TELEGRAM_BOT_TOKEN not configured")
        return []

    url = f"{API_BASE}/getUpdates"
    payload = {
        "timeout": settings.TELEGRAM_POLL_TIMEOUT,
        "offset": offset,
        "limit": settings.TELEGRAM_POLL_LIMIT,
        "allowed_updates": settings.TELEGRAM_POLL_ALLOWED_UPDATES,
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=settings.TELEGRAM_POLL_TIMEOUT + 5)
            r.raise_for_status()
            data = r.json()

            if data.get("ok"):
                return data.get("result", [])
            else:
                logger.error(f"[polling] API error: {data}")
                return []
        except httpx.TimeoutException:
            return []
        except Exception as e:
            logger.error(f"[polling] Error fetching updates: {e}")
            return []


async def _ensure_user(user_id: str, first_name: Optional[str], last_name: Optional[str]) -> Optional[int]:
    """Ensure user exists in DB, return user_id."""
    db = SessionLocal()
    try:
        db_user = db.query(User).filter_by(external_id=str(user_id), channel="telegram").first()
        if not db_user:
            db_user = User(
                external_id=str(user_id),
                channel="telegram",
                first_name=first_name,
                last_name=last_name,
                opted_in=True,
            )
            db.add(db_user)
            db.commit()
            name = " ".join([n for n in [first_name, last_name] if n]) or str(user_id)
            send_admin_notification(f"[INFO] New user joined (polling): {name}.")
        return db_user.user_id
    finally:
        db.close()


async def _log_message(user_id: int, parsed: dict) -> None:
    """Log incoming message to database."""
    db = SessionLocal()
    try:
        log = MessageLog(
            user_id=user_id,
            direction="inbound",
            channel="telegram",
            external_message_id=parsed["external_message_id"],
            content=parsed["text"],
            status="delivered",
            error_message=None,
        )
        try:
            log.message_role = "user"
        except Exception:
            pass
        db.add(log)
        db.commit()
    finally:
        db.close()


async def _trigger_batch(user_id: int, external_id: str) -> None:
    """Trigger batch processing for user."""
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        existing = db.query(BatchLock).filter(
            BatchLock.user_id == user_id,
            BatchLock.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
        ).first()
        if not existing:
            lock = BatchLock(
                user_id=user_id,
                channel="telegram",
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=3),
            )
            db.add(lock)
            db.commit()
            asyncio.create_task(_import_and_process(user_id, external_id))
    finally:
        db.close()


async def _import_and_process(user_id: int, external_id: str) -> None:
    """Import and run batch processing (avoid circular import)."""
    from src.integrations.telegram import process_telegram_batch
    await process_telegram_batch(user_id, external_id)


async def _is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to interact."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        if not user:
            return True
        restricted = bool(getattr(user, "processing_restricted", False))
        deleted = bool(getattr(user, "is_deleted", False))
        opted_in = bool(getattr(user, "opted_in", True))
        return not (restricted or deleted or opted_in is False)
    finally:
        db.close()


async def process_update(update: dict) -> None:
    """Process a single Telegram update."""
    update_id = update.get("update_id")
    if update_id in _processed_updates:
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    parsed = TelegramHandler.parse_webhook(update)
    if not parsed:
        return

    user_id_str = parsed["user_id"]
    text = parsed["text"]
    chat_id = int(parsed["chat_id"])

    logger.info(f"[polling] Message from {user_id_str}: {text[:30]}...")

    # Send typing indicator immediately
    await send_typing_action(chat_id)

    # Ensure user exists
    first_name = message.get("from", {}).get("first_name")
    last_name = message.get("from", {}).get("last_name")
    db_user_id = await _ensure_user(user_id_str, first_name, last_name)

    if db_user_id is None:
        return

    # Check restrictions
    if not await _is_user_allowed(db_user_id):
        _processed_updates.add(update_id)
        return

    # Log message
    await _log_message(db_user_id, parsed)

    # Mark processed
    _processed_updates.add(update_id)

    # Trigger batch processing
    await _trigger_batch(db_user_id, user_id_str)


async def start_polling() -> None:
    """Main polling loop."""
    logger.info("[polling] Starting Telegram long-polling...")
    offset = 0

    while True:
        try:
            updates = await poll_updates(offset)

            for update in updates:
                await process_update(update)
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1

            # Cleanup old processed updates
            if len(_processed_updates) > 1000:
                sorted_updates = sorted(_processed_updates)
                _processed_updates.clear()
                _processed_updates.update(sorted_updates[:1000])

        except Exception as e:
            logger.error(f"[polling] Error: {e}")
            await asyncio.sleep(5)


def start_polling_task() -> Optional[asyncio.Task]:
    """Start polling as background task."""
    if not settings.USE_TELEGRAM_LONG_POLLING:
        return None
    return asyncio.create_task(start_polling())

