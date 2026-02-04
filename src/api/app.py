from fastapi import FastAPI, Request, HTTPException
from src.services.memory_manager import MemoryManager
from src.services.maintenance import run_daily_maintenance
from src.models.database import SessionLocal, User, MessageLog, BatchLock
from src.config import settings
from src.integrations.telegram import TelegramHandler, send_message
from src.services.dialogue_engine import DialogueEngine
from src.api.dialogue_routes import router as dialogue_router
from src.api.gdpr_routes import router as gdpr_router
import threading
import time
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import httpx
from sqlalchemy.exc import OperationalError

app = FastAPI()

# Include dialogue routes with context-aware endpoints
app.include_router(dialogue_router)
app.include_router(gdpr_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


async def process_telegram_batch(user_id: int, external_id: str) -> None:
    """Batch inbound messages for a user and send one AI response."""
    await asyncio.sleep(1.0)

    try:
        for _ in range(3):
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
                    break

                if len(unprocessed) > 1:
                    print(f"[batch] Combining {len(unprocessed)} messages from user {user_id}")

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
                break

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
                break

            await asyncio.sleep(0.5)
    finally:
        # Release batch lock by deleting from table
        try:
            db = SessionLocal()
            db.query(BatchLock).filter_by(user_id=user_id).delete(synchronize_session=False)
            db.commit()
            db.close()
        except Exception as e:
            print("[batch lock release error]", e)


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
    processing_restricted = bool(getattr(db_user, "processing_restricted", False)) if db_user else False
    is_deleted = bool(getattr(db_user, "is_deleted", False)) if db_user else False
    is_opted_in = bool(getattr(db_user, "opted_in", True)) if db_user else True
    db.close()

    if processing_restricted or is_deleted or not is_opted_in:
        return {"ok": True, "restricted": True}

    # Log all incoming messages to MessageLog with retry
    def _log_message():
        db = SessionLocal()
        try:
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
        finally:
            db.close()
    
    try:
        _retry_db_op("messagelog", _log_message, attempts=3, delay_seconds=0.1)
    except Exception as e:
        print("[messagelog error]", e)

    # Schedule background batch processing to allow more messages to arrive
    def _create_batch_lock():
        db = SessionLocal()
        try:
            # Check if lock already exists and is still valid
            existing_lock = db.query(BatchLock).filter(
                BatchLock.user_id == user_id,
                BatchLock.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if not existing_lock:
                # Create new lock (3 minute TTL)
                lock = BatchLock(
                    user_id=user_id,
                    channel="telegram",
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=3)
                )
                db.add(lock)
                db.commit()
                asyncio.create_task(process_telegram_batch(user_id, uid))
        finally:
            db.close()
    
    try:
        _retry_db_op("batch lock", _create_batch_lock, attempts=3, delay_seconds=0.1)
    except Exception as e:
        print("[batch lock error]", e)

    return {"ok": True}


# --- Add a background thread to purge old messages from MessageLog daily ---
def _retry_db_op(op_name: str, func, attempts: int = 3, delay_seconds: float = 1.0):
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except OperationalError as e:
            if attempt == attempts:
                print(f"[{op_name} error] {e}")
                return None
            time.sleep(delay_seconds * attempt)


def purge_old_messages(hour_utc: int = 2):
    """Purge old messages at maintenance time (02:00 UTC). Skip first run on startup."""
    first_run = True
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            # Skip purge on first startup to avoid conflicts
            if not first_run:
                sleep_seconds = (next_run - now).total_seconds()
                time.sleep(sleep_seconds)
                
                def _do_purge():
                    db = SessionLocal()
                    try:
                        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                        deleted = db.query(MessageLog).filter(MessageLog.created_at < cutoff).delete()
                        if deleted:
                            print(f"[purge] Deleted {deleted} old messages from MessageLog.")
                        db.commit()
                    finally:
                        db.close()

                _retry_db_op("purge", _do_purge)
            else:
                # First run: calculate sleep to next 02:00 UTC without running
                sleep_seconds = (next_run - now).total_seconds()
                print(f"[purge] Next message purge scheduled at {next_run.isoformat()}")
                time.sleep(sleep_seconds)
            
            first_run = False
        except Exception as e:
            print(f"[purge error] {e}")
            time.sleep(60)


def purge_expired_batch_locks():
    """Remove expired batch locks from the database."""
    try:
        def _do_purge():
            db = SessionLocal()
            try:
                deleted = db.query(BatchLock).filter(
                    BatchLock.expires_at < datetime.now(timezone.utc)
                ).delete(synchronize_session=False)
                if deleted:
                    print(f"[purge] Deleted {deleted} expired batch locks.")
                db.commit()
            finally:
                db.close()

        _retry_db_op("batch lock purge", _do_purge)
    except Exception as e:
        print(f"[batch lock purge error] {e}")


def nightly_memory_purge(days_keep: int = 60, hour_utc: int = 2):
    """Run maintenance at fixed UTC hour (02:00 AM). Skip first run on startup."""
    first_run = True
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            # Skip purge on first startup to avoid conflicts with normal operations
            if not first_run:
                sleep_seconds = (next_run - now).total_seconds()
                time.sleep(sleep_seconds)
                run_daily_maintenance(days_keep=days_keep)
                purge_expired_batch_locks()
            else:
                # First run: just schedule for next maintenance window
                sleep_seconds = (next_run - now).total_seconds()
                print(f"[purge] Scheduled nightly maintenance at {next_run.isoformat()}")
                time.sleep(sleep_seconds)
            
            first_run = False
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
