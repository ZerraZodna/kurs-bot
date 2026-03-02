"""Lesson retrieval and handling logic."""

from __future__ import annotations

import logging
import json
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.memories.constants import MemoryKey
from src.config import settings


def _get_ollama_client():
    from src.services.dialogue.ollama_client import call_ollama

    return call_ollama


logger = logging.getLogger(__name__)


def detect_lesson_request(text: str) -> Optional[Dict[str, Any]]:
    """
    Detect if user is requesting information about a specific lesson.

    Examples:
    - "Tell me about lesson 10"
    - "What is lesson 5?"
    - "Explain lesson 42"
    - "Lesson 1 content"

    Returns:
        Dict with lesson_id if detected, None otherwise
    """
    # Normalize input for robust matching: lowercase, replace punctuation
    # with spaces, and collapse multiple whitespace.
    raw = text or ""
    text_lower = raw.lower()
    text_normalized = re.sub(r"[^\w\s]", " ", text_lower)
    text_normalized = re.sub(r"\s+", " ", text_normalized).strip()
    tokens = set(text_normalized.split())

    def _extract_number(s: str) -> Optional[int]:
        patterns = [
            r"\b(?:lesson|leksjon|lekse|day)\s*(?:number|nr|no|text|tekst|content|innhold)?\s*#?\s*(\d{1,3})\b",
            r"\b(?:lesson|leksjon|lekse)\s*(?:text|tekst|content|innhold)\s*#?\s*(\d{1,3})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, s)
            if not m:
                continue
            try:
                n = int(m.group(1))
            except Exception:
                return None
            if 1 <= n <= 365:
                return n
        return None

    # 1) explicit numbered lesson
    num = _extract_number(text_normalized)
    if num:
        return {"lesson_id": num}

    # 2) "today's lesson" variants (English/Norwegian)
    lesson_keywords = {"lesson", "leksjon", "lekse"}
    today_keywords = {"today", "todays", "idag", "dagens"}
    has_lesson_word = bool(tokens & lesson_keywords)
    has_today_word = bool(tokens & today_keywords) or ("i dag" in text_normalized)
    if has_lesson_word and has_today_word:
        return {"today": True}

    return None


def _find_lesson_by_id(session: Session, lesson_id: int) -> Optional[Lesson]:
    """Lookup lesson by id and best-effort import bundled lessons when missing."""
    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if lesson:
        return lesson

    from src.lessons.importer import ensure_lessons_available

    ok = ensure_lessons_available(session)
    if not ok:
        return None
    return session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()


async def handle_lesson_request(
    lesson_id: int, user_input: str, session: Session, user_language: str = "en"
) -> str:
    """
    Handle requests for specific lesson content using RAG.

    Retrieves the lesson from database and injects it into the context
    so the LLM responds with accurate information.

    Args:
        lesson_id: The lesson number (1-365)
        user_input: User's question about the lesson
        session: Database session

    Returns:
        LLM response about the lesson
    """
    try:
        lesson = _find_lesson_by_id(session, lesson_id)
        if not lesson:
            return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."

        # Detect if the user explicitly asks for the exact/raw lesson text.
        # Use keyword-based detection for explicit requests.
        user_lower = user_input.lower()
        
        # Check for explicit requests for exact lesson text
        exact_text_indicators = [
            r"\bwhat exactly is\b.*\blesson\b",
            r"\b(exact|exactly|the text of|exact text|exact words)\b",
            r"\b(raw|verbatim|full text|complete text)\b",
            r"\btext of lesson\b",
            r"\blesson text\b",
        ]
        
        wants_exact_text = any(
            re.search(pattern, user_lower) for pattern in exact_text_indicators
        )
        
        if wants_exact_text:
            logger.info(
                "lesson_trigger_decision payload=%s",
                json.dumps(
                    {
                        "matched_action": "raw_lesson",
                        "score": 1.0,
                        "threshold": 0.0,
                        "fallback_path_used": False,
                        "match_source": "keyword_detection",
                    },
                    sort_keys=True,
                ),
            )
            return await format_lesson_message(lesson, user_language or "en")

        # Otherwise (including plain "Give me lesson N"), use RAG/LLM to discuss the lesson
        system_prompt = f"""{settings.SYSTEM_PROMPT}

    ### Requested Lesson Content [RAG CONTEXT - USE THIS]
    **Lesson {lesson.lesson_id}**: "{lesson.title}"

    {lesson.content}

    ---
    The user is asking about this lesson. Use the above content to provide accurate, detailed information."""

        prompt = f"""{system_prompt}

    ### User Question
    {user_input}

    ### Response
    Provide a thoughtful, detailed response about this ACIM lesson. Reference specific points from the lesson content above. Be warm and encouraging."""

        response = await _get_ollama_client()(prompt, None, user_language)
        return response

    except Exception as e:
        logger.error(f"[Lesson request error] Failed to handle lesson {lesson_id}: {e}")
        return (
            f"I encountered an error retrieving lesson {lesson_id}. Please try again."
        )


async def pre_llm_lesson_short_circuit(
    original_text: str,
    precomputed_embedding,  # Kept for backward compatibility but no longer used
    user_id: int,
    session: Session,
    prompt_builder,
    user_lang: str,
) -> Optional[str]:
    """
    Check for lesson requests using keyword detection before calling the LLM.
    Returns a verbatim/formatted lesson message when a lesson request is detected.

    Note: Embedding-based trigger matching removed in favor of keyword detection
    and function calling. This function is kept for backward compatibility
    but no longer uses precomputed_embedding.
    """
    # Use keyword-based detection instead of embedding-based matching
    lesson_request = detect_lesson_request(original_text)
    
    if not lesson_request:
        return None
    
    if lesson_request.get("today") and prompt_builder:
        today_ctx = prompt_builder.get_today_lesson_context(user_id)
        state = today_ctx.get("state", {})
        lesson_id = state.get("lesson_id")
        if lesson_id:
            lesson = (
                session.query(Lesson)
                .filter(Lesson.lesson_id == lesson_id)
                .first()
            )
            if lesson:
                return await format_lesson_message(lesson, user_lang)
    
    if lesson_request.get("lesson_id"):
        lesson_id = lesson_request.get("lesson_id")
        lesson = (
            session.query(Lesson)
            .filter(Lesson.lesson_id == lesson_id)
            .first()
        )
        if lesson:
            return await format_lesson_message(lesson, user_lang)
    
    return None


async def format_lesson_message(
    lesson: Lesson, language: Optional[str], call_ollama_fn=None
) -> str:
    """
    Format lesson for display with optional translation.

    Args:
        lesson: Lesson object from database
        language: Target language
        call_ollama_fn: Optional function to call Ollama (for translation)

    Returns:
        Formatted lesson text
    """
    text = f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"
    lang = (language or "en").lower()
    if lang in ["en"]:
        return text
    return await translate_text(text, lang, call_ollama_fn)


async def translate_text(text: str, language: str, call_ollama_fn=None) -> str:
    """
    Translate text to target language using Ollama.

    Args:
        text: Text to translate
        language: Target language
        call_ollama_fn: Optional function to call Ollama

    Returns:
        Translated text or original if translation fails
    """
    try:
        prompt = (
            f"Translate the following text to {language}. "
            "Preserve paragraph breaks and meaning. Return only the translation. Be as close to original text as possible. Text:\n\n"
            f"{text}"
        )
        call_fn = call_ollama_fn or _get_ollama_client()
        result = await call_fn(prompt, None, language)
        return result or text
    except Exception as e:
        logger.warning(f"Translation failed, sending original text: {e}")
        return text


# Helper: lazy import embedding service to avoid cycles during module import
def _get_embedding_service():
    try:
        from src.services.embedding_service import get_embedding_service

        return get_embedding_service()
    except Exception:
        return None


async def process_lesson_query(
    user_id: int,
    text: str,
    session: Session,
    prompt_builder: Optional[object],
    memory_manager: Optional[object],
    onboarding_flow: Optional[object],
    onboarding_service: Optional[object],
    user_language: Optional[str],
) -> Optional[str]:
    """
    Handle incoming lesson-related queries (e.g. "What's today's lesson?", "Lesson 3").

    Centralized handler: first try semantic trigger matching (embeddings),
    then fall back to regex-based detection.
    """
    # First run rule-based detection so explicit requests like
    # "lesson 13"/"lesson text 13"/"today's lesson" cannot be overridden by a
    # semantic trigger that might point to a different lesson.
    lesson_request = detect_lesson_request(text)
    if lesson_request:
        # If the user is in onboarding lesson-status step, let onboarding own
        # this message to keep state/schedule flow consistent.
        pending = None
        if memory_manager:
            pending = memory_manager.get_memory(
                user_id, MemoryKey.ONBOARDING_STEP_PENDING
            )
        if pending:
            val = (pending[0].get("value") or "").lower()
            if val == "lesson_status" and onboarding_flow:
                onboarding_resp = await onboarding_flow.handle_onboarding(
                    user_id, text, session
                )
                if onboarding_resp:
                    return onboarding_resp

        if lesson_request.get("today"):
            if not prompt_builder:
                return "I couldn't determine your current lesson. Tell me which lesson number you'd like, e.g. 'Lesson 7'."

            today_ctx = prompt_builder.get_today_lesson_context(user_id)
            state = today_ctx.get("state", {})
            lesson_id = state.get("lesson_id")
            if not lesson_id:
                return "I couldn't determine your current lesson. Tell me which lesson number you'd like, e.g. 'Lesson 7'."

            lesson = _find_lesson_by_id(session, int(lesson_id))
            if lesson:
                return await format_lesson_message(lesson, user_language)
            return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."

        lesson_id = lesson_request.get("lesson_id")
        if lesson_id:
            lesson = _find_lesson_by_id(session, int(lesson_id))
            if lesson:
                return await format_lesson_message(lesson, user_language)
            return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."

    # Try keyword-based short circuit before LLM call
    try:
        pre = await pre_llm_lesson_short_circuit(
            original_text=text,
            precomputed_embedding=None,  # No longer used
            user_id=user_id,
            session=session,
            prompt_builder=prompt_builder,
            user_lang=user_language,
        )
        if pre:
            return pre
    except Exception:
        # If short circuit fails, continue and let the caller handle it.
        pass

    return None
