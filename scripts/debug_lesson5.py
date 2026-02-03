"""
Debug Lesson 5 content and boundary issues.
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

def debug_lesson_5(text: str) -> None:
    """Debug lesson 5 extraction."""
    
    # Find lesson 5
    lesson5_pattern = r"lesson\s+5\n([^\n]+?)(?=\nlesson\s+\d+|$)"
    lesson5_match = re.search(lesson5_pattern, text, re.MULTILINE | re.IGNORECASE)
    
    if not lesson5_match:
        print("Lesson 5 not found!")
        return
    
    print("LESSON 5 ANALYSIS")
    print("="*60)
    print(f"Match start: {lesson5_match.start()}")
    print(f"Match end: {lesson5_match.end()}")
    
    # Find next lesson (lesson 6)
    lesson6_pattern = r"\nlesson\s+6"
    lesson6_match = re.search(lesson6_pattern, text[lesson5_match.end():])
    
    if lesson6_match:
        print(f"\nLesson 6 found at position: {lesson5_match.end() + lesson6_match.start()}")
        
        # Extract full content between lesson 5 and lesson 6
        match_start = lesson5_match.end()
        match_end = lesson5_match.end() + lesson6_match.start()
        
        content = text[match_start:match_end]
        print(f"Content length: {len(content)} chars")
        print(f"\nLast 500 chars of Lesson 5 content:")
        print(repr(content[-500:]))
        
        print(f"\nFirst 200 chars after 'lesson 6':")
        full_lesson6_end = lesson5_match.end() + lesson6_match.end()
        print(repr(text[full_lesson6_end:full_lesson6_end+200]))
    
    # Look for all occurrences of "lesson 5"
    lesson5_all = list(re.finditer(r"lesson\s+5", text, re.IGNORECASE))
    print(f"\n\nFound {len(lesson5_all)} occurrences of 'lesson 5':")
    for i, match in enumerate(lesson5_all):
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 100)
        print(f"\n  Occurrence {i+1}:")
        print(f"  {repr(text[start:end])}")

def check_page_breaks(text: str) -> None:
    """Check for page break patterns."""
    print("\n\nPAGE BREAK ANALYSIS")
    print("="*60)
    
    # Look for page markers
    workbook_matches = list(re.finditer(r"WORKBOOK\s+\d+", text))
    print(f"Found {len(workbook_matches)} WORKBOOK markers")
    
    part_matches = list(re.finditer(r"PART\s+I", text))
    print(f"Found {len(part_matches)} PART I markers")
    
    # Check text around lesson 5 and 6
    lesson5_start = text.find("lesson 5\n")
    lesson6_start = text.find("\nlesson 6")
    
    if lesson5_start != -1 and lesson6_start != -1:
        print(f"\nDistance from lesson 5 to lesson 6: {lesson6_start - lesson5_start} chars")
        
        middle_section = text[lesson5_start:lesson6_start]
        
        # Count page markers in between
        workbook_in_middle = middle_section.count("WORKBOOK")
        part_in_middle = middle_section.count("PART I")
        
        print(f"WORKBOOK markers between lesson 5 and 6: {workbook_in_middle}")
        print(f"PART I markers between lesson 5 and 6: {part_in_middle}")

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...\n")
    text = extract_text_from_pdf(pdf_path)
    
    debug_lesson_5(text)
    check_page_breaks(text)

if __name__ == "__main__":
    main()
