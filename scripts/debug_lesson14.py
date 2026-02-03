"""
Debug Lesson 14 to see what's happening with the content.
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

def debug_lesson_14(text: str) -> None:
    """Debug lesson 14 extraction."""
    
    # Find all lesson 14 occurrences
    lesson14_matches = list(re.finditer(r"lesson\s+14\n", text, re.IGNORECASE | re.MULTILINE))
    
    print(f"Found {len(lesson14_matches)} occurrences of 'lesson 14':\n")
    
    for i, match in enumerate(lesson14_matches):
        pos = match.start()
        # Show context
        start = max(0, pos - 50)
        end = min(len(text), pos + 200)
        
        print(f"Occurrence {i+1} at position {pos}:")
        print(f"  {repr(text[start:end])}")
        print()
    
    # Extract lesson 14 content like the import script does
    if len(lesson14_matches) > 0:
        match = lesson14_matches[-1]  # Use last occurrence
        
        # Title
        title_start = match.end()
        title_end = text.find('\n', title_start)
        if title_end == -1:
            title_end = len(text)
        title = text[title_start:title_end].strip()
        
        print("="*60)
        print("LESSON 14 EXTRACTION")
        print("="*60)
        print(f"Title: {title}\n")
        
        # Find content start (after title line)
        content_start = title_end + 1 if title_end < len(text) else len(text)
        
        # Find next lesson (15)
        lesson15_matches = list(re.finditer(r"lesson\s+15\n", text, re.IGNORECASE | re.MULTILINE))
        if lesson15_matches:
            first_lesson15 = lesson15_matches[0]
            content_end = first_lesson15.start()
        else:
            content_end = len(text)
        
        content = text[content_start:content_end].strip()
        
        print(f"Content length: {len(content)} chars")
        print(f"\nLast 500 chars of content:")
        print(repr(content[-500:]))
        
        # Check for page artifacts
        print(f"\n\nLooking for page artifacts:")
        if "WORKBOOK" in content:
            print("  Found: 'WORKBOOK'")
            pos = content.find("WORKBOOK")
            print(f"    Context: {repr(content[pos-50:pos+100])}")
        
        if re.search(r'\b\d{1,3}\b', content[-100:]):
            print("  Found: Numbers that might be page numbers near the end")
            print(f"    Last 100 chars: {repr(content[-100:])}")

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...\n")
    text = extract_text_from_pdf(pdf_path)
    
    debug_lesson_14(text)

if __name__ == "__main__":
    main()
