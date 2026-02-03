"""
Check what's on page 24 after the page break and before lesson 15.
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

def check_lesson14_continuation(text: str) -> None:
    """Check what's in the WORKBOOK line that follows lesson 14."""
    
    # Find "WORKBOOK \n24" in lesson 14
    workbook_pattern = r'WORKBOOK\s+\n\d+'
    matches = list(re.finditer(workbook_pattern, text))
    
    print(f"Found {len(matches)} 'WORKBOOK' page breaks\n")
    
    # Find the one after lesson 14
    lesson14_pos = text.find("lesson 14\n")
    lesson15_pos = text.find("lesson 15\n")
    
    if lesson14_pos == -1 or lesson15_pos == -1:
        print("Could not find both lessons")
        return
    
    print(f"Lesson 14 at position: {lesson14_pos}")
    print(f"Lesson 15 at position: {lesson15_pos}")
    print(f"Distance: {lesson15_pos - lesson14_pos} chars\n")
    
    # Find WORKBOOK breaks between lesson 14 and 15
    between_text = text[lesson14_pos:lesson15_pos]
    workbook_matches = list(re.finditer(workbook_pattern, between_text))
    
    print(f"Found {len(workbook_matches)} WORKBOOK markers between lesson 14 and 15\n")
    
    for i, match in enumerate(workbook_matches):
        pos_in_between = match.start()
        actual_pos = lesson14_pos + pos_in_between
        
        # Show context around this marker
        start = max(0, actual_pos - 100)
        end = min(len(text), actual_pos + 200)
        
        print(f"WORKBOOK marker {i+1}:")
        print(f"  Position in text: {actual_pos}")
        print(f"  Context before:")
        print(f"    {repr(text[start:actual_pos])}")
        print(f"  Context after:")
        print(f"    {repr(text[actual_pos:end])}")
        print()

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from PDF...\n")
    text = extract_text_from_pdf(pdf_path)
    
    check_lesson14_continuation(text)

if __name__ == "__main__":
    main()
