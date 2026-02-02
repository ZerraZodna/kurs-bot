import os
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from src.config import settings

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

class TelegramHandler:
    @staticmethod
    def parse_webhook(request: dict) -> Optional[Dict[str, Any]]:
        # Handles both message and edited_message
        msg = request.get("message") or request.get("edited_message")
        if not msg:
            return None
        user = msg.get("from")
        if not user or not msg.get("text"):
            return None
        # Ignore bot commands (optional)
        text = msg.get("text")
        if text.startswith("/"):
            return None
        return {
            "user_id": str(user.get("id")),
            "channel": "telegram",
            "text": text,
            "external_message_id": str(msg.get("message_id")),
            "timestamp": datetime.utcfromtimestamp(msg.get("date", 0)),
        }

async def send_message(chat_id: int, text: str) -> Optional[dict]:
    if not TELEGRAM_BOT_TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN not set")
        return None
    url = f"{API_BASE}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            # Telegram hard limit is 4096 chars; stay below to be safe
            max_len = 3500
            chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)] or [""]
            last_response = None
            for chunk in chunks:
                payload = {"chat_id": chat_id, "text": chunk}
                r = await client.post(url, json=payload, timeout=10.0)
                r.raise_for_status()
                last_response = r.json()
            return last_response
    except Exception as e:
        print("[telegram send error]", e)
        return None
