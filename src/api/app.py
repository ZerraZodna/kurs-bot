from fastapi import FastAPI, Request, HTTPException
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, User, MessageLog
from src.config import settings
from src.integrations.telegram import TelegramHandler
import threading
import time
from datetime import datetime, timedelta, timezone

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
