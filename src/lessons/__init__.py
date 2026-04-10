"""ACIM Lessons import, delivery, and management.

This package provides:
- pdf_extractor: Extract formatted text from ACIM PDF using PyMuPDF
- text_normalizer: Normalize extracted text for parsing
- lesson_parser: Parse lessons from normalized text
- db_importer: Import lessons into the database
- Lesson delivery: send lessons to users, track progress, handle state

Usage:
    # Import lessons from PDF to DB
    from src.lessons import main
    main()

    # Or use individual components
    from src.lessons import extract_formatted_text, parse_lessons_from_text, import_to_db
"""

# PDF import functions
# Lesson delivery/progression functions (restored from original exports)
from .db_importer import import_to_db, verify_db_count
from .handler import get_english_lesson_text
from .importer import ensure_lessons_available
from .lesson_parser import parse_lessons_from_text
from .pdf_extractor import extract_formatted_text
from .state import (
    compute_current_lesson_state,
    get_current_lesson,
    get_lesson_state,
    has_lesson_status,
    set_current_lesson,
)

__all__ = [
    # PDF import functions
    "extract_formatted_text",
    "parse_lessons_from_text",
    "import_to_db",
    "verify_db_count",
    # CLI entry points
    # Lesson delivery/progression functions
    "ensure_lessons_available",
    "compute_current_lesson_state",
    "get_current_lesson",
    "get_lesson_state",
    "has_lesson_status",
    "set_current_lesson",
    "get_english_lesson_text",
]
