"""
Import ACIM lessons from PDF into the database.

This script extracts lessons from the ACIM PDF and populates the lessons table.
Each lesson is stored with title, content, and metadata.

Usage:
    python scripts/import_acim_lessons.py --pdf src/data/Sparkly\ ACIM\ lessons-extracted.pdf
    python scripts/import_acim_lessons.py --pdf src/data/Sparkly\ ACIM\ lessons-extracted.pdf --clear
"""

import os
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson, init_db


def extract_lessons_from_pdf(pdf_path: str) -> list:
    """
    Extract lessons from PDF file.
    Attempts to use pypdf first, falls back to pdfplumber if available.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return parse_lessons_from_text(text)
    except ImportError:
        try:
            import pdfplumber
            lessons = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lessons.extend(parse_lessons_from_text(text))
            return lessons
        except ImportError:
            print("ERROR: Neither 'pypdf' nor 'pdfplumber' is installed.")
            print("Install with: pip install pypdf")
            sys.exit(1)


def parse_lessons_from_text(text: str) -> list:
    """
    Parse lesson text into structured format.
    Looks for patterns like "Lesson 1: Title..." or numbered lessons.
    Handles special case of "Lesson 361 to 365" (single lesson spanning 5 days).
    """
    lessons = {}  # Use dict to deduplicate by lesson_id
    
    # First, check for special "Lesson X to Y" pattern (e.g., "Lesson 361 to 365")
    lesson_range_pattern = r"Lesson\s+(\d+)\s+to\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    range_matches = list(re.finditer(lesson_range_pattern, text, re.MULTILINE | re.IGNORECASE))
    
    for match in range_matches:
        start_num = int(match.group(1))
        end_num = int(match.group(2))
        title = match.group(3).strip()
        
        # Extract content between this lesson and next lesson
        match_start = match.end()
        next_lesson = re.search(r"Lesson\s+(\d+|(\d+\s+to\s+\d+))[:\s]+", text[match_start:])
        if next_lesson:
            match_end = match_start + next_lesson.start()
        else:
            match_end = len(text)
        
        content = text[match_start:match_end].strip()
        
        # Clean up title and content
        title = re.sub(r'\s+', ' ', title)
        title = title.replace('\\', '').replace('"', '').strip()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if not title or len(title) < 2:
            title = f"Lesson {start_num} to {end_num}"
        
        # Truncate if too long
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        # Create same lesson for each day in the range
        for day_num in range(start_num, end_num + 1):
            lessons[day_num] = {
                "lesson_id": day_num,
                "title": title,
                "content": content or f"Lesson {day_num}: {title}",
                "difficulty_level": "beginner",
                "duration_minutes": 15,
            }
    
    # Then, parse regular numbered lessons
    lesson_pattern = r"Lesson\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    
    matches = re.finditer(lesson_pattern, text, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        lesson_num = int(match.group(1))
        
        # Skip if already in lessons (from range parsing above)
        if lesson_num in lessons:
            continue
        
        title = match.group(2).strip()
        
        # Extract content - find text between this lesson and next lesson
        match_start = match.end()
        next_lesson = re.search(r"Lesson\s+(\d+|(\d+\s+to\s+\d+))[:\s]+", text[match_start:])
        if next_lesson:
            match_end = match_start + next_lesson.start()
        else:
            match_end = len(text)
        
        content = text[match_start:match_end].strip()
        
        # Clean up title and content
        title = re.sub(r'\s+', ' ', title)
        title = title.replace('\\', '').replace('"', '').strip()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if not title or len(title) < 2:
            title = f"Lesson {lesson_num}"
        
        # Truncate if too long (keep first 3000 chars of content)
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        lessons[lesson_num] = {
            "lesson_id": lesson_num,
            "title": title,
            "content": content or f"Lesson {lesson_num}: {title}",
            "difficulty_level": "beginner",
            "duration_minutes": 15,
        }
    
    return sorted(lessons.values(), key=lambda x: x["lesson_id"])


def import_lessons_to_db(lessons: list, clear_existing: bool = False) -> int:
    """
    Import lessons into the database.
    
    Args:
        lessons: List of lesson dicts with title, content, etc.
        clear_existing: If True, delete all existing lessons before importing
    
    Returns:
        Number of lessons imported
    """
    session = SessionLocal()
    try:
        init_db()
        
        if clear_existing:
            session.query(Lesson).delete()
            session.commit()
            print(f"Cleared existing lessons")
        
        count = 0
        now = datetime.now(timezone.utc)
        
        for lesson_data in lessons:
            # Check if lesson already exists
            existing = session.query(Lesson).filter(
                Lesson.lesson_id == lesson_data.get("lesson_id")
            ).first()
            
            if existing:
                # Update existing lesson
                for key, value in lesson_data.items():
                    if key != "lesson_id" and hasattr(existing, key):
                        setattr(existing, key, value)
                session.add(existing)
            else:
                # Create new lesson
                lesson = Lesson(
                    lesson_id=lesson_data.get("lesson_id"),
                    title=lesson_data["title"],
                    content=lesson_data["content"],
                    difficulty_level=lesson_data.get("difficulty_level", "beginner"),
                    duration_minutes=lesson_data.get("duration_minutes", 15),
                    created_at=now,
                )
                session.add(lesson)
            
            count += 1
            if count % 50 == 0:
                session.commit()
                print(f"  Imported {count} lessons...")
        
        session.commit()
        print(f"\n✅ Successfully imported {count} lessons")
        return count
    
    except Exception as e:
        session.rollback()
        print(f"❌ Error importing lessons: {e}")
        raise
    finally:
        session.close()


def verify_lessons(expected_count: int = 365) -> None:
    """Verify that lessons were imported correctly."""
    session = SessionLocal()
    try:
        count = session.query(Lesson).count()
        print(f"\n📊 Database now contains {count} lessons")
        
        if count == expected_count:
            print(f"✅ All {expected_count} ACIM lessons successfully imported!")
        elif count > 0:
            print(f"⚠️  Expected {expected_count} lessons, found {count}")
        else:
            print(f"❌ No lessons found in database")
        
        # Show a sample
        sample = session.query(Lesson).order_by(Lesson.lesson_id).limit(3).all()
        if sample:
            print(f"\nSample lessons:")
            for lesson in sample:
                print(f"  - Lesson {lesson.lesson_id}: {lesson.title}")
                print(f"    Content preview: {lesson.content[:100]}...")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Import ACIM lessons from PDF to database")
    parser.add_argument(
        "--pdf",
        default="src/data/Sparkly ACIM lessons-extracted.pdf",
        help="Path to the ACIM lessons PDF file"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=True,
        help="Clear existing lessons before importing (default: True)"
    )
    parser.add_argument(
        "--no-clear",
        action="store_false",
        dest="clear",
        help="Do not clear existing lessons"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify lessons after import"
    )
    
    args = parser.parse_args()
    
    # Check if PDF exists
    if not os.path.exists(args.pdf):
        print(f"❌ PDF file not found: {args.pdf}")
        sys.exit(1)
    
    print(f"📖 Reading ACIM lessons from: {args.pdf}")
    print(f"File size: {os.path.getsize(args.pdf) / 1024 / 1024:.2f} MB")
    
    # Extract lessons
    print("\n🔍 Extracting lessons from PDF...")
    lessons = extract_lessons_from_pdf(args.pdf)
    print(f"Found {len(lessons)} lessons in PDF")
    
    if not lessons:
        print("❌ No lessons could be extracted from the PDF")
        print("\nTroubleshooting:")
        print("1. Ensure the PDF is in the correct format")
        print("2. Try installing: pip install pypdf pdfplumber")
        sys.exit(1)
    
    # Show first few lessons
    print("\nFirst 3 lessons found:")
    for lesson in lessons[:3]:
        print(f"  - Lesson {lesson['lesson_id']}: {lesson['title']}")
    
    # Import to database
    print("\n💾 Importing lessons to database...")
    count = import_lessons_to_db(lessons, clear_existing=args.clear)
    
    # Verify
    if args.verify:
        verify_lessons(expected_count=len(lessons))


if __name__ == "__main__":
    main()
