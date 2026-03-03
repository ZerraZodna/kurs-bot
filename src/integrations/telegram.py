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
    url = f"{API_BASE}/editMessageText"
    html_text = _markdown_to_html(text)
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": html_text,
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
    url = f"{API_BASE}/sendMessage"
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
    # Repair PDF/import artifacts like: a****** ******meaningless -> a meaningless
    text = _repair_asterisk_artifacts(text)

    # Promote table-like plain text into fenced blocks so Telegram renders them
    # in a monospaced <pre> block instead of proportional body text.
    text = _promote_table_blocks_to_fenced_code(text)

    # Escape HTML-sensitive characters first to avoid invalid HTML
    text = _escape_html(text)

    # Convert fenced code blocks first to avoid further markdown substitutions.
    text = _fenced_code_to_pre(text)

    # Order matters: process longest patterns first to avoid conflicts
    
    # 0. Headings (must be done FIRST before bold processing)
    # ### Heading -> <b>Heading</b> with newlines
    text = re.sub(r'^### (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+?)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    
    # 1. Bold italic: ***text*** -> <b><i>text</i></b>
    # Guard with lookarounds so literal asterisk runs (e.g. "a******")
    # are not interpreted as nested formatting.
    text = re.sub(r'(?<!\*)\*\*\*([^*\n]+?)\*\*\*(?!\*)', r'<b><i>\1</i></b>', text)
    
    # 2. Bold: **text** -> <b>text</b>
    text = re.sub(r'(?<!\*)\*\*(?!\*)([^*\n]+?)(?<!\*)\*\*(?!\*)', r'<b>\1</b>', text)
    
    # 3. Italic: *text* -> <i>text</i>
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # 4. Code: `text` -> <code>text</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    # 5. Links: [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    
    return text


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "<")
        .replace(">", ">")
    )


def _repair_asterisk_artifacts(text: str) -> str:
    # Common importer/PDF artifact in some lessons:
    #   "a****** ******meaningless" -> "a meaningless"
    #   "a**** ****meaningless" -> "a meaningless"
    # Only strip multi-asterisk runs between word characters so legitimate
    # markdown markers like *italic* / **bold** are unaffected.
    text = re.sub(r'(?<=\w)\*{2,}(?:\s+\*{2,})+(?=\w)', ' ', text)
    text = re.sub(r'(?<=\w)\*{2,}(?=\w)', '', text)
    return text


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


def _fenced_code_to_pre(text: str) -> str:
    pattern = re.compile(r"```(?:[A-Za-z0-9_+-]+)?\n?(.*?)```", re.DOTALL)

    def _replace(match: re.Match) -> str:
        content = match.group(1).strip("\n")
        return f"<pre>{content}</pre>"

    return pattern.sub(_replace, text)


def _promote_table_blocks_to_fenced_code(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    out: list[str] = []
    i = 0
    while i < len(lines):
        if not _is_table_candidate_line(lines[i]):
            out.append(lines[i])
            i += 1
            continue

        j = i
        block: list[str] = []
        while j < len(lines) and _is_table_candidate_line(lines[j]):
            block.append(lines[j])
            j += 1

        if _should_wrap_table_block(block):
            out.append("```")
            out.extend(block)
            out.append("```")
        else:
            out.extend(block)

        i = j

    return "\n".join(out)


def _is_table_candidate_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _contains_box_drawing_char(stripped):
        return True
    if re.match(r"^\+[-=:+\s]+(?:\+[-=:+\s]+)+\+?$", stripped):
        return True
    if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
        return True
    if "|" in stripped:
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) >= 2 and any(cells):
            return True
    return False


def _should_wrap_table_block(block: list[str]) -> bool:
    if len(block) < 2:
        return False

    has_strong_separator = any(_is_table_separator_line(line.strip()) for line in block)
    has_box = any(_contains_box_drawing_char(line) for line in block)
    if has_box or has_strong_separator:
        return True

    # Fallback for simple pipe-based tables without explicit separators.
    return len(block) >= 3 and any("|" in line for line in block)


def _is_table_separator_line(stripped: str) -> bool:
    if not stripped:
        return False
    if re.match(r"^\+[-=:+\s]+(?:\+[-=:+\s]+)+\+?$", stripped):
        return True
    if re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", stripped):
        return True
    return False


def _contains_box_drawing_char(line: str) -> bool:
    return any(ch in line for ch in "┌┬┐├┼┤└┴┘│─═╔╗╚╝╠╣╦╩")


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
                    await extract_and_store_memories(dialogue.memory_manager, dialogue.memory_extractor, user_id, combined_text, rag_mode=False)

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
