from __future__ import annotations

import logging
import json
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone

from src.services.semantic_search import get_semantic_search_service
from src.services.scheduler import SchedulerService
from src.models.database import Schedule
from src.services.gdpr_service import (
    export_user_data,
    restrict_processing,
    erase_user_data,
    object_to_processing,
    withdraw_consent,
)
from src.services.gdpr_verification import create_verification, verify_code
from src.models.database import PromptTemplate, SessionLocal
from src.services.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


def handle_rag_mode_toggle(text: str, memory_manager, user_id: int) -> Optional[str]:
    text_lower = text.strip().lower()
    # Normalize: accept both 'rag_mode' and 'rag mode' (and plain 'rag')
    normalized = text_lower.replace("_", " ").strip()

    # Accept 'rag', 'rag mode', 'rag_mode', and 'ragmode' as aliases
    if normalized in ("rag_mode", "rag mode", "rag", "ragmode"):
        rag_mode_memory = memory_manager.get_memory(user_id, "rag_mode_enabled")
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
            key="rag_mode_enabled",
            value="true",
            confidence=1.0,
            source="user_command",
            category="conversation",
        )
        return (
            "RAG mode enabled. I will use semantic search over your memories for future messages.\n\n"
            "You can customize RAG behavior:\n"
            "- Use `rag_prompt list` to view available prompt templates.\n"
            "- Use `rag_prompt select <key>` to pick a template from the library.\n"
            "- Use `rag_prompt custom <text>` to set a personal RAG system prompt.\n\n"
            "Tip: prefix a single message with `rag:` to use RAG only for that message."
        )
    if mode_cmd == "off":
        memory_manager.store_memory(
            user_id=user_id,
            key="rag_mode_enabled",
            value="false",
            confidence=1.0,
            source="user_command",
            category="conversation",
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
    rag_mode_memory = memory_manager.get_memory(user_id, "rag_mode_enabled")
    return bool(rag_mode_memory and rag_mode_memory[0].get("value") == "true")


async def handle_forget_commands(
    text: str,
    memory_manager,
    session: Session,
    user_id: int,
) -> Optional[str]:
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
            "GDPR options:\n"
            "- gdpr export: receive a JSON copy of your data\n"
            "- gdpr erase: delete your data (you can onboard again later)\n"
            "- gdpr restrict <reason>: limit processing (onboarding is blocked)\n"
            "- gdpr object <reason>: object to processing and restrict it (onboarding is blocked)\n"
            "- gdpr withdraw <scope>: withdraw consent (onboarding is blocked; default scope: data_storage)"
        )

    action = parts[1]
    reason = " ".join(parts[2:]).strip() if len(parts) > 2 else None

    if action not in {"export", "erase", "restrict", "object", "withdraw"}:
        return "Unsupported GDPR action. Try: export, erase, restrict, object, withdraw."

    payload = {}
    if action in {"restrict", "object", "erase"} and reason:
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
    return (
        f"Verification code: {code}. Reply with 'verify {code}' within "
        "10 minutes to proceed."
    )


def handle_debug_next_day(
    text: str,
    memory_manager,
    session: Session,
    user_id: int,
) -> Optional[str]:
    if text.strip().lower() != "next_day":
        return None

    if memory_manager:
        memory_manager.store_memory(
            user_id=user_id,
            key="debug_day_offset",
            value="1",
            confidence=1.0,
            source="debug_command",
            ttl_hours=1,
            category="conversation",
        )
    schedules = []
    if session:
        schedules = (
            session.query(Schedule)
            .filter(
                Schedule.user_id == user_id,
                Schedule.is_active == True,
                Schedule.schedule_type == "daily",
            )
            .all()
        )
    if schedules:
        scheduler = SchedulerService.get_scheduler()
        now = datetime.now(timezone.utc)
        for schedule in schedules:
            job_id = f"debug_next_day_{schedule.schedule_id}_{int(now.timestamp())}"
            scheduler.add_job(
                func=SchedulerService.execute_scheduled_task,
                trigger=DateTrigger(run_date=now, timezone="UTC"),
                args=[schedule.schedule_id],
                id=job_id,
                replace_existing=True,
            )
        return "OK — simulating next day for 1 hour and triggering the scheduled morning message now."
    return "OK — simulating next day for 1 hour. No active daily schedule found."


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
            templates = db.query(PromptTemplate).filter(PromptTemplate.visibility == "public").all()
            if not templates:
                return "No public prompt templates available."
            lines = [f"{t.key}: {t.title}" for t in templates]
            return "Available prompts:\n" + "\n".join(lines)

        if sub == "select":
            if len(parts) < 3:
                return "Usage: rag_prompt select <key>"
            key = parts[2]
            tmpl = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
            if not tmpl:
                return f"Prompt template '{key}' not found. Use 'rag_prompt list' to view available keys."
            memory_manager.store_memory(
                user_id=user_id,
                key="selected_rag_prompt_key",
                value=key,
                confidence=1.0,
                source="user_command",
                category="conversation",
            )
            return f"Selected prompt '{key}' ({tmpl.title})."

        if sub == "custom":
            rest = text.strip()[len(parts[0]) + len(parts[1]) + 2 :].strip()
            if not rest:
                return "Usage: rag_prompt custom <text>"
            memory_manager.store_memory(
                user_id=user_id,
                key="custom_rag_prompt",
                value=rest,
                confidence=1.0,
                source="user_command",
                category="conversation",
            )
            return "Custom RAG prompt saved for your account."

        if sub == "show":
            sel = memory_manager.get_memory(user_id, "selected_rag_prompt_key")
            custom = memory_manager.get_memory(user_id, "custom_rag_prompt")
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
