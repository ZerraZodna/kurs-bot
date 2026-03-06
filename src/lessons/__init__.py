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
from .text_normalizer import _normalize_extracted_text_for_dump, normalize_dump_text
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


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for importing ACIM lessons from PDF into DB."""
    p = argparse.ArgumentParser(description="Import ACIM lessons from PDF into DB")
    p.add_argument('--pdf', type=Path, default=Path('src/data/Sparkly ACIM lessons-extracted.pdf'))
    p.add_argument('--no-clear', action='store_true', help='Do not clear existing lessons')
    p.add_argument('--dump-text', type=Path, help='Write extracted text to this file for inspection')
    p.add_argument('--verify', default=True, type=lambda v: v.lower() not in ("false","0","no"))
    p.add_argument('--limit', type=int, help='Limit number of lessons to import (for testing)')
    ns = p.parse_args(argv)

    pdf = ns.pdf
    if not pdf.exists():
        print(f"PDF not found: {pdf}")
        return 2

    print(f"📖 Reading ACIM lessons from: {pdf}")
    text = extract_formatted_text(pdf)

    if getattr(ns, 'dump_text', None):
        try:
            out_path = ns.dump_text
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_text = normalize_dump_text(text)
            out_path.write_text(out_text, encoding='utf8')
            print(f"🔧 Extracted text written to: {out_path}")
        except Exception as e:
            print(f"⚠️  Failed to write extracted text to {ns.dump_text}: {e}")

    # If we produced a normalized dump (`out_text`), use it as the
    # canonical source for parsing so the DB content matches the dump.
    if 'out_text' in locals():
        text = out_text
    else:
        # Apply the same normalization that would have been applied for dump
        text = _normalize_extracted_text_for_dump(text)

    print("🔍 Extracting lessons from PDF...")
    lessons = parse_lessons_from_text(text)
    print(f"Found {len(lessons)} candidate lessons in PDF")
    if not lessons:
        print("No lessons found — check PDF format. See docs/ACIM_LESSONS_IMPORT.md")
        return 3

    added = import_to_db(lessons, clear=(not ns.no_clear), limit=ns.limit)
    print(f"✅ Imported {added} lessons")

    if ns.verify:
        expected = len(lessons)
        ok = verify_db_count(expected)
        if not ok:
            print("⚠️  Verification failed: lesson count lower than expected")
            return 4
    return 0


# Backwards compatibility - import the main function for the old script location
def run_import(argv: Optional[list[str]] = None) -> int:
    """Backwards-compatible entry point."""
    return main(argv)


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

