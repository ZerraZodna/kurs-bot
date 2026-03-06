from __future__ import annotations

import logging
import json
from typing import Optional, Tuple
import asyncio
import threading

from sqlalchemy.orm import Session
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone, timedelta

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.semantic_search import get_semantic_search_service
from src.memories.memory_handler import MemoryHandler
from src.scheduler import api as scheduler_api
from src.scheduler.domain import SCHEDULE_TYPE_DAILY
from src.services.gdpr_service import (
    export_user_data,
    restrict_processing,
    erase_user_data,
    object_to_processing,
    withdraw_consent,
)
from src.services.gdpr_verification import create_verification, verify_code
from src.models.database import PromptTemplate, SessionLocal
from src.models.schedule import Schedule
from src.language.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


def handle_rag_mode_toggle(text: str, memory_manager, user_id: int) -> Optional[str]:
    text_lower = text.strip().lower()
    # Normalize: accept both 'rag_mode' and 'rag mode' (and plain 'rag')
    normalized = text_lower.replace("_", " ").strip()

    # Accept 'rag', 'rag mode', 'rag_mode', and 'ragmode' as aliases
    if normalized in ("rag_mode", "rag mode", "rag", "ragmode"):
        rag_mode_memory = memory_manager.get_memory(user_id, MemoryKey.RAG_MODE_ENABLED)
        is_on = bool(rag_mode_memory and rag_mode_memory[0].get("value") == "true")
        return f"RAG mode is {'on' if is_on else 'off'}."

    # Support commands like 'rag_mode on', 'rag mode on', 'rag on', and also 'rag:on' via parse fallback
    mode_cmd = ""
    if normalized.startswith("rag mode "):
        mode_cmd = normalized[len("rag mode "):].strip()
    elif normalized.startswith("rag "):
        mode_cmd = normalized[len("rag "):].strip()
    elif normalized.startswith("ragmode "):
        mode_cmd = normalized[len("ragmode "):].strip()
    # Also allow 'rag: on' or 'ragmode: on' style (colon)
    elif text_lower.startswith("rag:") or text_lower.startswith("ragmode:"):
        mode_cmd = text_lower.split(":", 1)[1].strip()

    if not mode_cmd:
        return None

    if mode_cmd == "on":
        memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.RAG_MODE_ENABLED,
            value="true",
            confidence=1.0,
            source="user_command",
            category=MemoryCategory.CONVERSATION.value,
        )
        return (
            "RAG mode enabled. I will use semantic search over your memories for future messages.\n\n"
            "You can customize RAG behavior:\n"
            "- Use `rag_prompt list` to view available prompt templates.\n"
            "- Use `rag_prompt select <key>` to pick a template from the library.\n"
            "- Use `rag_prompt custom <text>` to set a personal RAG system prompt.\n"
            "- Use `list memories` or `list memories <query>` to list or search your stored memories while RAG is active.\n\n"
            "Tip: prefix a single message with `rag:` to use RAG only for that message."
        )
    if mode_cmd == "off":
        memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.RAG_MODE_ENABLED,
            value="false",
            confidence=1.0,
            source="user_command",
            category=MemoryCategory.CONVERSATION.value,
        )
        return "RAG mode disabled. Back to standard workflow."

    return None


def parse_rag_prefix(text: str) -> Tuple[str, bool]:
    text_lower = text.strip().lower()
    if text_lower.startswith("rag:") or text_lower.startswith("rag "):
        stripped = text[4:].lstrip(": ").strip()
        return stripped, True
    return text, False


def is_rag_mode_enabled(memory_manager, user_id: int) -> bool:
    rag_mode_memory = memory_manager.get_memory(user_id, MemoryKey.RAG_MODE_ENABLED)
    return bool(rag_mode_memory and rag_mode_memory[0].get("value") == "true")


async def handle_forget_commands(
    text: str,
    memory_manager,
    session: Session,
    user_id: int,
    rag_mode_enabled: bool = False,
) -> Optional[str]:
    """Handle forget/erase/delete commands for memories.
    
    Only active when RAG mode is enabled to avoid conflicts with
    schedule deletion commands in normal ACIM study mode.
    """
    # Only process memory deletion commands when in RAG mode
    if not rag_mode_enabled:
        return None
        
    text_lower = text.strip().lower()
    forget_prefixes = ("forget ", "erase ", "delete ", "remove ")
    if text_lower in {"forget", "erase", "delete", "remove"}:
        return "Tell me what to forget (e.g., 'forget my grandfather')."
    if text_lower.startswith(forget_prefixes):
        query_text = text.split(" ", 1)[1].strip()
        if not query_text:
            return "Tell me what to forget (e.g., 'forget my grandfather')."
        memory_ids = []
        try:
            search_service = get_semantic_search_service()
            search_session = Session(bind=session.get_bind())
            try:
                results = await search_service.search_memories(
                    user_id=user_id,
                    query_text=query_text,
                    session=search_session,
                )
                memory_ids = [memory.memory_id for memory, _ in results]
            finally:
                search_session.close()
        except Exception as ex:
            logger.warning(f"Semantic search failed for forget: {ex}")
        archived = memory_manager.archive_memories(user_id, memory_ids)
        if archived == 0:
            return "I couldn't find any matching memories to forget."
        return f"Forgot {archived} memory item(s) related to: {query_text}."
    return None


def _execute_verified_request(session: Session, user_id: int, verification) -> str:
    request_type = verification.request_type
    payload = {}
    try:
        if verification.request_payload:
            payload = json.loads(verification.request_payload)
    except Exception:
        payload = {}

    if request_type == "export":
        data = export_user_data(session, user_id)
        return "Export (JSON): " + json.dumps(data, ensure_ascii=False)
    if request_type == "erase":
        erase_user_data(session, user_id, payload.get("reason"), actor="user")
        return "Your data has been erased."
    if request_type == "clear":
        # Clear behaves like erase but leaves the User row active so the
        # same user_id can be reused by tests / WebUI.
        from src.services.gdpr_service import clean_user_data

        clean_user_data(session, user_id, payload.get("reason"), actor="user")
        return "Your data has been erased (clear). User record left active."
    if request_type == "restrict":
        restrict_processing(session, user_id, payload.get("reason"), actor="user")
        return "Your data processing has been restricted."
    if request_type == "object":
        object_to_processing(session, user_id, payload.get("reason"), actor="user")
        return "Your objection has been recorded and processing restricted."
    if request_type == "withdraw":
        withdraw_consent(
            session,
            user_id=user_id,
            scope=payload.get("scope", "data_storage"),
            actor="user",
            reason=payload.get("reason"),
        )
        return "Your consent has been withdrawn."

    return "Verification completed, but request type is unsupported."


async def handle_gdpr_commands(
    text: str,
    session: Session,
    user_id: int,
    channel: str,
) -> Optional[str]:
    text_lower = text.strip().lower()

    if text_lower.startswith("verify "):
        code = text_lower.split(" ", 1)[1].strip()
        if not code.isdigit():
            return "Verification code must be numeric."
        try:
            verification = verify_code(session, user_id, code)
        except ValueError as exc:
            return f"Verification failed: {exc}."

        response = _execute_verified_request(session, user_id, verification)
        return response

    if not (text_lower.startswith("gdpr") or text_lower.startswith("/gdpr")):
        return None

    parts = text_lower.replace("/gdpr", "gdpr", 1).split()
    if len(parts) == 1:
        return (
            "<b>GDPR options:</b>\n"
            "- gdpr export: receive a JSON copy of your data\n"
            "- gdpr erase: delete your data (you can onboard again later)\n"
            "- gdpr clear: delete/anonymize PII but keep the user id active for reuse\n"
            "- gdpr restrict &lt;reason&gt;: limit processing (onboarding is blocked)\n"
            "- gdpr object &lt;reason&gt;: object to processing and restrict it (onboarding is blocked)\n"
            "- gdpr withdraw &lt;scope&gt;: withdraw consent (onboarding is blocked; default scope: data_storage)"
        )

    action = parts[1]
    reason = " ".join(parts[2:]).strip() if len(parts) > 2 else None

    if action not in {"export", "erase", "clear", "restrict", "object", "withdraw"}:
        return "Unsupported GDPR action. Try: export, erase, clear, restrict, object, withdraw."

    # Descriptions of what each GDPR action does
    action_descriptions = {
        "export": "📥 <b>Export Data</b>: You will receive a JSON copy of all your stored data including memories, schedules, and message history.",
        "erase": "⚠️ <b>Erase Data</b>: This will <b>permanently delete all your personal data</b> including memories, schedules, and messages. This action cannot be undone and you will need to onboard again to use the service.",
        "clear": "⚠️ <b>Clear Data</b>: This will delete your personal information but keep your user ID active. Your memories, schedules, and messages will be removed. This is mainly used for testing purposes.",
        "restrict": "⚠️ <b>Restrict Processing</b>: This will limit how your data is used and <b>block you from onboarding</b> until the restriction is lifted. You will not be able to use the service while processing is restricted.",
        "object": "⚠️ <b>Object to Processing</b>: This will restrict all data processing and <b>block you from using the service</b> (onboarding will be disabled). A legal record will be created for GDPR compliance.",
        "withdraw": "⚠️ <b>Withdraw Consent</b>: This will withdraw your consent for data storage and <b>disable your access</b> to the service. You will be opted out and blocked from onboarding until you provide consent again.",
    }
    payload = {}
    if action in {"restrict", "object", "erase", "clear"} and reason:
        payload["reason"] = reason
    if action == "withdraw":
        payload["scope"] = reason or "data_storage"

    code = create_verification(
        session=session,
        user_id=user_id,
        channel=channel,
        request_type=action,
        payload=payload,
    )

    description = action_descriptions.get(action, "")
    return (
        f"{description}\n\n"
        f"To proceed, reply with: verify {code}\n"
        f"(Code expires in 10 minutes)"
    )


def handle_debug_next_day(
    text: str,
    memory_manager,
    session: Session,
    user_id: int,
) -> Optional[str]:
    """Advance the debug day offset and execute daily schedules once.

    This command uses scheduler.api to find and execute daily schedules.
    """
    if text.strip().lower() != "next_day":
        return None

    if memory_manager:
        # Increment existing debug offset if present so repeated `next_day`
        # calls advance the simulated day consecutively.
        try:
            offsets = memory_manager.get_memory(user_id, MemoryKey.DEBUG_DAY_OFFSET)
            current = 0
            if offsets:
                latest = max(offsets, key=lambda x: x.get("created_at") or datetime(1970, 1, 1, tzinfo=timezone.utc))
                raw = str(latest.get("value", "")).strip()
                try:
                    current = int(raw)
                except Exception:
                    current = 0
            new_value = str(current + 1)
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.DEBUG_DAY_OFFSET,
                value=new_value,
                confidence=1.0,
                source="debug_command",
                ttl_hours=1,
                category=MemoryCategory.CONVERSATION.value,
            )
        except Exception:
            # Fall back to writing '1' if anything goes wrong
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.DEBUG_DAY_OFFSET,
                value="1",
                confidence=1.0,
                source="debug_command",
                ttl_hours=1,
                category=MemoryCategory.CONVERSATION.value,
            )
    
    # Use scheduler.api to get user's daily schedules
    schedules = scheduler_api.get_user_schedules(
        user_id=user_id,
        active_only=True,
        session=session,
    )
    
    # Filter for daily schedules only
    daily_schedules = [s for s in schedules if s.schedule_type == SCHEDULE_TYPE_DAILY]
    
    if daily_schedules:
        # Use the production scheduler simulation path so we exercise
        # the same code paths used in production. Collect returned
        # simulated messages (if any) and return them to the caller.
        messages = []
        for schedule in daily_schedules:
            try:
                result = scheduler_api.execute_scheduled_task(schedule.schedule_id, simulate=True, session=session)
                if result:
                    # result is expected to be a list of messages when simulate=True
                    if isinstance(result, list):
                        messages.extend(result)
                    elif isinstance(result, str):
                        messages.append(result)
            except Exception as e:
                logger.exception("Failed to simulate schedule %s: %s", getattr(schedule, "schedule_id", "?"), e)

        if messages:
            return "\n\n".join(messages)
        return "OK"
    return "OK"


def handle_list_memories(text: str, memory_manager, session: Session, user_id: int) -> Optional[str]:
    """Handle user commands that request listing memories.

    Recognizes aliases like `list memories`, `list my memories`, `list_memories`.
    Returns a formatted string when matched, otherwise `None`.
    """
    if not text or not text.strip():
        return None
    text_lower = text.strip().lower()
    triggers = {
        "list all my memories",
        "list my memories",
        "list memories",
        "list_memories",
        "list memory",
    }
    # Accept trigger optionally followed by extra query text (handled below)

    try:
        def _format_mem_lines(mems: list) -> list:
            out = []
            out.append("Memory")
            for mem in mems:
                date = getattr(mem, "created_at", None)
                date_short = date.strftime("%m-%d %H:%M") if date is not None else "-"
                key = getattr(mem, "key", "")
                key_part = f"{key}" if key else ""
                val = mem.value or ""
                category = getattr(mem, "category", "")
                if len(val) > 300:
                    val = val[:297] + "..."
                category = (category or "")
                                
                # Wrap label in backticks to prevent Markdown italics from underscores
                # Format: date `label` "value"
                line = f'{date_short} {category}.{key_part}={val}'
                out.append(line)
            return out

        # Determine whether the user provided a trailing query after the trigger
        matched_trigger = False
        query_tail = ""
        for trig in triggers:
            if text_lower == trig:
                matched_trigger = True
                query_tail = ""
                break
            if text_lower.startswith(trig + " "):
                matched_trigger = True
                # preserve original text after the trigger (not lowercased)
                query_tail = text[len(trig) :].strip()
                break
        if not matched_trigger:
            return None

        # If no query provided or user asked for '*', list all memories as before
        if not query_tail or query_tail.strip() == "*":
            rows = (
                MemoryHandler(session)
                .list_active_memories(user_id=user_id, order_ascending=True)
            )
            if not rows:
                return "You have no memories stored."
            lines = _format_mem_lines(rows)
            return "<pre>\n" + "\n".join(lines) + "\n</pre>"

        # Otherwise run a semantic search for the provided query tail and list matching memories
        def _run_coro_sync(coro):
            """Run coroutine `coro` synchronously.

            If there's no running event loop in the current thread, use
            `asyncio.run`. If there is a running loop, run the coroutine in a
            fresh event loop on a new thread to avoid "asyncio.run() cannot be
            called from a running event loop" errors.
            """
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(coro)

            result = {}
            exc = {}

            def _worker():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result["value"] = loop.run_until_complete(coro)
                except Exception as e:
                    exc["e"] = e
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

            t = threading.Thread(target=_worker)
            t.start()
            t.join()
            if "e" in exc:
                raise exc["e"]
            return result.get("value")

        try:
            search_service = get_semantic_search_service()
            search_session = Session(bind=session.get_bind())
            try:
                results = _run_coro_sync(
                    search_service.search_memories(
                        user_id=user_id, query_text=query_tail, session=search_session, limit=20
                    )
                )
            finally:
                search_session.close()
            if not results:
                return "No results for query"
            mems = [m for (m, s) in results]
            lines = _format_mem_lines(mems)
            return "<pre>\n" + "\n".join(lines) + "\n</pre>"
        except Exception as e:
            logger.exception("Semantic search failed for list memories: %s", e)
            # Include exception text to help debugging in dev environments
            try:
                return f"Failed to perform semantic search for memories: {e}"
            except Exception:
                return "Failed to perform semantic search for memories."
    except Exception as e:
        logger.exception("Failed to build memory list: %s", e)
        return "Failed to list memories."


def handle_rag_prompt_command(text: str, memory_manager, user_id: int) -> Optional[str]:
    """Handle `rag_prompt` CLI-style commands from users.

    Supported commands:
      - `rag_prompt list` — list available public prompt templates
      - `rag_prompt select <key>` — select a template for your account
      - `rag_prompt custom <text>` — set a custom free-text prompt for RAG
      - `rag_prompt show` — show current selection / custom prompt
    """
    if not text or not text.strip():
        return None

    parts = text.strip().split()
    cmd = parts[0].lower()
    if cmd not in ("rag_prompt", "ragprompt", "rag-prompt"):
        return None

    # no subcommand -> help
    if len(parts) == 1:
        return (
            "RAG prompt commands:\n"
            "- rag_prompt list\n"
            "- rag_prompt select <key>\n"
            "- rag_prompt custom <text>\n"
            "- rag_prompt show"
        )

    sub = parts[1].lower()
    db = SessionLocal()
    try:
        if sub == "list":
            parts_out = []

            # Resolve active prompt according to PromptRegistry logic: custom overrides selected key
            active_type = None
            active_key = None
            try:
                custom_mem = memory_manager.get_memory(user_id, MemoryKey.CUSTOM_RAG_PROMPT)
                custom_val = custom_mem[0].get("value") if custom_mem else None
                if custom_val and custom_val.strip():
                    active_type = "custom"
            except Exception:
                custom_val = None

            try:
                sel_mem = memory_manager.get_memory(user_id, MemoryKey.SELECTED_RAG_PROMPT_KEY)
                sel_key = sel_mem[0].get("value") if sel_mem else None
                if active_type is None and sel_key:
                    active_type = "selected"
                    active_key = sel_key
            except Exception:
                sel_key = None

            # Include any ad-hoc custom prompt stored in user memory
            if custom_val:
                snippet = custom_val[:200] + ("..." if len(custom_val) > 200 else "")
                suffix = " (active)" if active_type == "custom" else ""
                parts_out.append(f"custom{suffix}: {snippet}")

            # Include private templates owned by this user (owner stored as str(user_id))
            try:
                private_templates = db.query(PromptTemplate).filter(
                    PromptTemplate.visibility == "private",
                    PromptTemplate.owner == str(user_id),
                ).all()
                for t in private_templates:
                    suffix = " (active)" if active_type == "selected" and active_key == t.key else ""
                    parts_out.append(f"{t.key} (private){suffix}: {t.title}")
            except Exception:
                pass

            # Finally include public templates
            templates = db.query(PromptTemplate).filter(PromptTemplate.visibility == "public").all()
            if templates:
                for t in templates:
                    suffix = " (active)" if active_type == "selected" and active_key == t.key else ""
                    parts_out.append(f"{t.key}{suffix}: {t.title}")

            if not parts_out:
                return "No RAG prompts available."
            return "Available prompts:\n" + "\n".join(parts_out)

        if sub == "select":
            if len(parts) < 3:
                return "Usage: rag_prompt select <key>"
            key = parts[2]
            tmpl = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
            if not tmpl:
                return f"Prompt template '{key}' not found. Use 'rag_prompt list' to view available keys."
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.SELECTED_RAG_PROMPT_KEY,
                value=key,
                confidence=1.0,
                source="user_command",
                category=MemoryCategory.CONVERSATION.value,
            )
            return f"Selected prompt '{key}' ({tmpl.title})."

        if sub == "custom":
            rest = text.strip()[len(parts[0]) + len(parts[1]) + 2 :].strip()
            if not rest:
                return "Usage: rag_prompt custom <text>"

            # Store in user memory (keeps existing behavior)
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.CUSTOM_RAG_PROMPT,
                value=rest,
                confidence=1.0,
                source="user_command",
                category=MemoryCategory.CONVERSATION.value,
            )

            # Also persist as a private PromptTemplate row so it appears in listings
            try:
                key = f"private_rag_user_{user_id}"
                existing = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
                if existing:
                    existing.text = rest
                    existing.title = f"Custom prompt (user {user_id})"
                    existing.owner = str(user_id)
                    existing.visibility = "private"
                else:
                    pt = PromptTemplate(
                        key=key,
                        title=f"Custom prompt (user {user_id})",
                        text=rest,
                        owner=str(user_id),
                        visibility="private",
                    )
                    db.add(pt)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

            return "Custom RAG prompt saved for your account."

        if sub == "show":
            sel = memory_manager.get_memory(user_id, MemoryKey.SELECTED_RAG_PROMPT_KEY)
            custom = memory_manager.get_memory(user_id, MemoryKey.CUSTOM_RAG_PROMPT)
            parts_out = []
            if custom and custom[0].get("value"):
                parts_out.append("Custom prompt: " + (custom[0].get("value")[:200] + ("..." if len(custom[0].get("value")) > 200 else "")))
            if sel and sel[0].get("value"):
                key = sel[0].get("value")
                tmpl = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
                if tmpl:
                    parts_out.append(f"Selected template: {key} — {tmpl.title}")
                else:
                    parts_out.append(f"Selected template: {key} (not found)")
            if not parts_out:
                return "No RAG prompt selected for your account."
            return "\n".join(parts_out)

    finally:
        db.close()

    return None
