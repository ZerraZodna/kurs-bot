"""
Check raw PDF text for lesson patterns.
"""

import os
import sys
from pathlib import Path
from pypdf import PdfReader

# Fix encoding for Windows
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from: {pdf_path}\n")
    
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Find "lesson 1" (case insensitive)
    import re
    
    # Search for different patterns
    patterns = [
        (r"lesson\s+1", "lesson 1 (basic)"),
        (r"Lesson\s+1", "Lesson 1 (capital L)"),
        (r"[Ll]esson\s+1", "lesson 1 (both cases)"),
        (r"[Ll]esson\s*1[:\s]", "lesson 1 with colon/space"),
        (r"^lesson\s+1", "lesson 1 at line start"),
        (r"lesson\s*1[\s:]", "lesson 1 flexible"),
    ]
    
    for pattern, desc in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
        if matches:
            print(f"[OK] Found {len(matches)} matches for '{desc}'")
            for i, match in enumerate(matches[:3]):
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 70)
                print(f"   Match {i+1} at position {match.start()}:")
                print(f"   ...{repr(text[start:end])}...")
        else:
            print(f"[NO] No matches for '{desc}'")
    
    # Try to find all "lesson" occurrences
    print(f"\n\nSearching for all 'lesson' patterns:")
    lesson_matches = list(re.finditer(r"[Ll]esson\s*\d+", text, re.MULTILINE))
    print(f"Found {len(lesson_matches)} lesson patterns")
    
    print(f"\nFirst 10 lesson patterns:")
    for match in lesson_matches[:10]:
        start = max(0, match.start() - 20)
        end = min(len(text), match.end() + 60)
        print(f"   {repr(text[start:end])}")
    
    print(f"\nLast 5 lesson patterns:")
    for match in lesson_matches[-5:]:
        start = max(0, match.start() - 20)
        end = min(len(text), match.end() + 60)
        print(f"   {repr(text[start:end])}")

if __name__ == "__main__":
    main()
