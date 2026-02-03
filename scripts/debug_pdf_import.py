"""
Debug script to analyze PDF import issues.
Tests the lesson extraction and parsing logic.
"""

import os
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF using available libraries."""
    try:
        from pypdf import PdfReader
        print("✅ Using pypdf library")
        reader = PdfReader(pdf_path)
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            print(f"   Page {i+1}: {len(page_text)} chars")
            text += page_text + "\n"
        return text
    except ImportError:
        try:
            import pdfplumber
            print("✅ Using pdfplumber library")
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    print(f"   Page {i+1}: {len(page_text)} chars")
                    text += page_text + "\n"
            return text
        except ImportError:
            print("❌ Neither pypdf nor pdfplumber installed")
            return None


def analyze_lesson_patterns(text: str) -> None:
    """Analyze lesson patterns in extracted text."""
    print("\n" + "="*60)
    print("ANALYZING LESSON PATTERNS")
    print("="*60)
    
    # Look for lesson patterns
    print("\n1️⃣  Looking for 'Lesson X to Y' patterns...")
    lesson_range_pattern = r"Lesson\s+(\d+)\s+to\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    range_matches = list(re.finditer(lesson_range_pattern, text, re.MULTILINE | re.IGNORECASE))
    print(f"   Found {len(range_matches)} range patterns")
    for match in range_matches[:5]:
        print(f"     - Lesson {match.group(1)} to {match.group(2)}: {match.group(3)[:50]}")
    
    # Look for regular numbered lessons
    print("\n2️⃣  Looking for 'Lesson X:' patterns...")
    lesson_pattern = r"Lesson\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    matches = list(re.finditer(lesson_pattern, text, re.MULTILINE | re.IGNORECASE))
    print(f"   Found {len(matches)} lesson patterns")
    
    # Get unique lesson numbers
    lesson_nums = set()
    for match in matches:
        try:
            lesson_nums.add(int(match.group(1)))
        except:
            pass
    
    print(f"   Unique lesson numbers found: {len(lesson_nums)}")
    if lesson_nums:
        sorted_nums = sorted(lesson_nums)
        print(f"   Range: {sorted_nums[0]} to {sorted_nums[-1]}")
        print(f"   First 10: {sorted_nums[:10]}")
        print(f"   Last 10: {sorted_nums[-10:]}")
        
        # Check for gaps
        expected = set(range(sorted_nums[0], sorted_nums[-1] + 1))
        missing = expected - lesson_nums
        if missing:
            print(f"   ⚠️  Missing {len(missing)} lesson numbers: {sorted(missing)[:20]}")
    
    # Show sample of raw text
    print("\n3️⃣  Sample of raw extracted text (first 1000 chars):")
    print("-" * 60)
    print(text[:1000])
    print("-" * 60)
    
    # Look for line breaks and structure
    print("\n4️⃣  Text structure analysis:")
    lines = text.split('\n')
    print(f"   Total lines: {len(lines)}")
    
    # Show lines that contain "Lesson"
    lesson_lines = [line for line in lines if 'Lesson' in line]
    print(f"   Lines containing 'Lesson': {len(lesson_lines)}")
    print("   First 10 lesson lines:")
    for line in lesson_lines[:10]:
        print(f"     {line[:80]}")


def test_parsing_logic(text: str) -> None:
    """Test the actual parsing logic from import_acim_lessons.py"""
    print("\n" + "="*60)
    print("TESTING PARSING LOGIC")
    print("="*60)
    
    lessons = {}
    
    # First, check for special "Lesson X to Y" pattern
    lesson_range_pattern = r"Lesson\s+(\d+)\s+to\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    range_matches = list(re.finditer(lesson_range_pattern, text, re.MULTILINE | re.IGNORECASE))
    
    print(f"\n✅ Found {len(range_matches)} range lessons")
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
            
        print(f"   Created {end_num - start_num + 1} lessons for days {start_num}-{end_num}")
    
    # Then, parse regular numbered lessons
    lesson_pattern = r"Lesson\s+(\d+)[:\s]+([^\n]+?)(?=\n|Lesson\s+\d+|$)"
    matches = re.finditer(lesson_pattern, text, re.MULTILINE | re.IGNORECASE)
    
    regular_count = 0
    for match in matches:
        lesson_num = int(match.group(1))
        
        # Skip if already in lessons (from range parsing above)
        if lesson_num in lessons:
            continue
        
        title = match.group(2).strip()
        
        # Extract content
        match_start = match.end()
        next_lesson = re.search(r"Lesson\s+(\d+|(\d+\s+to\s+\d+))[:\s]+", text[match_start:])
        if next_lesson:
            match_end = match_start + next_lesson.start()
        else:
            match_end = len(text)
        
        content = text[match_start:match_end].strip()
        
        # Clean up
        title = re.sub(r'\s+', ' ', title)
        title = title.replace('\\', '').replace('"', '').strip()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if not title or len(title) < 2:
            title = f"Lesson {lesson_num}"
        
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        lessons[lesson_num] = {
            "lesson_id": lesson_num,
            "title": title,
            "content": content or f"Lesson {lesson_num}: {title}",
            "difficulty_level": "beginner",
            "duration_minutes": 15,
        }
        
        regular_count += 1
    
    print(f"✅ Found {regular_count} regular numbered lessons")
    print(f"\n📊 TOTAL LESSONS EXTRACTED: {len(lessons)}")
    
    # Show sample lessons
    if lessons:
        sorted_lessons = sorted(lessons.values(), key=lambda x: x["lesson_id"])
        print("\n📚 Sample extracted lessons:")
        print(f"   Lesson 1: {sorted_lessons[0]['title']}")
        print(f"     Content preview: {sorted_lessons[0]['content'][:100]}...")
        
        if len(sorted_lessons) > 5:
            print(f"   Lesson {sorted_lessons[5]['lesson_id']}: {sorted_lessons[5]['title']}")
            print(f"     Content preview: {sorted_lessons[5]['content'][:100]}...")
        
        if len(sorted_lessons) > 180:
            print(f"   Lesson {sorted_lessons[180]['lesson_id']}: {sorted_lessons[180]['title']}")
            print(f"     Content preview: {sorted_lessons[180]['content'][:100]}...")
        
        last_lesson = sorted_lessons[-1]
        print(f"   Lesson {last_lesson['lesson_id']}: {last_lesson['title']}")
        print(f"     Content preview: {last_lesson['content'][:100]}...")
    
    return lessons


def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"📖 Analyzing PDF: {pdf_path}")
    print(f"File size: {os.path.getsize(pdf_path) / 1024 / 1024:.2f} MB\n")
    
    # Extract text
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        print("❌ Failed to extract text")
        sys.exit(1)
    
    print(f"✅ Extracted {len(text):,} characters\n")
    
    # Analyze patterns
    analyze_lesson_patterns(text)
    
    # Test parsing
    lessons = test_parsing_logic(text)
    
    print("\n" + "="*60)
    print("DEBUG COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
