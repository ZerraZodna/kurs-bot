"""Centralized language and prompt package.

Translation is centralized in translation_service.py - the ONLY place translations occur."""

from .keyword_detector import detect_language as detect_language_keywords
from .language_service import detect_and_store_language, detect_language
from .prompt_builder import PromptBuilder
from .prompt_optimizer import PromptOptimizer
from .translation_service import translate_text

__all__ = [
    "PromptBuilder",
    "PromptOptimizer",
    "detect_language",
    "detect_and_store_language",
    "detect_language_keywords",
    "translate_text",
]
