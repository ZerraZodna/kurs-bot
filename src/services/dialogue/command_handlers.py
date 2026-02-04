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

logger = logging.getLogger(__name__)


def handle_rag_mode_toggle(text: str, memory_manager, user_id: int) -> Optional[str]:
    text_lower = text.strip().lower()
    if text_lower == "rag_mode":
        rag_mode_memory = memory_manager.get_memory(user_id, "rag_mode_enabled")
        is_on = bool(rag_mode_memory and rag_mode_memory[0].get("value") == "true")
        return f"RAG mode is {'on' if is_on else 'off'}."
    if text_lower.startswith("rag_mode "):
        mode_cmd = text_lower.replace("rag_mode", "").strip()
        if mode_cmd == "on":
            memory_manager.store_memory(
                user_id=user_id,
                key="rag_mode_enabled",
                value="true",
                confidence=1.0,
                source="user_command",
                category="conversation",
            )
            return "RAG mode enabled. I will use semantic search for all future messages."
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
