import asyncio
import httpx
import logging
import re
import time
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime, timedelta, timezone
from src.config import settings
from src.models.database import SessionLocal, MessageLog, BatchLock

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def sanitize_html_for_telegram(text: str) -> str:
    """Sanitize HTML to Telegram-supported format.
    
    Converts unsupported tags (<ul>, <li>, <br>) to plain text
    while preserving supported formatting tags (<b>, <i>, <em>, <u>, etc).
    
    Telegram supports: <b>, <strong>, <i>, <em>, <u>, <s>, <code>, <pre>, <a>
    Unsupported (converted): <ul>, <li>, <br>
    """
    if not text:
        return text
    
    # Step 1: Convert <ul><li> items to bullet points with dashes
    # First handle <li> content and prepend with dash
    text = re.sub(r'<li>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)
    # Remove <ul> tags
    text = re.sub(r'</?ul[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Step 2: Convert <br> to newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # Step 3: Strip unsupported HTML tags but keep their content
    text = _strip_unsupported_tags(text)
    
    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def _strip_unsupported_tags(text: str) -> str:
    """Remove HTML tags that Telegram doesn't support, keeping their content."""
    # List of tags Telegram supports
    supported_tags = ['b', 'strong', 'i', 'em', 'u', 's', 'code', 'pre', 'a']
    
    # Pattern to match any tag not in supported list
    # This matches <tag> or </tag> where tag is not in supported list
    def replace_tag(match):
        # Return just the content between tags
        return match.group(1) or ''
    
    # Match opening tags with content: <unsupported>content</unsupported>
    pattern = r'<(/?)(?!/?(?:' + '|'.join(supported_tags) + r')\b)(\w+)[^>]*>([^<]*)'
    
    # Use a different approach: find each tag and check if supported
    result = []
    i = 0
    while i < len(text):
        if text[i] == '<':
            # Find the end of the tag
            end = text.find('>', i)
            if end == -1:
                result.append(text[i])
                i += 1
                continue
            
            tag = text[i:end+1]
            
            # Check if it's a closing tag
            is_closing = tag.startswith('</')
            
            # Extract tag name
            tag_name = re.sub(r'[</>]', '', tag).lower()
            # Handle self-closing tags and attributes
            tag_name = re.split(r'[\s>]', tag_name)[0]
            
            if tag_name in supported_tags:
                # Keep the tag
                result.append(tag)
            else:
                # Skip the tag but keep content (handled separately)
                pass
            
            i = end + 1
        else:
            result.append(text[i])
            i += 1
    
    return ''.join(result)


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
            "chat_id": str(msg.get("chat", {}).get("id")),
            "timestamp": datetime.fromtimestamp(msg.get("date", 0), timezone.utc),
        }

async def edit_message(chat_id: int, message_id: int, text: str) -> Optional[dict]:
    """Edit an existing Telegram message with new text."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    
    # Sanitize HTML to Telegram-supported format
    text = sanitize_html_for_telegram(text)
    
    url = f"{API_BASE}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=10.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            resp = e.response
            # Telegram returns 400 if the text hasn't actually changed — ignore
            if resp is not None and resp.status_code == 400:
                body = ""
                try:
                    body = resp.text
                except Exception:
                    pass
                if "message is not modified" in body.lower():
                    return None
                # Fallback: send plain text without parse_mode
                fallback = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                }
                try:
                    r = await client.post(url, json=fallback, timeout=10.0)
                    r.raise_for_status()
                    return r.json()
                except Exception:
                    return None
            logger.warning("[telegram] editMessageText error %s", e)
            return None
        except Exception as e:
            logger.warning("[telegram] editMessageText exception: %s", e)
            return None


async def send_message_streaming(
    chat_id: int,
    token_generator: AsyncIterator[str],
    min_update_interval: float = None,
) -> tuple[str, Optional[int]]:
    """Stream tokens to Telegram by sending an initial message then editing it.

    Args:
        chat_id: Telegram chat ID.
        token_generator: Async iterator yielding text chunks from the LLM.
        min_update_interval: Minimum seconds between edits (defaults to config).

    Returns:
        (full_text, message_id) — the complete accumulated text and the
        Telegram message_id that was created/edited.
    """
    if min_update_interval is None:
        min_update_interval = getattr(settings, "TELEGRAM_STREAM_UPDATE_INTERVAL", 1.0)

    accumulated = ""
    message_id: Optional[int] = None
    last_edit_time: float = 0.0
    last_sent_text: str = ""
    _tg_start = time.monotonic()

    # We use a typing indicator "⏳" as the initial placeholder
    PLACEHOLDER = "⏳"

    async for token in token_generator:
        accumulated += token

        now = time.monotonic()
        elapsed = now - last_edit_time

        if elapsed >= min_update_interval and accumulated != last_sent_text:
            if message_id is None:
                # Send the first message
                logger.info(
                    "[telegram_stream] FIRST sendMessage at t=+%.3fs with %d chars",
                    now - _tg_start,
                    len(accumulated),
                )
                result = await send_message(chat_id, accumulated or PLACEHOLDER)
                if result and result.get("ok") and result.get("result"):
                    message_id = result["result"].get("message_id")
                last_sent_text = accumulated
            else:
                logger.info(
                    "[telegram_stream] editMessage at t=+%.3fs with %d chars",
                    now - _tg_start,
                    len(accumulated),
                )
                # Edit the existing message
                await edit_message(chat_id, message_id, accumulated)
                last_sent_text = accumulated
            last_edit_time = time.monotonic()

    # Final edit with the complete text (if it changed since last edit)
    if accumulated and accumulated != last_sent_text:
        if message_id is None:
            result = await send_message(chat_id, accumulated)
            if result and result.get("ok") and result.get("result"):
                message_id = result["result"].get("message_id")
        else:
            await edit_message(chat_id, message_id, accumulated)

    return accumulated, message_id


async def send_message(chat_id: int, text: str) -> Optional[dict]:
    if not TELEGRAM_BOT_TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN not set")
        return None
    
    # Sanitize HTML to Telegram-supported format
    text = sanitize_html_for_telegram(text)
    
    url = f"{API_BASE}/sendMessage"
    async with httpx.AsyncClient() as client:
        # Telegram hard limit is 4096 chars; stay below to be safe
        max_len = 3500
        chunks = _split_text(text, max_len) or [""]
        last_response = None
        for chunk in chunks:
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML"  # Use HTML instead of MarkdownV2
            }
            try:
                r = await client.post(url, json=payload, timeout=10.0)
                r.raise_for_status()
                last_response = r.json()
            except httpx.HTTPStatusError as e:
                # Log details for easier debugging
                resp = e.response
                body = None
                try:
                    body = resp.text if resp is not None else None
                except Exception:
                    body = None
                print(f"[telegram] HTTPStatusError {getattr(resp, 'status_code', None)}; body={body}")
                # Fallback: send plain text without parse_mode to avoid HTML errors
                if resp is not None and resp.status_code == 400:
                    fallback_payload = {
                        "chat_id": chat_id,
                        "text": chunk
                    }
                    r = await client.post(url, json=fallback_payload, timeout=10.0)
                    r.raise_for_status()
                    last_response = r.json()
                else:
                    # Let the caller see the exception so they can mark the send as failed
                    raise
        return last_response


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


async def process_telegram_batch(user_id: int, external_id: str) -> None:
    """Batch inbound messages for a user and send one AI response.

    When streaming is enabled (``OLLAMA_STREAM_ENABLED``), LLM-generated
    responses are streamed token-by-token to Telegram via progressive
    message edits.  Non-LLM responses (commands, onboarding, lessons, etc.)
    are sent normally as a single message.
    """
    from src.services.dialogue_engine import DialogueEngine
    from src.services.traffic_tracker import record_traffic_event
    from src.services.dialogue import extract_and_store_memories

    await asyncio.sleep(1.0)

    stream_enabled = getattr(settings, "OLLAMA_STREAM_ENABLED", True)
    logger.info(f"[batch] stream_enabled={stream_enabled} for user_id={user_id}")

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

            # Generate AI response — streaming or non-streaming
            chat_id = int(external_id)
            ai_response: str

            if stream_enabled:
                db = SessionLocal()
                dialogue = DialogueEngine(db)
                result = await dialogue.process_message_for_telegram(
                    user_id=user_id,
                    text=combined_text,
                    session=db,
                    chat_id=chat_id,
                    include_history=True,
                    history_turns=4,
                )
                db.close()

                if result["type"] == "stream":
                    # Stream tokens to Telegram via progressive edits
                    logger.info(f"[batch] Using STREAMING path for user_id={user_id}")
                    
                    # Accumulate full response first to avoid sending JSON to user
                    full_response = ""
                    async for token in result["generator"]:
                        full_response += token
                    
                    logger.info(f"[batch] Accumulated full_response: {full_response[:200]}...")
                    
                    if not full_response:
                        ai_response = "[No response from LLM]"
                        await send_message(chat_id, ai_response)
                    else:
                        # Extract just the response text if the response contains JSON
                        extract_text_fn = result.get("extract_text")
                        if extract_text_fn:
                            ai_response = extract_text_fn(full_response)
                        else:
                            ai_response = full_response
                        
                        logger.info(f"[batch] Extracted ai_response: {ai_response[:200] if ai_response else 'EMPTY'}...")
                        
                        # Run post-response hooks FIRST to check for function calls
                        # This prevents duplicate messages when functions are executed
                        function_response_text = None
                        has_function_results = False
                        try:
                            diagnostics = await result["post_hook"](full_response)
                            # Check if there are function execution results to send
                            if diagnostics and diagnostics.get("execution_result"):
                                from src.functions.response_builder import get_response_builder
                                from src.functions.intent_parser import get_intent_parser
                                
                                response_builder = get_response_builder()
                                parser = get_intent_parser()
                                parse_result = parser.parse(full_response)
                                
                                built_response = response_builder.build(
                                    user_text=combined_text,
                                    ai_response_text=parse_result.response_text if parse_result.response_text is not None else full_response,
                                    execution_result=diagnostics["execution_result"],
                                    include_function_results=True,
                                )
                                function_response_text = built_response.text
                                has_function_results = True
                        except Exception as e:
                            print(f"[stream post_hook error] {e}")
                        
                        # If we have function results, send the combined response once
                        # Otherwise, send just the AI text (to avoid duplication)
                        if has_function_results and function_response_text and function_response_text.strip():
                            await send_message(chat_id, function_response_text)
                        elif ai_response and ai_response.strip():
                            await send_message(chat_id, ai_response)
                else:
                    # Non-LLM response — send normally
                    logger.info(f"[batch] Using NON-STREAMING (text) path for user_id={user_id}")
                    ai_response = result["text"]
                    await send_message(chat_id, ai_response)
            else:
                # Streaming disabled — use original non-streaming path
                logger.info(f"[batch] OLLAMA_STREAM_ENABLED=False, using NON-STREAMING path for user_id={user_id}")
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
                await send_message(chat_id, ai_response)

            record_traffic_event()

            # Log outbound and mark processed
            try:
                db = SessionLocal()

                # If onboarding is not required, extract and store memories from the combined text.
                if 'dialogue' in locals() and dialogue.onboarding and not dialogue.onboarding.should_show_onboarding(user_id):
                    await extract_and_store_memories(dialogue.memory_manager, dialogue.memory_judge, user_id, combined_text, rag_mode=False)

                log = MessageLog(
                    user_id=user_id,
                    direction="outbound",
                    channel="telegram",
                    external_message_id=None,
                    content=ai_response,
                    status="sent",
                    error_message=None
                )
                log.message_role = "assistant"
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
