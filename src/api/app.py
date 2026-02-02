from fastapi import FastAPI, Request
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, User, MessageLog

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    payload = await request.json()
    # Minimal normalization placeholder
    user = payload.get("message", {}).get("from", {}) or payload.get("from")
    text = payload.get("message", {}).get("text") if payload.get("message") else payload.get("text")
    # Log to console
    print("[telegram webhook]", user, text)

    # --- Add or update user in DB ---
    if user and isinstance(user, dict):
        uid = user.get("id") or user.get("user_id")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        username = user.get("username")
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
            # Optionally update names if changed
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
        if user and isinstance(user, dict):
            uid = user.get("id") or user.get("user_id")
        else:
            uid = None
        if uid and text:
            db = SessionLocal()
            log = MessageLog(
                user_id=db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id if uid else None,
                direction="inbound",
                channel="telegram",
                external_message_id=str(payload.get("message", {}).get("message_id", "")),
                content=text,
                status="delivered",
                error_message=None
            )
            db.add(log)
            db.commit()
            db.close()
    except Exception as e:
        print("[messagelog error]", e)

    # Optionally: store to MemoryManager only if important fact (placeholder, not storing every message)
    # Uncomment and adjust the following if you want to store only certain messages as memories:
    # try:
    #     if uid and text and is_important_fact(text):
    #         mm = MemoryManager()
    #         mm.store_memory(int(uid), 'important_fact', text, confidence=1.0, source='telegram')
    # except Exception as e:
    #     print("[memory store error]", e)
import schedule
import threading
import time
from datetime import datetime, timedelta, timezone
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
