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
    
    # Lesson delivery functions
    from src.lessons import maybe_send_next_lesson, get_current_lesson, set_current_lesson
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# PDF import functions
from .pdf_extractor import extract_formatted_text
from .lesson_parser import parse_lessons_from_text
from .db_importer import import_to_db, verify_db_count

# Lesson delivery/progression functions (restored from original exports)
from .advance import is_simple_greeting, maybe_send_next_lesson
from .handler import format_lesson_message, translate_text
from .importer import ensure_lessons_available
from .state import (
    compute_current_lesson_state,
    get_current_lesson,
    get_lesson_state,
    has_lesson_status,
    set_current_lesson,
    set_next_lesson,
)
from .state_flow import apply_reported_progress, determine_lesson_action



__all__ = [
    # PDF import functions
    'extract_formatted_text',
    'parse_lessons_from_text',
    'import_to_db',
    'verify_db_count',
    # CLI entry points
    'main',
    'run_import',
    # Lesson delivery/progression functions
    'is_simple_greeting',
    'maybe_send_next_lesson',
    'format_lesson_message',
    'translate_text',
    'ensure_lessons_available',
    'compute_current_lesson_state',
    'get_current_lesson',
    'get_lesson_state',
    'has_lesson_status',
    'set_current_lesson',
    'set_next_lesson',
    'apply_reported_progress',
    'determine_lesson_action',
]

