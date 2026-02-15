"""Lesson retrieval and handling logic."""

from __future__ import annotations

import logging
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.config import settings
from src.services.dialogue.ollama_client import call_ollama

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
    text_lower = text.lower()

    lesson_patterns = [
        r"lesson\s+(\d+)",
        r"leksjon\s+(\d+)",
        r"day\s+(\d+)",
        r"lesson\s+#(\d+)",
    ]

    for pattern in lesson_patterns:
        match = re.search(pattern, text_lower)
        if match:
            lesson_num = int(match.group(1))
            if 1 <= lesson_num <= 360:
                return {"lesson_id": lesson_num}
            if 361 <= lesson_num <= 365:
                return {"lesson_id": 361}
    # Detect requests for "today's lesson" or similar phrasing
    if re.search(r"\btoday('?s)?\s+lesson\b", text_lower) or "todays lesson" in text_lower:
        return {"today": True}

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

        is_raw_request = any(t in user_lower for t in raw_triggers) or bool(
            re.search(r"\bwhat exactly is\b.*\blesson\b", user_lower)
        )

        if is_raw_request:
            # Return raw lesson text directly (translate if needed)
            return await format_lesson_message(lesson, user_language or "en", call_ollama)

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

        response = await call_ollama(prompt, None, user_language)
        return response

    except Exception as e:
        logger.error(f"[Lesson request error] Failed to handle lesson {lesson_id}: {e}")
        return f"I encountered an error retrieving lesson {lesson_id}. Please try again."


async def format_lesson_message(lesson: Lesson, language: str, call_ollama_fn) -> str:
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
    if language.lower() in ["en"]:
        return text
    return await translate_text(text, language, call_ollama_fn)


async def translate_text(text: str, language: str, call_ollama_fn) -> str:
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
            "Preserve paragraph breaks and meaning. Return only the translation.\n\n"
            f"{text}"
        )
        result = await call_ollama_fn(prompt)
        return result or text
    except Exception as e:
        logger.warning(f"Translation failed, sending original text: {e}")
        return text
