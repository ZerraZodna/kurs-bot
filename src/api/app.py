from fastapi import FastAPI, Request
from src.services.memory_manager import MemoryManager

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
