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
        r"day\s+(\d+)",
        r"lesson\s+#(\d+)",
        r"#(\d+)",
    ]

    for pattern in lesson_patterns:
        match = re.search(pattern, text_lower)
        if match:
            lesson_num = int(match.group(1))
            if 1 <= lesson_num <= 365:
                return {"lesson_id": lesson_num}

    return None


async def handle_lesson_request(
    lesson_id: int, user_input: str, session: Session
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

        # Build RAG-enhanced prompt with lesson content
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

        response = await call_ollama(prompt)
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
    if language.lower() in ["english", "en"]:
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
