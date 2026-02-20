"""Lesson retrieval and handling logic."""

from __future__ import annotations

import logging
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.config import settings
from src.services.dialogue import ollama_client

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
    text_lower = (text or "").lower()

    def _extract_number(s: str) -> Optional[int]:
        m = re.search(r"\b(?:lesson|leksjon|day)\s*#?\s*(\d+)\b", s)
        if m:
            try:
                n = int(m.group(1))
            except Exception:
                return None
            if 1 <= n <= 360:
                return n
            if 361 <= n <= 365:
                return 361
        return None

    # Direct command forms: "show lesson 6", "send me lesson 6", "give lesson 6"
    def _is_command_like(s: str) -> bool:
        return bool(re.search(r"^\s*(?:show|send|give|read|display)(?: me)?(?: the)?\b", s)) and "lesson" in s

    # 1) explicit numbered lesson
    num = _extract_number(text_lower)
    if num:
        return {"lesson_id": num}

    # 2) today's lesson
    if re.search(r"\btoday('?s)?\s+lesson\b", text_lower) or "todays lesson" in text_lower:
        return {"today": True}

    # 3) command-like without a number (e.g., "show lesson")
    if _is_command_like(text_lower):
        return {"raw_command": True}

    return None


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
        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()

        if not lesson:
            # If the lessons table is empty, attempt to import lessons from the
            # bundled PDF automatically to reduce friction on new hosts.
            session_count = session.query(Lesson).count()
            if session_count == 0:
                from pathlib import Path
                import importlib.util

                repo_root = Path(__file__).resolve().parents[3]
                script_path = repo_root / 'scripts' / 'utils' / 'import_acim_lessons.py'
                if script_path.exists():
                    try:
                        spec = importlib.util.spec_from_file_location("import_acim_lessons", str(script_path))
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        # Call main() to perform import; it returns an exit code
                        rc = mod.main([])
                        if rc == 0:
                            # re-query for the lesson after successful import
                            lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
                    except Exception:
                        # If importing fails, continue to return the not-found message
                        lesson = None

            if not lesson:
                return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."

        # Detect if the user explicitly asks for the exact/raw lesson text
        user_lower = user_input.lower()
        raw_triggers = [
            "text of lesson",
            "text for lesson",
            "the text of lesson",
            "what is the text of",
            "exact words",
            "exact text",
            "what exactly is",
            "give me the exact words",
            "give me the exact text",
            "exactly what",
        ]

        # Also treat direct 'show/send/give/read/display lesson' commands as raw requests
        def _is_command_like(s: str) -> bool:
            return bool(re.search(r"^\s*(?:show|send|give|read|display)(?: me)?(?: the)?\b", s)) and "lesson" in s

        is_raw_request = any(t in user_lower for t in raw_triggers) or bool(
            re.search(r"\bwhat exactly is\b.*\blesson\b", user_lower)
        ) or _is_command_like(user_lower)

        if is_raw_request:
            # Return raw lesson text directly (translate if needed)
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

        response = await ollama_client.call_ollama(prompt, None, user_language)
        return response

    except Exception as e:
        logger.error(f"[Lesson request error] Failed to handle lesson {lesson_id}: {e}")
        return f"I encountered an error retrieving lesson {lesson_id}. Please try again."


async def pre_llm_lesson_short_circuit(
    original_text: str,
    precomputed_embedding,
    user_id: int,
    session: Session,
    prompt_builder,
    user_lang: str,
) -> Optional[str]:
    """
    Check triggers on the original user text before calling the LLM and
    return a verbatim/formatted lesson message when a lesson-related trigger
    (next_lesson/raw_lesson) matches.

    This function intentionally avoids try/except so failures surface to the
    caller for observability.
    """
    from src.triggers.trigger_matcher import get_trigger_matcher

    matcher = get_trigger_matcher()
    matches = await matcher.match_triggers(original_text, precomputed_embedding=precomputed_embedding)
    for m in matches:
        if m.get("score", 0.0) >= m.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD):
            action = m.get("action_type")
            if action in ("next_lesson", "raw_lesson") and prompt_builder:
                today_ctx = prompt_builder.get_today_lesson_context(user_id)
                state = today_ctx.get("state", {})
                lesson_id = state.get("lesson_id")
                if lesson_id:
                    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
                    if lesson:
                        return await format_lesson_message(lesson, user_lang)


async def format_lesson_message(lesson: Lesson, language: Optional[str]) -> str:
    """
    Format lesson for display with optional translation.

    Args:
        lesson: Lesson object from database
        language: Target language
        call_ollama_fn: Function to call Ollama (for translation)

    Returns:
        Formatted lesson text
    """
    text = f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"
    lang = (language or "en").lower()
    if lang in ["en"]:
        return text
    return await translate_text(text, lang)


async def translate_text(text: str, language: str) -> str:
    """
    Translate text to target language using Ollama.

    Args:
        text: Text to translate
        language: Target language
        call_ollama_fn: Function to call Ollama

    Returns:
        Translated text or original if translation fails
    """
    try:
        prompt = (
            f"Translate the following text to {language}. "
            "Preserve paragraph breaks and meaning. Return only the translation. Be as close to original text as possible. Text:\n\n"
            f"{text}"
        )
        result = await ollama_client.call_ollama(prompt, None, language)
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
    # Compute embedding (embedding service is responsible for any
    # normalization/cleanup of the text). Use the pre-LLM trigger
    # matcher first (semantic short-circuit).
    precomputed_embedding = None
    emb_svc = _get_embedding_service()
    if emb_svc is not None:
        try:
            precomputed_embedding = await emb_svc.generate_embedding(text)
        except Exception:
            precomputed_embedding = None

    try:
        pre = await pre_llm_lesson_short_circuit(
            original_text=text,
            precomputed_embedding=precomputed_embedding,
            user_id=user_id,
            session=session,
            prompt_builder=prompt_builder,
            user_lang=user_language,
        )
        if pre:
            return pre
    except Exception:
        # If trigger matching fails, continue to regex fallback below.
        pass

    # Fall back to the rule-based detector if semantic matching didn't return.
    lesson_request = detect_lesson_request(text)
    if not lesson_request:
        return None

    # If the user is in the onboarding 'lesson_status' step, let onboarding
    # handle the message so we persist the lesson and create the default
    # schedule instead of sending the lesson content immediately.
    pending = None
    if memory_manager:
        pending = memory_manager.get_memory(user_id, "onboarding_step_pending")
    if pending:
        val = (pending[0].get("value") or "").lower()
        if val == "lesson_status" and onboarding_flow:
            onboarding_resp = await onboarding_flow.handle_onboarding(user_id, text, session)
            if onboarding_resp:
                return onboarding_resp

    # Support 'today' requests which need resolution to an actual lesson id
    if lesson_request.get("today") and prompt_builder:
        today_ctx = prompt_builder.get_today_lesson_context(user_id)
        state = today_ctx.get("state", {})
        lesson_id = state.get("lesson_id")
        if lesson_id:
            # Return the raw lesson text directly to avoid invoking the LLM
            lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if lesson:
                return await format_lesson_message(lesson, user_language)
        else:
            return "I couldn't determine your current lesson. Tell me which lesson number you'd like, e.g. 'Lesson 7'."

    if lesson_request.get("lesson_id"):
        # Return the raw lesson text directly to avoid invoking the LLM
        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_request["lesson_id"]).first()
        if lesson:
            return await format_lesson_message(lesson, user_language)

    return None
