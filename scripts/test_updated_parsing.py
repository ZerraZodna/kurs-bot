"""
Test the updated parsing logic.
"""

import os
import sys
import re
from pathlib import Path
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent.parent))

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def parse_lessons_from_text(text: str) -> list:
    """
    Parse lesson text into structured format (UPDATED VERSION).
    """
    lessons = {}
    
    # First, check for special "lesson X to Y" pattern
    lesson_range_pattern = r"lesson\s+(\d+)\s+to\s+(\d+)\n([^\n]+?)(?=\nlesson\s+\d+|$)"
    range_matches = list(re.finditer(lesson_range_pattern, text, re.MULTILINE | re.IGNORECASE))
    
    for match in range_matches:
        start_num = int(match.group(1))
        end_num = int(match.group(2))
        title = match.group(3).strip()
        
        # Extract content between this lesson and next lesson
        match_start = match.end()
        next_lesson = re.search(r"\nlesson\s+(\d+)", text[match_start:])
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
    lesson_pattern = r"lesson\s+(\d+)\n([^\n]+?)(?=\nlesson\s+\d+|$)"
    
    matches = re.finditer(lesson_pattern, text, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        lesson_num = int(match.group(1))
        
        # Skip if already in lessons (from range parsing above)
        if lesson_num in lessons:
            continue
        
        title = match.group(2).strip()
        
        # Extract content - find text between this lesson and next lesson
        match_start = match.end()
        next_lesson = re.search(r"\nlesson\s+(\d+)", text[match_start:])
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
        
        # Truncate if too long
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

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(text):,} characters\n")
    
    print(f"Parsing lessons...")
    lessons = parse_lessons_from_text(text)
    print(f"Found {len(lessons)} lessons\n")
    
    # Show first 3 lessons with full content
    print("="*60)
    print("FIRST 3 LESSONS")
    print("="*60)
    
    for lesson in lessons[:3]:
        print(f"\nLesson {lesson['lesson_id']}:")
        print(f"Title: {lesson['title']}")
        print(f"Content length: {len(lesson['content'])} chars")
        print(f"Content: {lesson['content'][:200]}...")
        print()
    
    # Specifically check lesson 1 and 2
    lesson1 = lessons[0]
    lesson2 = lessons[1]
    
    print("="*60)
    print("CHECKING LESSON BOUNDARIES")
    print("="*60)
    print(f"\nLesson 1 last 100 chars:")
    print(repr(lesson1['content'][-100:]))
    
    print(f"\nLesson 2 first 100 chars:")
    print(repr(lesson2['content'][:100]))
    
    # Check for overlaps
    if "lesson 2" in lesson1['content'].lower():
        print("\n[ERROR] Lesson 1 contains 'lesson 2'")
    else:
        print("\n[OK] Lesson 1 does NOT contain 'lesson 2'")
        
    if "lesson 1" in lesson2['content'].lower():
        print("[ERROR] Lesson 2 contains 'lesson 1'")
    else:
        print("[OK] Lesson 2 does NOT contain 'lesson 1'")

if __name__ == "__main__":
    main()
