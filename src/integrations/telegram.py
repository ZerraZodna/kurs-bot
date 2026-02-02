import os
import httpx
from typing import Optional

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(chat_id: int, text: str) -> Optional[dict]:
    if not TELEGRAM_BOT_TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN not set")
        return None
    url = f"{API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, timeout=10.0)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print("[telegram send error]", e)
        return None
