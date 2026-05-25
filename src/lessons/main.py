#!/usr/bin/env python3
"""Main entry point for ACIM lessons import from PDF."""

import argparse
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_formatted_text(pdf_path: Path) -> str:
    """Extract formatted text from PDF."""
    from .pdf_extractor import extract_formatted_text as extract

    return extract(pdf_path)


def parse_lessons_from_text(text: str) -> list:
    """Parse lessons from formatted text."""
    from .lesson_parser import parse_lessons_from_text as parse

    return parse(text)


def import_to_db(lessons: list, clear: bool = False) -> int:
    """Import parsed lessons into database."""
    from .db_importer import import_to_db as import_

    return import_(lessons, clear=clear)


def main() -> int:
    """Main entry point for ACIM lessons import."""
    parser = argparse.ArgumentParser(description="Import ACIM lessons from PDF")
    parser.add_argument("--pdf", type=str, help="Path to ACIM lessons PDF")
    parser.add_argument("--clear", action="store_true", help="Clear existing lessons before import")
    parser.add_argument("--no-clear", action="store_true", help="Preserve existing lessons")
    parser.add_argument("--verify", action="store_true", help="Verify import count")
    parser.add_argument("--dump-text", type=str, help="Dump extracted text to file (for debugging)")

    args = parser.parse_args()

    # Validate PDF path
    if not args.pdf:
        logger.error("Please specify --pdf path to ACIM lessons PDF file")
        return 1

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return 1

    logger.info(f"Reading ACIM lessons from: {pdf_path}")
    logger.info(f"File size: {pdf_path.stat().st_size / 1024:.2f} KB")

    try:
        # Extract text from PDF
        logger.info("Extracting formatted text from PDF...")
        text = extract_formatted_text(pdf_path)

        # Save extracted text for debugging
        if args.dump_text:
            with open(args.dump_text, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Extracted text saved to: {args.dump_text}")

        # Parse lessons
        logger.info("Parsing lessons from text...")
        lessons = parse_lessons_from_text(text)

        if not lessons:
            logger.error("No lessons found in PDF!")
            return 1

        logger.info(f"Found {len(lessons)} lessons in PDF")

        if len(lessons) > 10:
            logger.info("First 3 lessons found:")
            for i, (_lid, title, _content) in enumerate(lessons[:3], 1):
                logger.info(f"  - Lesson {i}: {title[:80]}...")

        # Import to database
        clear_flag = args.clear or (not args.no_clear and not len(lessons))
        logger.info(f"Importing lessons to database... {'Clearing existing' if clear_flag else 'Preserving existing'}")

        added = import_to_db(lessons, clear=clear_flag)

        logger.info(f"✅ Successfully imported {added} lessons")

        # Verify
        if args.verify:
            if added >= 365:
                logger.info("✅ All ACIM lessons successfully imported!")
            else:
                logger.warning(f"⚠️ Only {added} lessons imported (expected 365)")

        return 0

    except Exception as e:
        logger.exception(f"Failed to import lessons: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
