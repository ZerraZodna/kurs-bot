from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone

from src.services.semantic_search import get_semantic_search_service
from src.services.scheduler import SchedulerService
from src.models.database import Schedule

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
