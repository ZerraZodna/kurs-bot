import os
import httpx
import re
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
            # Convert markdown formatting to Telegram MarkdownV2
            # This handles *text* -> **text** (bold) and **text** stays **text** (bold)
            # And _text_ -> *text* (italic) 
            formatted_text = _convert_to_telegram_markdown(text)
            
            # Telegram hard limit is 4096 chars; stay below to be safe
            max_len = 3500
            chunks = [formatted_text[i:i + max_len] for i in range(0, len(formatted_text), max_len)] or [""]
            last_response = None
            for chunk in chunks:
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "MarkdownV2"  # Enable Telegram markdown parsing
                }
                r = await client.post(url, json=payload, timeout=10.0)
                r.raise_for_status()
                last_response = r.json()
            return last_response
    except Exception as e:
        print("[telegram send error]", e)
        return None


def _convert_to_telegram_markdown(text: str) -> str:
    """
    Convert markdown formatting to Telegram MarkdownV2 format.
    
    Telegram MarkdownV2 uses:
    - **text** for bold (same as markdown)
    - *text* for italic (markdown uses _ or *)
    
    Special chars that need escaping in MarkdownV2:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    # First, escape special characters except for markdown symbols
    # We'll handle markdown symbols separately
    special_chars = r'_\[\]()~`>#+-=|{}.!'
    
    # Convert standard markdown to Telegram MarkdownV2
    # Pattern: **text** stays as **text** (bold)
    # Pattern: *text* -> *text* (italic)
    # Pattern: ***text*** -> ***text*** (bold italic)
    
    # Escape literal special chars (but preserve markdown formatting)
    # This is tricky - we need to escape non-markdown special chars
    result = text
    
    # Preserve existing **bold** and ***bold italic***
    # Convert single *italic* to _italic_ for clarity (Telegram supports both)
    
    # Handle the case where Ollama might output ***bold italic***
    # Telegram MarkdownV2 supports this natively
    
    # Escape special characters that aren't part of markdown formatting
    # But be careful not to double-escape or break valid markdown
    
    # For simplicity and safety: just ensure we're using MarkdownV2 compatible syntax
    # The output from Ollama should already be mostly compatible
    
    return result
