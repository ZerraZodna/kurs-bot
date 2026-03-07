"""CLI entry point for the lesson import system.

Provides a command-line interface for importing ACIM lessons from PDFs.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from . import extractor, normalizer, parser, writer


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging.
    
    Args:
        verbose: If True, use DEBUG level logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def run_import(
    argv: Optional[list[str]] = None,
    pdf_path: Optional[Path] = None,
) -> int:
    """Run the full import pipeline.
    
    Pipeline steps:
    1. Extract text from PDF
    2. Normalize extracted text
    3. Parse lessons from normalized text
    4. Write to database
    
    Args:
        argv: Command line arguments (if None, uses sys.argv).
        pdf_path: Override PDF path (for programmatic use).
        
    Returns:
        Exit code (0 = success).
    """
    # Parse arguments
    parser_args = argparse.ArgumentParser(
        description="Import ACIM lessons from PDF into DB"
    )
    parser_args.add_argument(
        '--pdf', 
        type=Path, 
        default=Path('src/data/Sparkly ACIM lessons-extracted.pdf')
    )
    parser_args.add_argument(
        '--no-clear',
        action='store_true',
        help='Do not clear existing lessons'
    )
    parser_args.add_argument(
        '--dump-text',
        type=Path,
        help='Write extracted text to this file for inspection'
    )
    parser_args.add_argument(
        '--verify',
        default=True,
        type=lambda v: v.lower() not in ("false", "0", "no")
    )
    parser_args.add_argument(
        '--limit',
        type=int,
        help='Limit number of lessons to import (for testing)'
    )
    parser_args.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    ns = parser_args.parse_args(argv)
    
    # Use provided path or parsed argument
    pdf = pdf_path or ns.pdf
    
    setup_logging(ns.verbose)
    
    # Validate PDF exists
    if not pdf.exists():
        logger.error(f"PDF not found: {pdf}")
        return 2
    
    logger.info(f"Reading ACIM lessons from: {pdf}")
    
    # Step 1: Extract text from PDF
    logger.info("Extracting text from PDF...")
    text = extractor.extract_pdf_text(pdf)
    logger.info(f"Extracted {len(text)} characters")
    
    # Optional: write extracted text for inspection
    if getattr(ns, 'dump_text', None):
        dump_path = ns.dump_text
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use dump-specific normalization
        dump_text = normalizer.normalize_for_dump(text)
        dump_path.write_text(dump_text, encoding='utf8')
        logger.info(f"Extracted text written to: {dump_path}")
        
        # Use dump text for parsing
        text = dump_text
    else:
        # Apply standard normalization
        text = normalizer.normalize_text(text)
    
    # Step 2: Parse lessons
    logger.info("Parsing lessons from text...")
    lessons = parser.parse_lessons(text)
    logger.info(f"Found {len(lessons)} lessons")
    
    if not lessons:
        logger.error("No lessons found - check PDF format")
        return 3
    
    # Apply limit if specified
    if ns.limit is not None:
        lessons = lessons[:ns.limit]
        logger.info(f"Limited to {len(lessons)} lessons")
    
    # Step 3: Import to database
    logger.info("Importing lessons to database...")
    added = writer.import_to_db(
        lessons, 
        clear=not ns.no_clear,
        verify=ns.verify,
    )
    logger.info(f"Successfully imported {added} lessons")
    
    # Verification
    if ns.verify:
        expected = len(lessons)
        if not writer.verify_db_count(expected):
            logger.warning(f"Verification failed: expected {expected}")
            return 4
    
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.
    
    Args:
        argv: Command line arguments.
        
    Returns:
        Exit code.
    """
    try:
        return run_import(argv)
    except Exception as e:
        logger.exception(f"Import failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

