"""
Analyze the duplicate lesson headers and page layout.
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

def analyze_duplicates(text: str) -> None:
    """Analyze lesson header duplicates."""
    
    # Get all lesson 5 occurrences with positions
    lesson5_matches = list(re.finditer(r"lesson\s+5\n", text, re.IGNORECASE))
    
    print(f"Found {len(lesson5_matches)} occurrences of 'lesson 5':\n")
    
    for i, match in enumerate(lesson5_matches):
        pos = match.start()
        # Look at context around this position
        start = max(0, pos - 100)
        end = min(len(text), pos + 300)
        
        context = text[start:end]
        print(f"Occurrence {i+1} at position {pos}:")
        print(f"Context: {repr(context)}")
        print()
    
    # Now analyze what's between the two lesson 5 markers
    if len(lesson5_matches) >= 2:
        between_start = lesson5_matches[0].end()
        between_end = lesson5_matches[1].start()
        between_text = text[between_start:between_end]
        
        print("\n" + "="*60)
        print("TEXT BETWEEN FIRST AND SECOND LESSON 5")
        print("="*60)
        print(f"Length: {len(between_text)} chars")
        print(f"Content:\n{repr(between_text[:500])}...")
        
        # Check if this text contains important content or just page markers
        has_content = len(between_text.strip()) > 100
        print(f"Has substantial content: {has_content}")

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...\n")
    text = extract_text_from_pdf(pdf_path)
    
    analyze_duplicates(text)

if __name__ == "__main__":
    main()
