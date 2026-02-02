from fastapi import FastAPI, Request, HTTPException
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, User, MessageLog
from src.config import settings
from src.integrations.telegram import TelegramHandler, send_message
from src.services.dialogue_engine import DialogueEngine
from src.api.dialogue_routes import router as dialogue_router
import threading
import time
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import httpx

app = FastAPI()

# Include dialogue routes with context-aware endpoints
app.include_router(dialogue_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


async def process_telegram_batch(user_id: int, external_id: str) -> None:
    """Batch inbound messages for a user and send one AI response."""
    await asyncio.sleep(1.0)

    message_ids = []
    combined_text = ""

    db = SessionLocal()
    try:
        unprocessed = db.query(MessageLog).filter(
            MessageLog.user_id == user_id,
            MessageLog.direction == "inbound",
            MessageLog.status == "delivered",
        ).order_by(MessageLog.created_at).all()

        if not unprocessed:
            db.close()
            return

        message_ids = [m.message_id for m in unprocessed]
        combined_text = "\n".join([m.content for m in unprocessed if m.content])

        # Claim messages
        db.query(MessageLog).filter(
            MessageLog.message_id.in_(message_ids)
        ).update({MessageLog.status: "processing"}, synchronize_session=False)
        db.commit()
        db.close()
    except Exception as e:
        print("[batch collection error]", e)
        db.close()
        return

    # Generate AI response
    db = SessionLocal()
    dialogue = DialogueEngine(db)
    ai_response = await dialogue.process_message(
        user_id=user_id,
        text=combined_text,
        session=db,
        include_history=True,
        history_turns=4,
    )
    db.close()

    # Send response back to user
    await send_message(int(external_id), ai_response)

    # Log outbound and mark processed
    try:
        db = SessionLocal()
        log = MessageLog(
            user_id=user_id,
            direction="outbound",
            channel="telegram",
            external_message_id=None,
            content=ai_response,
            status="sent",
            error_message=None
        )
        try:
            log.message_role = "assistant"
        except Exception:
            pass
        db.add(log)
        db.commit()

        db.query(MessageLog).filter(
            MessageLog.message_id.in_(message_ids)
        ).update({MessageLog.status: "processed"}, synchronize_session=False)
        db.commit()
        db.close()
    except Exception as e:
        print("[messagelog outbound error]", e)


@app.post("/webhook/telegram/{secret_token}")
async def telegram_webhook(request: Request, secret_token: str):
    # Validate secret token from config
    if secret_token != settings.TELEGRAM_BOT_TOKEN.split(":")[1]:
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = await request.json()
    # Use TelegramHandler to normalize
    parsed = TelegramHandler.parse_webhook(payload)
    if not parsed:
        return {"ok": False, "reason": "Not a valid Telegram message"}
    # Log to console
    print("[telegram webhook]", parsed)

    # --- Add or update user in DB ---
    uid = parsed["user_id"]
    text = parsed["text"]
    first_name = payload.get("message", {}).get("from", {}).get("first_name")
    last_name = payload.get("message", {}).get("from", {}).get("last_name")

    db = SessionLocal()
    db_user = db.query(User).filter_by(external_id=str(uid), channel="telegram").first()
    if not db_user:
        db_user = User(
            external_id=str(uid),
            channel="telegram",
            first_name=first_name,
            last_name=last_name,
            opted_in=True
        )
        db.add(db_user)
        db.commit()
        print(f"[user added] {uid} {first_name} {last_name}")
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
            print(f"[user updated] {uid} {first_name} {last_name}")
    # Extract user_id before closing session
    user_id = db_user.user_id if db_user else db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id
    db.close()

    # Log all incoming messages to MessageLog
    try:
        db = SessionLocal()
        user_id = db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id if uid else None
        log = MessageLog(
            user_id=user_id,
            direction="inbound",
            channel="telegram",
            external_message_id=parsed["external_message_id"],
            content=text,
            status="delivered",
            error_message=None
        )
        # Only set new columns if they exist (migration applied)
        try:
            log.message_role = "user"
        except:
            pass
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        print("[messagelog error]", e)

    # Schedule background batch processing to allow more messages to arrive
    try:
        db = SessionLocal()
        memory_manager = MemoryManager(db)
        lock = memory_manager.get_memory(user_id, "batch_lock")
        if not lock:
            memory_manager.store_memory(
                user_id=user_id,
                key="batch_lock",
                value="locked",
                category="conversation",
                ttl_hours=0.01,  # ~36 seconds
                source="webhook",
                allow_duplicates=False,
            )
            asyncio.create_task(process_telegram_batch(user_id, uid))
        db.close()
    except Exception as e:
        print("[batch lock error]", e)

    return {"ok": True}


# --- Add a background thread to purge old messages from MessageLog daily ---
def purge_old_messages():
    while True:
        try:
            db = SessionLocal()
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            deleted = db.query(MessageLog).filter(MessageLog.created_at < cutoff).delete()
            if deleted:
                print(f"[purge] Deleted {deleted} old messages from MessageLog.")
            db.commit()
            db.close()
        except Exception as e:
            print(f"[purge error] {e}")
        time.sleep(24 * 60 * 60)  # Run once per day


def purge_inactive_memories(days_keep: int = 60):
    """Purge archived/inactive memories older than days_keep (UTC)."""
    try:
        db = SessionLocal()
        memory_manager = MemoryManager(db)
        deleted = memory_manager.purge_expired(days_keep=days_keep)
        if deleted:
            print(f"[purge] Deleted {deleted} archived memories older than {days_keep} days.")
        db.close()
    except Exception as e:
        print(f"[purge error] {e}")


def nightly_memory_purge(days_keep: int = 60, hour_utc: int = 2):
    """Run memory purge at startup and then nightly at a fixed UTC hour."""
    # Run immediately at startup
    purge_inactive_memories(days_keep=days_keep)

    while True:
        try:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            sleep_seconds = (next_run - now).total_seconds()
            time.sleep(sleep_seconds)
            purge_inactive_memories(days_keep=days_keep)
        except Exception as e:
            print(f"[purge error] {e}")
            time.sleep(60)

# Start the purge thread when the app starts
@app.on_event("startup")
def start_purge_thread():
    t = threading.Thread(target=purge_old_messages, daemon=True)
    t.start()

    t2 = threading.Thread(target=nightly_memory_purge, daemon=True)
    t2.start()

    return {"ok": True}

@app.on_event("startup")
def startup_info():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    ollama_url = "http://localhost:11434"
    try:
        # Try to GET /api/tags as a lightweight check
        response = httpx.get(f"{ollama_url}/api/tags", timeout=2.0)
        if response.status_code == 200:
            logging.info(f"Ollama AI server is running at {ollama_url} (model: {settings.OLLAMA_MODEL})")
        else:
            logging.warning(f"Ollama AI server responded with status {response.status_code} at {ollama_url}")
    except Exception as e:
        logging.error(f"Ollama AI server is NOT reachable at {ollama_url}: {e}")
