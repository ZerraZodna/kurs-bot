from fastapi import FastAPI, Request
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, User

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

    # Store incoming message to prototype MemoryManager (short TTL)
    try:
        if user and isinstance(user, dict):
            uid = user.get("id") or user.get("user_id")
        else:
            uid = None
        if uid and text:
            try:
                mm = MemoryManager()
                mm.store_memory(int(uid), 'last_message', text, confidence=1.0, source='telegram', ttl_hours=24)
            except Exception as e:
                print("[memory store error]", e)
    except Exception as e:
        print("[memory manager error]", e)

    return {"ok": True}
