import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from src.core.timezone import datetime, timezone
from typing import Any, Dict

import httpx

from src.config import settings
from src.integrations.telegram_stream import StreamingFilter
from src.models.database import BatchLock, MessageLog, SessionLocal

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Shared httpx client with connection pooling to avoid creating a new
# client for every Telegram API call (especially during streaming where
# edit_message is called 20+ times per response).
_telegram_client: httpx.AsyncClient | None = None


async def _get_telegram_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient with connection pooling."""
    global _telegram_client
    if _telegram_client is None or _telegram_client.is_closed:
        _telegram_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            timeout=httpx.Timeout(10.0),
        )
    return _telegram_client


async def close_telegram_client() -> None:
    """Close the shared Telegram httpx client. Call on shutdown."""
    global _telegram_client
    if _telegram_client is not None and not _telegram_client.is_closed:
        await _telegram_client.aclose()
        _telegram_client = None


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
    text = re.sub(r"<li>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL)
    # Remove <ul> tags
    text = re.sub(r"</?ul[^>]*>", "", text, flags=re.IGNORECASE)

    # Step 2: Convert <br> to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Step 3: Strip unsupported HTML tags but keep their content
    text = _strip_unsupported_tags(text)

    # Clean up excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _strip_unsupported_tags(text: str) -> str:
    """Remove HTML tags that Telegram doesn't support, keeping their content."""
    # List of tags Telegram supports
    supported_tags = ["b", "strong", "i", "em", "u", "s", "code", "pre", "a"]

    # Pattern to match any tag not in supported list
    # This matches <tag> or </tag> where tag is not in supported list
    def replace_tag(match):
        # Return just the content between tags
        return match.group(1) or ""

    # Match opening tags with content: <unsupported>content</unsupported>
    # pattern = r'<(/?)(?!/?(?:' + '|'.join(supported_tags) + r')\b)(\w+)[^>]*>([^<]*)'

    # Use a different approach: find each tag and check if supported
    result = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            # Find the end of the tag
            end = text.find(">", i)
            if end == -1:
                result.append(text[i])
                i += 1
                continue

            tag = text[i : end + 1]

            # Check if it's a closing tag
            # is_closing = tag.startswith('</')

            # Extract tag name
            tag_name = re.sub(r"[</>]", "", tag).lower()
            # Handle self-closing tags and attributes
            tag_name = re.split(r"[\s>]", tag_name)[0]

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

    return "".join(result)


class TelegramHandler:
    @staticmethod
    def parse_webhook(request: dict) -> Dict[str, Any] | None:
        # Handles both message and edited_message
        msg = request.get("message") or request.get("edited_message")
        if not msg:
            return None
        user = msg.get("from")
        if not user or not msg.get("text"):
            return None
        # Ignore bot commands (optional)
        text = msg.get("text")
        chat = msg.get("chat", {}) or {}
        return {
            "user_id": str(user.get("id")),
            "channel": "telegram",
            "text": text,
            "external_message_id": str(msg.get("message_id")),
            "chat_id": str(chat.get("id")),
            "chat_type": chat.get("type"),
            "timestamp": datetime.fromtimestamp(msg.get("date", 0), timezone.utc),
        }


async def send_typing_action(chat_id: int) -> bool:
    """Send typing indicator to Telegram chat.

    Args:
        chat_id: Telegram chat ID

    Returns:
        True if successful, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"{API_BASE}/sendChatAction"
    payload = {"chat_id": chat_id, "action": "typing"}
    client = await _get_telegram_client()
    try:
        r = await client.post(url, json=payload, timeout=10.0)
        r.raise_for_status()
        return r.json().get("ok", False)
    except Exception:
        return False


async def edit_message(chat_id: int, message_id: int, text: str) -> dict | None:
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
    client = await _get_telegram_client()
    max_retries = settings.TELEGRAM_EDIT_MAX_RETRIES
    base_backoff = settings.TELEGRAM_BACKOFF_BASE_S

    for attempt in range(max_retries + 1):
        try:
            r = await client.post(url, json=payload, timeout=10.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            resp = e.response
            if resp is None:
                if attempt < max_retries:
                    await asyncio.sleep(base_backoff * (2**attempt))
                    continue
                logger.warning("[telegram] editMessageText final fail after %d retries: no resp", max_retries + 1)
                return None

            status = resp.status_code
            body = ""
            try:
                body = resp.text
            except Exception:
                pass

            # Ignore "message not modified"
            if status == 400 and "message is not modified" in body.lower():
                return None

            # Rate limit or bad request - backoff and retry
            if status in (400, 429) and attempt < max_retries:
                backoff = base_backoff * (2**attempt)
                logger.warning(
                    "[telegram] editMessageText retry %d/%d after %.1fs (status=%d): %s",
                    attempt + 1,
                    max_retries,
                    backoff,
                    status,
                    body[:100],
                )
                await asyncio.sleep(backoff)
                continue

            # HTML error fallback (no parse_mode)
            if status == 400:
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
                    pass

            # Final fail
            logger.warning(
                "[telegram] editMessageText final fail after %d retries: %d %s", max_retries + 1, status, body[:100]
            )
            return None
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(base_backoff * (2**attempt))
                continue
            logger.warning("[telegram] editMessageText final exception after %d retries: %s", max_retries + 1, e)
            return None


async def send_message_streaming(
    chat_id: int,
    token_generator: AsyncIterator[str],
    min_update_interval: float = None,
) -> tuple[str, int | None]:
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
    message_id: int | None = None
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


async def send_message(chat_id: int, text: str) -> dict | None:
    if not TELEGRAM_BOT_TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN not set")
        return None

    # Sanitize HTML to Telegram-supported format
    text = sanitize_html_for_telegram(text)

    url = f"{API_BASE}/sendMessage"
    client = await _get_telegram_client()
    # Telegram hard limit is 4096 chars; stay below to be safe
    max_len = 3500
    chunks = _split_text(text, max_len) or [""]
    last_response = None
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",  # Use HTML instead of MarkdownV2
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
                fallback_payload = {"chat_id": chat_id, "text": chunk}
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

    Streaming is enabled, LLM-generated
    responses are streamed token-by-token to Telegram via progressive
    message edits.  Non-LLM responses (commands, onboarding, lessons, etc.)
    are sent normally as a single message.
    """
    from src.services.dialogue_engine import DialogueEngine
    from src.services.traffic_tracker import record_traffic_event

    # Send typing indicator to show user we're processing (works for both webhook and polling)
    chat_id = int(external_id)
    await send_typing_action(chat_id)

    await asyncio.sleep(1.0)

    # Track dialogue for memory extraction (need to keep reference)
    dialogue = None

    # Use a single db session for the entire batch processing to ensure proper cleanup
    # This session will be used for: message collection, logging, and lock release
    db = SessionLocal()
    try:
        for _ in range(3):
            message_ids = []
            combined_text = ""

            try:
                unprocessed = (
                    db
                    .query(MessageLog)
                    .filter(
                        MessageLog.user_id == user_id,
                        MessageLog.direction == "inbound",
                        MessageLog.status == "delivered",
                    )
                    .order_by(MessageLog.created_at)
                    .all()
                )

                if not unprocessed:
                    break

                if len(unprocessed) > 1:
                    print(f"[batch] Combining {len(unprocessed)} messages from user {user_id}")

                message_ids = [m.message_id for m in unprocessed]
                combined_text = "\n".join([m.content for m in unprocessed if m.content])

                # Claim messages
                db.query(MessageLog).filter(MessageLog.message_id.in_(message_ids)).update(
                    {MessageLog.status: "processing"}, synchronize_session=False
                )
                db.commit()
            except Exception as e:
                print("[batch collection error]", e)
                db.rollback()
                break

            # Generate AI response — streaming or non-streaming
            chat_id = int(external_id)
            ai_response: str
            dialogue = None

            try:
                dialogue_db = db

                dialogue = DialogueEngine(dialogue_db)
                result = await dialogue.process_message(
                    user_id=user_id,
                    text=combined_text,
                    session=dialogue_db,
                    chat_id=chat_id,
                    include_history=True,
                    history_turns=4,
                )

                if result["type"] == "stream":
                    logger.info(f"[batch] Using STREAMING path for user_id={user_id}")

                    raw_generator = result["generator"]
                    stream_filter = StreamingFilter(raw_generator)
                    filtered_stream = stream_filter.filter_stream()

                    full_response, telegram_message_id = await send_message_streaming(
                        chat_id=chat_id,
                        token_generator=filtered_stream,
                    )

                    logger.info(f"[batch] Streamed to Telegram, message_id={telegram_message_id}")

                    remaining_for_functions = stream_filter.get_remaining_for_functions()
                    function_parse_text = remaining_for_functions or full_response

                    # Detailed failure logging
                    logger.info(f"[telegram FUNCTION_FAILURE user={user_id}] user_text='{combined_text[:200]}...'")
                    logger.info(
                        f"[telegram FUNCTION_FAILURE user={user_id}] function_parse_text='{function_parse_text[:1000]}...' (len={len(function_parse_text)})"
                    )
                    logger.info(
                        f"[telegram FUNCTION_FAILURE user={user_id}] raw_generator_remaining='{stream_filter.get_remaining_for_functions()[:500]}...'"
                    )

                    from src.functions import get_function_executor
                    from src.functions.intent_parser import get_intent_parser
                    from src.functions.response_builder import get_response_builder

                    parser = get_intent_parser()
                    parse_result = parser.parse(function_parse_text)

                    # RAW functions logging before any processing
                    fn_names = [f.get("name", "NO_NAME") for f in parse_result.functions]
                    fn_details = [
                        f"{f.get('name', 'NO_NAME')} (len={len(f.get('name', ''))})" for f in parse_result.functions
                    ]
                    logger.info(
                        f"[telegram RAW_FUNCTIONS user={user_id}] functions_count={len(parse_result.functions)}, names={fn_names}, details={fn_details}"
                    )
                    logger.info(
                        f"[telegram PARSE_RESULT user={user_id}] success={parse_result.success},fallback={parse_result.is_fallback},functions={len(parse_result.functions)},errors={len(parse_result.errors or [])}"
                    )

                    # Direct executor call (no post_hook)
                    diagnostics = {}
                    if parse_result.functions:
                        executor = get_function_executor()
                        execution_context = {
                            "user_id": user_id,
                            "session": dialogue_db,
                            "memory_manager": dialogue.memory_manager,
                            "original_text": combined_text,
                        }
                        execution_result = await executor.execute_all(
                            parse_result.functions, execution_context, continue_on_error=True
                        )
                        diagnostics["execution_result"] = execution_result
                        diagnostics["dispatched_actions"] = [
                            r.function_name for r in execution_result.results if r.success
                        ]
                    logger.info(
                        f"[telegram EXEC_RESULT user={user_id}] exec_result={diagnostics.get('execution_result') is not None},actions_len={len(diagnostics.get('dispatched_actions', []))},keys={list(diagnostics.keys())}"
                    )

                    # Handle all cases: success, empty [], parse errors, exec fails
                    parse_had_errors = bool(parse_result.errors and not parse_result.success)
                    exec_had_errors = (
                        diagnostics.get("execution_result")
                        and "error" in str(diagnostics.get("execution_result", "")).lower()
                    )

                    if parse_result.functions:  # Valid functions found
                        logger.info(
                            f"[telegram VALID_FUNCTIONS user={user_id}] Executing {len(parse_result.functions)} functions"
                        )
                        response_builder = get_response_builder()
                        built_response = response_builder.build(
                            user_text=combined_text,
                            ai_response_text="",  # Don't repeat streamed LLM response
                            execution_result=diagnostics.get("execution_result"),
                            include_function_results=True,
                        )
                        if built_response.text.strip():  # Only results/error
                            await send_message(chat_id, built_response.text)
                    elif parse_had_errors:
                        # Parser errors: undefined func / bad params
                        error_msg = f"Sorry, invalid command.\nErrors: {chr(10).join(parse_result.errors[:2])}\nExamples: 'Set daily reminder at 09:00', 'lesson 29'"
                        logger.warning(f"[telegram PARSE_ERROR user={user_id}] {parse_result.errors}")
                        await send_message(chat_id, error_msg)
                    elif exec_had_errors:
                        # Execution failed (but parsed OK)
                        error_msg = "Command failed during execution. Please try again or rephrase."
                        await send_message(chat_id, error_msg)
                    else:
                        # Normal: empty [] or chat
                        log_type = "EMPTY_FUNCTIONS" if parse_result.success else "PURE_CHAT"
                        logger.info(f"[telegram {log_type} user={user_id}] len={len(function_parse_text)}")

                    ai_response = full_response
                else:
                    logger.info(f"[batch] Text response for user_id={user_id}")
                    ai_response = result["text"]
                    await send_message(chat_id, ai_response)

            except Exception as e:
                logger.error(f"[telegram dialogue] Error in dialogue processing for user {user_id}: {e}")
                ai_response = "Sorry, I encountered an error processing your message."

            record_traffic_event()

            # Log outbound and mark processed using the main db session
            try:
                # Memory extraction now happens in the main Ollama call via the main prompt.

                log = MessageLog(
                    user_id=user_id,
                    direction="outbound",
                    channel="telegram",
                    external_message_id=None,
                    content=ai_response,
                    status="sent",
                    error_message=None,
                )
                log.message_role = "assistant"
                db.add(log)
                db.flush()
                logger.info(
                    f"[telegram] Created outbound MessageLog id={log.message_id} content_len={len(ai_response)}"
                )
                db.refresh(log)
                db.commit()

                db.query(MessageLog).filter(MessageLog.message_id.in_(message_ids)).update(
                    {MessageLog.status: "processed"}, synchronize_session=False
                )
                db.flush()
                db.commit()
            except Exception as e:
                logger.error("[messagelog outbound error]", e)
                db.rollback()
                break

            await asyncio.sleep(0.5)

    finally:
        # Release batch lock by deleting from table
        # Always use a fresh session for lock release to ensure it's not affected by prior errors
        lock_db = None
        try:
            lock_db = SessionLocal()
            lock_db.query(BatchLock).filter_by(user_id=user_id).delete(synchronize_session=False)
            lock_db.commit()
        except Exception as e:
            print("[batch lock release error]", e)
            if lock_db is not None:
                lock_db.rollback()
        finally:
            if lock_db is not None:
                lock_db.close()

        # Close the main db session
        if db is not None:
            db.close()
