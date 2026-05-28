"""AI-powered practice instruction extraction for ACIM lessons.

Reads lesson content via Ollama and extracts structured practice instructions:
- frequency (hourly, twice_daily, etc.)
- key_phrases (italicized self-talk text)
- instructions (what to do)
- practice_window (time pattern)

Results are cached in the database on first extraction and reused thereafter.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from src.models.database import Lesson, get_session

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "You are analyzing an ACIM (A Course in Miracles) lesson. Extract the practice instructions.\n\n"
    "Return a JSON object with these fields:\n"
    "  - frequency: one of 'hourly', 'twice_daily', 'three_times_daily', 'morning_evening', 'single'\n"
    "    - 'hourly' if the lesson says to practice every hour, hourly, repeatedly throughout the day,\n"
    "      in intervals, at regular intervals, as often as possible, or similar recurring patterns\n"
    "    - 'twice_daily' if morning and evening or twice a day\n"
    "    - 'three_times_daily' if three times a day\n"
    "    - 'morning_evening' if specifically morning and evening\n"
    "    - 'single' ONLY if the lesson mentions practicing once, a single time, or has no recurring pattern\n"
    "  - key_phrases: array of strings — the italicized self-talk text the user should repeat\n"
    "    (look for text in italics, quotes, or emphasized text that the user is told to say to themselves)\n"
    "  - instructions: string — what the user should actually do (e.g., 'Take five minutes', 'Practice with eyes open')\n"
    "  - practice_window: string — the time pattern (e.g., 'hourly from 7:00 to 22:00', 'morning and evening')\n\n"
    "IMPORTANT: ACIM lessons frequently use phrases like:\n"
    "  - 'in five-minute intervals' → hourly\n"
    "  - 'as often as possible' → hourly\n"
    "  - 'repeatedly throughout the day' → hourly\n"
    "  - 'repeat the reminder as often as possible' → hourly\n"
    "  - 'the hourly five minutes' → hourly\n"
    "  - 'practice at regular intervals' → hourly\n"
    "When you see any of these or similar recurring time patterns, use frequency 'hourly'.\n"
    "Do NOT use 'single' when the lesson suggests repeated practice.\n\n"
    "Rules:\n"
    "- key_phrases should be empty array if none found\n"
    "- instructions should be empty string if none found\n"
    "- practice_window should describe when to practice\n"
    "- Return ONLY valid JSON, no markdown, no explanations\n\n"
    "LESSON CONTENT:\n{content}\n"
)


def _extract_via_llm(lesson: Lesson) -> dict[str, Any] | None:
    """Call configured LLM (Ollama or OpenAI) to extract practice instructions."""
    try:
        import asyncio

        from src.services.dialogue import call_llm_router

        prompt = EXTRACTION_PROMPT.format(content=lesson.content)
        try:
            asyncio.get_running_loop()
            # We are inside a running loop (uvicorn) — create a new event loop
            # in a separate thread to avoid "loop already running" conflict
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(call_llm_router(prompt)))
                result = future.result()
        except RuntimeError:
            # No running loop — safe to use asyncio.run directly
            result = asyncio.run(call_llm_router(prompt))
        if not result:
            return None

        # Clean up potential markdown wrappers
        text = result.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last markdown lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError as e:
        logger.warning("AI extraction returned invalid JSON for lesson %d: %s", lesson.lesson_id, e)
        return None
    except Exception as e:
        logger.warning("AI extraction failed for lesson %d: %s", lesson.lesson_id, e)
        return None


def _default_extraction() -> dict[str, Any]:
    """Return default extraction for lessons with no special practice pattern."""
    return {
        "frequency": "single",
        "key_phrases": [],
        "instructions": "",
        "practice_window": "",
    }


def check_and_extract_practice_instructions(lesson_id: int, session: Session | None = None) -> dict[str, Any] | None:
    """Check if practice instructions are cached; if not, extract via AI and cache.

    Args:
        lesson_id: The lesson to check/extract for
        session: Optional DB session (managed via context manager)

    Returns:
        Dict with practice instructions, or None on failure (defaults to single).
    """
    with get_session(session) as db:
        try:
            lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if not lesson:
                logger.warning("Lesson %d not found", lesson_id)
                return None

            # Check if already cached
            if lesson.practice_instructions:
                try:
                    return json.loads(lesson.practice_instructions)
                except json.JSONDecodeError:
                    logger.warning(
                        "Cached practice_instructions for lesson %d is invalid JSON, re-extracting", lesson_id
                    )

            # Extract via AI
            result = _extract_via_llm(lesson)
            if result is None:
                result = _default_extraction()
                logger.info(
                    "AI extraction failed for lesson %d, using default (frequency=%s)",
                    lesson_id,
                    result.get("frequency", "single"),
                )
            else:
                # Cache only on successful extraction
                lesson.practice_instructions = json.dumps(result)
                db.commit()
                logger.info(
                    "Extracted and cached practice instructions for lesson %d: %s",
                    lesson_id,
                    result.get("frequency", "single"),
                )
            return result
        except Exception as e:
            logger.error("Failed to extract practice instructions for lesson %d: %s", lesson_id, e)
            return _default_extraction()
