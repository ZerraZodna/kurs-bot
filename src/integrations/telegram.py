"""Telegram integration using python-telegram-bot SDK.

Replaces raw HTTP calls with clean SDK methods.
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime, timedelta, timezone

from telegram import Bot
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError, BadRequest

from src.config import settings
from src.models.database import SessionLocal, MessageLog, BatchLock
from src.integrations.telegram_stream import StreamingFilter
from src.services.dialogue_engine import DialogueEngine
from src.services.traffic_tracker import record_traffic_event
from src.functions.intent_parser import get_intent_parser
from src.functions.executor import get_function_executor
from src.functions.response_builder import get_response_builder

logger = logging.getLogger(__name__)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN) if settings.TELEGRAM_BOT_TOKEN else None


class TelegramHandler:
    @staticmethod
    def parse_webhook(request: dict) -> Optional[Dict[str, Any]]:
        msg = request.get('message') or request.get('edited_message')
        if not msg:
            return None
        user = msg.get('from')
        if not user or not msg.get('text'):
            return None
        text = msg.get('text')
        if text.startswith('/'):
            return None
        return {
            "user_id": str(user.get("id")),
            "channel": "telegram",
            "text": text,
            "external_message_id": str(msg.get("message_id")),
            "chat_id": str(msg.get("chat", {}).get("id")),
            "timestamp": datetime.fromtimestamp(msg.get("date", 0), timezone.utc),
        }


async def send_typing_action(chat_id: int) -> bool:
    if not bot:
        return False
    try:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        return True
    except TelegramError:
        return False


async def send_message(chat_id: int, text: str) -> bool:
    if not bot:
        return False
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text, 
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return True
    except TelegramError as e:
        logger.warning(f"[telegram send] {e}")
        return False


async def edit_message(chat_id: int, message_id: int, text: str) -> bool:
    if not bot:
        return False
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return True
    except BadRequest as e:
        if 'message is not modified' in str(e).lower():
            return True
        logger.warning(f"[telegram edit] {e}")
        return False
    except TelegramError as e:
        logger.warning(f"[telegram edit] {e}")
        return False


async def send_message_streaming(
    chat_id: int,
    token_generator: AsyncIterator[str],
    min_update_interval: float = None
) -> tuple[str, Optional[int]]:
    if min_update_interval is None:
        min_update_interval = getattr(settings, "TELEGRAM_STREAM_UPDATE_INTERVAL", 0.3)

    accumulated = "⏳ Thinking..."
    message_id: Optional[int] = None
    last_edit_time = 0.0
    last_text = ""
    start_time = time.monotonic()

    await send_typing_action(chat_id)

    async for token in token_generator:
        accumulated += token
        now = time.monotonic()
        if now - last_edit_time >= min_update_interval and accumulated != last_text:
            try:
                if message_id is None:
                    sent_msg = await bot.send_message(
                        chat_id=chat_id,
                        text=accumulated,
                        parse_mode=ParseMode.HTML
                    )
                    message_id = sent_msg.message_id
                else:
                    await edit_message(chat_id, message_id, accumulated)
                last_text = accumulated
                last_edit_time = now
            except (TelegramError, BadRequest) as e:
                logger.warning(f"[stream] Edit failed: {e}")
        # yield token  # Remove yield to make non-generator

    # Final edit
    if accumulated.strip() and accumulated != last_text:
        await edit_message(chat_id, message_id or 1, accumulated)

    logger.info(f"[stream] Complete: {len(accumulated)} chars in {time.monotonic() - start_time:.1f}s")
    return accumulated, message_id


async def process_telegram_batch(user_id: int, chat_id: str) -> None:
    chat_id_int = int(chat_id)
    await send_typing_action(chat_id_int)
    await asyncio.sleep(1.0)

    db = SessionLocal()
    try:
        for _ in range(3):
            message_ids = []
            combined_text = ""

            unprocessed = db.query(MessageLog).filter(
                MessageLog.user_id == user_id,
                MessageLog.direction == "inbound",
                MessageLog.status == "delivered",
            ).order_by(MessageLog.created_at).all()

            if not unprocessed:
                break

            message_ids = [m.message_id for m in unprocessed]
            combined_text = "\n".join([m.content for m in unprocessed if m.content])

            # Claim
            db.query(MessageLog).filter(MessageLog.message_id.in_(message_ids)).update(
                {MessageLog.status: "processing"}, synchronize_session=False
            )
            db.commit()

            # Dialogue
            dialogue = DialogueEngine(db)
            result = await dialogue.process_message(
                user_id=user_id,
                text=combined_text,
                session=db,
                chat_id=chat_id_int,
                include_history=True,
                history_turns=4,
            )

            if result["type"] == "stream":
                stream_filter = StreamingFilter(result["generator"])
                filtered_stream = stream_filter.filter_stream()
                full_response, _ = await send_message_streaming(chat_id=chat_id_int, token_generator=filtered_stream)

                # Functions
                function_parse_text = stream_filter.get_remaining_for_functions() or full_response
                parser = get_intent_parser()
                parse_result = parser.parse(function_parse_text)

                if parse_result.functions:
                    executor = get_function_executor()
                    execution_context = {
                        "user_id": user_id,
                        "session": db,
                        "memory_manager": dialogue.memory_manager,
                        "original_text": combined_text,
                    }
                    execution_result = await executor.execute_all(parse_result.functions, execution_context, continue_on_error=True)

                    response_builder = get_response_builder()
                    built_response = response_builder.build(
                        user_text=combined_text,
                        ai_response_text="",
                        execution_result=execution_result,
                        include_function_results=True,
                    )
                    if built_response.text.strip():
                        await send_message(chat_id_int, built_response.text)
                elif parse_result.errors:
                    error_msg = f"Sorry, invalid command.\\nErrors: {chr(10).join(parse_result.errors[:2])}\\nExamples: 'Set daily reminder at 09:00', 'lesson 29'"
                    await send_message(chat_id_int, error_msg)
                ai_response = full_response
            else:
                ai_response = result["text"]
                await send_message(chat_id_int, ai_response)

            record_traffic_event()

            # Log outbound
            log = MessageLog(
                user_id=user_id,
                direction="outbound",
                channel="telegram",
                content=ai_response,
                status="sent",
                message_role="assistant"
            )
            db.add(log)
            db.flush()

            # Mark processed
            db.query(MessageLog).filter(MessageLog.message_id.in_(message_ids)).update(
                {MessageLog.status: "processed"}, synchronize_session=False
            )
            db.commit()
            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"[batch] Error processing batch for user {user_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        lock_db = SessionLocal()
        try:
            lock_db.query(BatchLock).filter_by(user_id=user_id).delete()
            lock_db.commit()
        finally:
            lock_db.close()
            db.close()
