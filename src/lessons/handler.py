"""Lesson retrieval and handling logic."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.models.database import Lesson


def _get_ollama_client():
    from src.services.dialogue.ollama_client import call_ollama

    return call_ollama


logger = logging.getLogger(__name__)


def _find_lesson_by_id(session: Session, lesson_id: int) -> Lesson | None:
    """Lookup lesson by id and best-effort import bundled lessons when missing."""
    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if lesson:
        return lesson

    from src.lessons.importer import ensure_lessons_available

    ok = ensure_lessons_available(session)
    if not ok:
        return None
    return session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()


async def format_lesson_message(lesson: Lesson, language: str | None, call_ollama_fn=None) -> str:
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
