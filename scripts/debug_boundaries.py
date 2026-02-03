"""
Debug the lesson boundary detection in the PDF.
"""

import os
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def debug_lesson_boundaries(text: str) -> None:
    """Debug the lesson boundary detection."""
    print("DEBUGGING LESSON BOUNDARY DETECTION")
    print("="*60)
    
    # Find where "Lesson 1:" starts
    lesson1_match = re.search(r"Lesson\s+1[:\s]+([^\n]+)", text)
    if not lesson1_match:
        print("Lesson 1 not found!")
        return
    
    lesson1_start = lesson1_match.start()
    lesson1_title_end = lesson1_match.end()
    
    print(f"Lesson 1 found at position {lesson1_start}")
    print(f"Lesson 1 title: {lesson1_match.group(1)[:80]}")
    print(f"\nText around Lesson 1 start (100 chars before and 200 after):")
    print(f"...{text[lesson1_start-50:lesson1_start]}[LESSON 1 START]{text[lesson1_start:lesson1_start+150]}...")
    
    # Now find the next lesson marker after Lesson 1
    search_from = lesson1_title_end
    next_lesson_pattern = r"Lesson\s+(\d+|(\d+\s+to\s+\d+))[:\s]+"
    next_match = re.search(next_lesson_pattern, text[search_from:])
    
    if next_match:
        next_lesson_pos = search_from + next_match.start()
        next_lesson_num = next_match.group(1)
        
        print(f"\nNext lesson found at position {next_lesson_pos}")
        print(f"Next lesson number: {next_lesson_num}")
        
        # Show the boundary area
        boundary_start = next_lesson_pos - 100
        boundary_end = next_lesson_pos + 200
        
        print(f"\nText around lesson boundary (100 chars before, 200 after):")
        print(f"...{text[boundary_start:next_lesson_pos]}[NEXT LESSON START]{text[next_lesson_pos:boundary_end]}...")
        
        # Calculate what would be extracted as Lesson 1 content
        lesson1_content = text[lesson1_title_end:next_lesson_pos]
        print(f"\n📊 Extracted Lesson 1 content:")
        print(f"   Length: {len(lesson1_content)} chars")
        print(f"   First 150 chars: {lesson1_content[:150]}")
        print(f"   Last 150 chars: {lesson1_content[-150:]}")
        
        # Check if it contains "lesson 2"
        if "lesson 2" in lesson1_content.lower():
            print(f"\n⚠️  WARNING: Lesson 1 content contains 'lesson 2'!")
            pos = lesson1_content.lower().find("lesson 2")
            print(f"   Position: {pos}")
            print(f"   Context: ...{lesson1_content[pos-50:pos+100]}...")

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from: {pdf_path}\n")
    text = extract_text_from_pdf(pdf_path)
    
    debug_lesson_boundaries(text)

if __name__ == "__main__":
    main()
