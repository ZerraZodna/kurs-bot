import os
import httpx
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
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
            "timestamp": datetime.fromtimestamp(msg.get("date", 0), timezone.utc),
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
            chunks = _split_text(text, max_len) or [""]
            last_response = None
            for chunk in chunks:
                html_chunk = _markdown_to_html(chunk)
                payload = {
                    "chat_id": chat_id,
                    "text": html_chunk,
                    "parse_mode": "HTML"  # Use HTML instead of MarkdownV2
                }
                try:
                    r = await client.post(url, json=payload, timeout=10.0)
                    r.raise_for_status()
                    last_response = r.json()
                except httpx.HTTPStatusError as e:
                    # Fallback: send plain text without parse_mode to avoid HTML errors
                    if e.response is not None and e.response.status_code == 400:
                        fallback_payload = {
                            "chat_id": chat_id,
                            "text": chunk
                        }
                        r = await client.post(url, json=fallback_payload, timeout=10.0)
                        r.raise_for_status()
                        last_response = r.json()
                    else:
                        raise
            return last_response
    except Exception as e:
        print("[telegram send error]", e)
        return None


def _markdown_to_html(text: str) -> str:
    """
    Convert markdown formatting to HTML for Telegram.
    
    Converts:
    - # Heading 1 -> <b>Heading 1</b> (bold with newlines)
    - ## Heading 2 -> <b>Heading 2</b> (bold with newlines)
    - ### Heading 3 -> <b>Heading 3</b> (bold with newlines)
    - **text** -> <b>text</b> (bold)
    - *text* -> <i>text</i> (italic)
    - ***text*** -> <b><i>text</i></b> (bold italic)
    - `text` -> <code>text</code> (code)
    - [text](url) -> <a href="url">text</a> (links)
    """
    # Escape HTML-sensitive characters first to avoid invalid HTML
    text = _escape_html(text)

    # Order matters: process longest patterns first to avoid conflicts
    
    # 0. Headings (must be done FIRST before bold processing)
    # ### Heading -> <b>Heading</b> with newlines
    text = re.sub(r'^### (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    
    # 1. Bold italic: ***text*** -> <b><i>text</i></b>
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    
    # 2. Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # 3. Italic: *text* -> <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    
    # 4. Code: `text` -> <code>text</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    # 5. Links: [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    
    return text


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _split_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks
