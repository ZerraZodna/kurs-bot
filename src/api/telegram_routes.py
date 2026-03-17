import asyncio
import logging
import time

# from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import OperationalError

from src.config import settings
from src.core.timezone import utc_now, utc_now_plus
from src.integrations.telegram import TelegramHandler, process_telegram_batch
from src.models.database import BatchLock, MessageLog, SessionLocal, User, get_session
from src.services.admin_notifier import send_admin_notification, set_admin_chat_id
from src.services.traffic_tracker import record_traffic_event

logger = logging.getLogger(__name__)

router = APIRouter()


def _retry_db_op(op_name: str, func, attempts: int = 3, delay_seconds: float = 1.0):
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except OperationalError as e:
            if attempt == attempts:
                logger.error(f"[{op_name} error] {e}")
                return None
            time.sleep(delay_seconds * attempt)


@router.post("/webhook/telegram/{secret_token}")  # Webhook route - unused with polling (ngrok unsupported)"
async def telegram_webhook(request: Request, secret_token: str):
    # Validate secret token from config
    if secret_token != settings.TELEGRAM_BOT_TOKEN.split(":")[1]:
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = await request.json()
    admin_username = (settings.ADMIN_TELEGRAM_USERNAME or "").lstrip("@").strip().lower()
    if admin_username:
        from_user = payload.get("message", {}).get("from", {})
        if (from_user.get("username") or "").lower() == admin_username:
            chat_id = payload.get("message", {}).get("chat", {}).get("id")
            if chat_id:
                set_admin_chat_id(int(chat_id))
    # Use TelegramHandler to normalize
    parsed = TelegramHandler.parse_webhook(payload)
    if not parsed:
        return {"ok": False, "reason": "Not a valid Telegram message"}
    logger.info(
        "[telegram webhook] user_id=%s message_id=%s channel=telegram",
        parsed.get("user_id"),
        parsed.get("external_message_id"),
    )

    # --- Add or update user in DB ---
    uid = parsed["user_id"]
    text = parsed["text"]
    first_name = payload.get("message", {}).get("from", {}).get("first_name")
    last_name = payload.get("message", {}).get("from", {}).get("last_name")

    with get_session() as db:
        db_user = db.query(User).filter_by(external_id=str(uid), channel="telegram").first()
        if not db_user:
            db_user = User(
                external_id=str(uid), channel="telegram", first_name=first_name, last_name=last_name, opted_in=True
            )
            db.add(db_user)
            db.commit()
            logger.info(f"[user added] {uid} {first_name} {last_name}")
            name = " ".join([n for n in [first_name, last_name] if n]) or str(uid)
            send_admin_notification(f"[INFO] New user joined: {name}.")
        else:
            updated = False
            if first_name and db_user.first_name != first_name:
                db_user.first_name = first_name
                updated = True
            if last_name and db_user.last_name != last_name:
                db_user.last_name = last_name
                updated = True
            if updated:
                db.commit()
                logger.info(f"[user updated] {uid} {first_name} {last_name}")
        user_id = db_user.user_id
        processing_restricted = bool(getattr(db_user, "processing_restricted", False))
        is_deleted = bool(getattr(db_user, "is_deleted", False))
        is_opted_in = bool(getattr(db_user, "opted_in", True))

    if processing_restricted or is_deleted or not is_opted_in:
        return {"ok": True, "restricted": True}

    # Log all incoming messages to MessageLog with retry
    def _log_message():
        with get_session() as db:
            uid_inner = (
                db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id if uid else None
            )
            log = MessageLog(
                user_id=uid_inner,
                direction="inbound",
                channel="telegram",
                external_message_id=parsed["external_message_id"],
                content=text,
                status="delivered",
                error_message=None,
            )
            # Only set new columns if they exist (migration applied)
            try:
                log.message_role = "user"
            except Exception:
                pass
            db.add(log)
            db.commit()

    _retry_db_op("messagelog", _log_message, attempts=3, delay_seconds=0.1)

    record_traffic_event()

    # Schedule background batch processing to allow more messages to arrive
    def _create_batch_lock():
        with get_session() as db:
            # Check if lock already exists and is still valid
            existing_lock = (
                db.query(BatchLock).filter(BatchLock.user_id == user_id, BatchLock.expires_at > utc_now()).first()
            )

            if not existing_lock:
                # Create new lock (3 minute TTL)
                lock = BatchLock(user_id=user_id, channel="telegram", expires_at=utc_now_plus(minutes=3))
                db.add(lock)
                db.commit()
                asyncio.create_task(process_telegram_batch(user_id, uid))

    _retry_db_op("batch lock", _create_batch_lock, attempts=3, delay_seconds=0.1)

    return {"ok": True}
