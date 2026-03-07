"""ACIM Lessons Import Package.

A clean, modular re-imagination of the PDF import system.

Architecture:
- reader.py: PDF reading abstraction
- extractor.py: Text extraction from PDF pages
- normalizer.py: Text normalization pipeline
- parser.py: Lesson structure parsing
- writer.py: Database import
- cli.py: CLI entry point

Usage:
    # Run full import
    from src.lessons.pdf_import import run_import
    result = run_import(['--pdf', 'path/to/pdf.pdf'])

    # Or use individual components
    from src.lessons.pdf_import import extract_pdf_text, parse_lessons, import_to_db
    
    # CLI entry point
    python -m src.lessons.pdf_import --pdf path/to/file.pdf
"""
from __future__ import annotations

from .cli import run_import, main
from .extractor import extract_pdf_text
from .parser import parse_lessons
from .writer import import_to_db, verify_db_count

__all__ = [
    'run_import',
    'main',
    'extract_pdf_text',
    'parse_lessons',
    'import_to_db',
    'verify_db_count',
]

