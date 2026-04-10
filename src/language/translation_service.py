"""Centralized translation service. ONLY place where translation happens."""

import logging
from typing import Callable

from src.services.dialogue.ollama_client import call_ollama

logger = logging.getLogger(__name__)


async def translate_text(english_text: str, target_language: str, ollama_callable: Callable | None = None) -> str:
    """
    Translate English text to target language using Ollama.

    Args:
        english_text: Source text (always English)
        target_language: Target language code (e.g., 'no', 'de')
        ollama_callable: Optional async callable(prompt, model=None, language=None) -> str

    Returns:
        Translated text, or original English if translation fails/is English.
    """
    lang = (target_language or "en").lower().strip()
    if lang in ["en", "english"]:
        return english_text

    try:
        prompt = (
            f"Translate the following text to {target_language}. "
            "Preserve paragraph breaks, formatting, and meaning exactly. "
            "Return ONLY the translation, no explanations. Be as close to original as possible.\n\n"
            f"{english_text}"
        )
        call_fn = ollama_callable or call_ollama
        result = await call_fn(prompt, None, target_language)
        return result.strip() or english_text
    except Exception as e:
        logger.warning(f"Translation to {target_language} failed: {e}")
        return english_text
