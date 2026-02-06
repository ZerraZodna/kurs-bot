"""Schedule query detection and response helpers."""

from __future__ import annotations

from typing import Iterable

from src.models.database import Schedule
from src.services.timezone_utils import format_dt_in_timezone
from src.services.embedding_service import get_embedding_service
from src.config import settings
import asyncio


# Curated schedule-status examples (used to detect queries like "what reminders do I have?")
_SCHEDULE_STATUS_EXAMPLES = [
    "do i have any reminders",
    "which reminders do i have",
    "what reminders do i have",
    "do i have a schedule",
    "what is my schedule",
    "show my reminders",
    "list my reminders",
    "which schedules do i have",
]

# Cached embeddings for the examples (computed once)
_cached_example_embeddings = None
# Lock to avoid parallel cache population
_cache_lock = asyncio.Lock()


async def _ensure_example_embeddings(emb_svc):
    global _cached_example_embeddings
    if _cached_example_embeddings is not None:
        return
    async with _cache_lock:
        if _cached_example_embeddings is not None:
            return
        try:
            embeds = await emb_svc.batch_embed(_SCHEDULE_STATUS_EXAMPLES)
            # filter out any None embeddings and keep order
            _cached_example_embeddings = [e for e in embeds if e is not None]
        except Exception:
            _cached_example_embeddings = []


async def detect_schedule_status_request(text: str) -> bool:
    """Use cached example embeddings and a single message embedding to detect
    schedule-status queries. This is faster than embedding both message and
    examples every call and avoids keyword hijacking.
    """
    message = (text or "").strip()
    if not message:
        return False

    emb_svc = get_embedding_service()

    try:
        await _ensure_example_embeddings(emb_svc)
        if not _cached_example_embeddings:
            return False

        # Embed only the incoming message
        msg_emb = await emb_svc.generate_embedding(message)
        if not msg_emb:
            return False

        sims = [emb_svc.cosine_similarity(msg_emb, e) for e in _cached_example_embeddings]
        max_sim = max(sims) if sims else 0.0
        return float(max_sim) >= float(getattr(settings, "TRIGGER_SIMILARITY_THRESHOLD", 0.75))
    except Exception:
        return False


def build_schedule_status_response(schedules: Iterable[Schedule], tz_name: str = "UTC") -> str:
    schedules = list(schedules)
    if not schedules:
        return "You don't have any active reminders."

    lines = ["Here are your active reminders:"]
    for schedule in schedules:
        if schedule.schedule_type.startswith("one_time"):
            if schedule.next_send_time:
                ts, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
                lines.append(f"- One-time reminder at {ts:%Y-%m-%d %H:%M}")
            else:
                lines.append("- One-time reminder (time not set)")
            continue

        if schedule.next_send_time:
            ts, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
            lines.append(f"- Daily reminder at {ts:%H:%M}")
        else:
            lines.append("- Daily reminder (time not set)")

    return "\n".join(lines)
