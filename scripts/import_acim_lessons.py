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


def clean_page_artifacts(content: str) -> str:
    """
    Remove PDF page artifacts from lesson content.
    
    Removes:
    - WORKBOOK markers with page numbers: "WORKBOOK \n##"
    - PART I markers with page numbers: "PART I\n##"
    - Orphaned page numbers: standalone numbers on their own line
    - Overlap across page boundaries (exact suffix/prefix overlap)
    """
    page_marker_pattern = r'(?:WORKBOOK\s*\n\d+|PART\s+I\s*\n\d+)'

    # Split by page markers to keep logical chunks
    parts = [p.strip() for p in re.split(page_marker_pattern, content, flags=re.IGNORECASE) if p.strip()]

    if not parts:
        return content

    merged = parts[0]
    for part in parts[1:]:
        merged = merge_with_overlap(merged, part)

    # Remove standalone page numbers at the end (just digits on a line)
    merged = re.sub(r'\s*\n\d+\s*$', '', merged)

    # Remove orphaned page numbers between content and the next section
    merged = re.sub(r'"\s*\n\d+\s*(?=[A-Z"])', r'"', merged)

    return merged


def merge_with_overlap(left: str, right: str, min_overlap: int = 60, max_overlap: int = 800) -> str:
    """
    Merge two strings by removing suffix/prefix overlap (whitespace-insensitive).

    This handles page-boundary overlap where the end of one page repeats at the start of the next,
    even when whitespace or line breaks differ.
    """
    left_sq, _ = squash_with_map(left)
    right_sq, right_map = squash_with_map(right)

    max_len = min(max_overlap, len(left_sq), len(right_sq))

    for overlap_len in range(max_len, min_overlap - 1, -1):
        if left_sq[-overlap_len:] == right_sq[:overlap_len]:
            cut_idx = right_map[overlap_len - 1] + 1
            return left + right[cut_idx:]

    return left + " " + right


def squash_with_map(text: str) -> tuple[str, list[int]]:
    """
    Remove whitespace for overlap detection while keeping a map to original indices.
    """
    mapping = []
    squashed_chars = []
    for idx, ch in enumerate(text):
        if ch.isspace():
            continue
        squashed_chars.append(ch)
        mapping.append(idx)
    return "".join(squashed_chars), mapping


def merge_wrapped_title(title: str, content: str) -> tuple[str, str]:
    """
    If the title is split across lines, pull the continuation from the start of content.

    Example:
      title: “I have given everything I see in this room [on this street, from this
      content starts: window, in this place] all the meaning that it has for me.” ...
    """
    title_stripped = title.strip()
    content_stripped = content.lstrip()

    if not title_stripped or not content_stripped:
        return title, content

    # If title has an opening quote but no closing quote, pull until closing quote
    has_open = "“" in title_stripped or '"' in title_stripped
    has_close = "”" in title_stripped or title_stripped.count('"') >= 2

    if has_open and not has_close:
        # Find closing quote in the content
        for quote in ["”", '"']:
            end_idx = content_stripped.find(quote)
            if end_idx != -1:
                # Include closing quote in title
                title = f"{title_stripped} {content_stripped[:end_idx + 1]}"
                content = content_stripped[end_idx + 1:].lstrip()
                return title, content

    return title, content


def parse_lessons_from_text(text: str) -> list:
    """
    Parse lesson text into structured format.
    Looks for patterns like "lesson 1" or numbered lessons.
    
    Note: PDF has duplicate lesson headers for page layout (lesson headers appear
    multiple times). We build a map of all occurrences and use specific logic to 
    extract complete content.
    
    Page artifacts are cleaned up:
    - Removes "WORKBOOK \n##" (page markers)
    - Removes "PART I ##" (section markers at page breaks)
    """
    lessons = {}  # Use dict to deduplicate by lesson_id
    
    # First, check for special "lesson X to Y" pattern (e.g., "lesson 361 to 365")
    lesson_range_pattern = r"lesson\s+(\d+)\s+to\s+(\d+)\n([^\n]+?)(?=\nlesson\s+\d+|$)"
    range_matches = list(re.finditer(lesson_range_pattern, text, re.MULTILINE | re.IGNORECASE))
    
    for match in range_matches:
        start_num = int(match.group(1))
        end_num = int(match.group(2))
        title = match.group(3).strip()
        
        # Extract content between this lesson and next lesson
        match_start = match.end()
        next_lesson = re.search(r"\nlesson\s+\d+", text[match_start:])
        if next_lesson:
            match_end = match_start + next_lesson.start()
        else:
            match_end = len(text)
        
        content = text[match_start:match_end].strip()
        
        # Clean up content: remove page artifacts
        content = clean_page_artifacts(content)
        
        # Fix title that wraps onto the first line of content
        title, content = merge_wrapped_title(title, content)

        # Clean up title and content
        title = re.sub(r'\s+', ' ', title)
        title = title.replace('\\', '').replace('"', '').strip()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if not title or len(title) < 2:
            title = f"Lesson {start_num} to {end_num}"
        
        # Truncate if too long
        if len(content) > 20000:
            content = content[:20000] + "..."
        
        # Create same lesson for each day in the range
        for day_num in range(start_num, end_num + 1):
            lessons[day_num] = {
                "lesson_id": day_num,
                "title": title,
                "content": content or f"Lesson {day_num}: {title}",
                "difficulty_level": "beginner",
                "duration_minutes": 15,
            }
    
    # Build a map of lesson occurrences: lesson_num -> list of match positions
    lesson_occurrences = {}
    lesson_pattern = r"lesson\s+(\d+)\n"
    
    for match in re.finditer(lesson_pattern, text, re.MULTILINE | re.IGNORECASE):
        lesson_num = int(match.group(1))
        if lesson_num not in lesson_occurrences:
            lesson_occurrences[lesson_num] = []
        lesson_occurrences[lesson_num].append(match)
    
    # Process each lesson
    for lesson_num in sorted(lesson_occurrences.keys()):
        # Skip if already processed (from range lessons)
        if lesson_num in lessons:
            continue
        
        matches = lesson_occurrences[lesson_num]
        if not matches:
            continue
        
        # Use the FIRST occurrence of this lesson header
        # PDF may have duplicate headers across pages, so we want the first
        # canonical appearance of the lesson
        match = matches[0]
        
        # Extract title (text after "lesson X\n")
        title_start = match.end()
        title_end = text.find('\n', title_start)
        if title_end == -1:
            title_end = len(text)
        title = text[title_start:title_end].strip()
        
        # Find content start (after the title line)
        content_start = title_end + 1 if title_end < len(text) else len(text)
        
        # Find where next lesson starts
        # Search for the NEXT lesson number that appears AFTER the current match
        content_end = len(text)  # Default to end of text
        for next_num in range(lesson_num + 1, lesson_num + 100):  # Check next ~100 lesson numbers
            if next_num in lesson_occurrences and lesson_occurrences[next_num]:
                # Find the FIRST occurrence of next lesson that is AFTER current match
                for next_match in lesson_occurrences[next_num]:
                    if next_match.start() > match.start():
                        content_end = next_match.start()
                        break
                if content_end != len(text):
                    break  # Found a valid boundary, stop searching
        
        content = text[content_start:content_end].strip()
        
        # Clean up content: remove page artifacts
        content = clean_page_artifacts(content)
        
        # Fix title that wraps onto the first line of content
        title, content = merge_wrapped_title(title, content)

        # Clean up title and content
        title = re.sub(r'\s+', ' ', title)
        title = title.replace('\\', '').replace('"', '').strip()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if not title or len(title) < 2:
            title = f"Lesson {lesson_num}"
        
        # Truncate if too long
        if len(content) > 20000:
            content = content[:20000] + "..."
        
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
