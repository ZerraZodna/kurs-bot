from fastapi import FastAPI, Request, HTTPException
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, User, MessageLog
from src.config import settings
from src.integrations.telegram import TelegramHandler, send_message
from src.services.dialogue_engine import DialogueEngine
import threading
import time
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import httpx

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


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
    db.close()

    # Log all incoming messages to MessageLog
    try:
        db = SessionLocal()
        log = MessageLog(
            user_id=db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id if uid else None,
            direction="inbound",
            channel="telegram",
            external_message_id=parsed["external_message_id"],
            content=text,
            status="delivered",
            error_message=None
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        print("[messagelog error]", e)

    # --- AI: Get response from DialogueEngine and send back to Telegram ---
    db = SessionLocal()
    dialogue = DialogueEngine()
    ai_response = await dialogue.process_message(db_user.user_id, text, db)
    db.close()
    # Send response back to user
    await send_message(int(uid), ai_response)

    # Log outbound message
    try:
        db = SessionLocal()
        log = MessageLog(
            user_id=db_user.user_id,
            direction="outbound",
            channel="telegram",
            external_message_id=None,
            content=ai_response,
            status="sent",
            error_message=None
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        print("[messagelog outbound error]", e)

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

# Start the purge thread when the app starts
@app.on_event("startup")
def start_purge_thread():
    t = threading.Thread(target=purge_old_messages, daemon=True)
    t.start()

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
