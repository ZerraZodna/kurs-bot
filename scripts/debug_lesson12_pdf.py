"""
Debug Lesson 12 at the PDF text level.
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

def debug_lesson_12_pdf(text: str) -> None:
    """Debug lesson 12 at PDF text level."""
    
    # Find all lesson 12 occurrences
    lesson12_matches = list(re.finditer(r"lesson\s+12\n", text, re.IGNORECASE | re.MULTILINE))
    
    print(f"Found {len(lesson12_matches)} occurrences of 'lesson 12':\n")
    
    for i, match in enumerate(lesson12_matches):
        pos = match.start()
        start = max(0, pos - 50)
        end = min(len(text), pos + 150)
        
        print(f"Occurrence {i+1} at position {pos}:")
        print(f"  {repr(text[start:end])}")
    
    # Extract lesson 12 like the import script does
    if lesson12_matches:
        match = lesson12_matches[-1]  # Use last occurrence
        
        # Find lesson 13 boundary
        lesson13_matches = list(re.finditer(r"lesson\s+13\n", text, re.IGNORECASE | re.MULTILINE))
        if not lesson13_matches:
            print("\nLesson 13 not found!")
            return
        
        first_lesson13 = lesson13_matches[0]
        
        # Extract content
        title_start = match.end()
        title_end = text.find('\n', title_start)
        if title_end == -1:
            title_end = len(text)
        
        content_start = title_end + 1
        content_end = first_lesson13.start()
        
        raw_content = text[content_start:content_end]
        
        print(f"\n{'='*60}")
        print(f"RAW EXTRACTED CONTENT (before cleanup)")
        print(f"{'='*60}")
        print(f"Length: {len(raw_content)} chars")
        print(f"\nLooking for repetitions...")
        
        # Look for duplicate sections
        # Search for the section "a meaningless world upset you"
        pattern = r"a meaningless world upset you"
        matches = list(re.finditer(pattern, raw_content, re.IGNORECASE))
        
        print(f"\nFound {len(matches)} occurrences of 'a meaningless world upset you':")
        for i, m in enumerate(matches):
            pos = m.start()
            start = max(0, pos - 100)
            end = min(len(raw_content), pos + 150)
            print(f"\n  Occurrence {i+1} at position {pos}:")
            print(f"    {repr(raw_content[start:end])}")
        
        # Look for "That is the ultimate purpose"
        pattern2 = r"That is the ultimate purpose"
        matches2 = list(re.finditer(pattern2, raw_content, re.IGNORECASE))
        print(f"\n\nFound {len(matches2)} occurrences of 'That is the ultimate purpose':")
        for i, m in enumerate(matches2):
            pos = m.start()
            start = max(0, pos - 50)
            end = min(len(raw_content), pos + 200)
            print(f"\n  Occurrence {i+1} at position {pos}:")
            print(f"    {repr(raw_content[start:end])}")

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...\n")
    text = extract_text_from_pdf(pdf_path)
    
    debug_lesson_12_pdf(text)

if __name__ == "__main__":
    main()
