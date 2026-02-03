#!/usr/bin/env python
"""Debug script to check lessons 297 and 298 in raw PDF text."""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pypdf import PdfReader

pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
reader = PdfReader(pdf_path)

# Extract all text with page markers
all_text = ""
for page_num, page in enumerate(reader.pages):
    all_text += f"\n[=== PAGE {page_num} ===]\n"
    all_text += page.extract_text() + "\n"

# Find lessons 297 and 298
print("=" * 80)
print("SEARCHING FOR LESSONS 297 AND 298")
print("=" * 80)

for lesson_num in [297, 298]:
    pattern = rf"lesson\s+{lesson_num}\n"
    matches = list(re.finditer(pattern, all_text, re.MULTILINE | re.IGNORECASE))
    print(f"\n\nFound {len(matches)} occurrence(s) of 'lesson {lesson_num}':")
    
    for i, match in enumerate(matches):
        start_pos = match.start()
        match_end = match.end()
        
        # Show 50 chars before, then 400 chars after
        before_start = max(0, start_pos - 150)
        after_end = min(len(all_text), match_end + 600)
        
        print(f"\n  --- Occurrence {i+1} ---")
        print(f"  Position: {start_pos}")
        context_before = all_text[before_start:start_pos]
        match_text = all_text[start_pos:match_end]
        context_after = all_text[match_end:after_end]
        
        print(f"\n  BEFORE:\n  {repr(context_before[-100:])}")
        print(f"\n  MATCH:\n  {repr(match_text)}")
        after_display = context_after.replace('\n', '\\n')
        print(f"\n  AFTER:\n  {after_display}")

# Now find where lesson 298 starts and where the body content is
print("\n\n" + "=" * 80)
print("DETAILED ANALYSIS: LESSON 297-298 BOUNDARY")
print("=" * 80)

# Find the last occurrence of "lesson 297"
lesson_297_pattern = r"lesson\s+297\n"
lesson_297_matches = list(re.finditer(lesson_297_pattern, all_text, re.MULTILINE | re.IGNORECASE))

# Find the first occurrence of "lesson 298"
lesson_298_pattern = r"lesson\s+298\n"
lesson_298_matches = list(re.finditer(lesson_298_pattern, all_text, re.MULTILINE | re.IGNORECASE))

if lesson_297_matches and lesson_298_matches:
    # Use FIRST 297 and FIRST 298 to see actual order
    lesson_297_match = lesson_297_matches[0]
    lesson_298_match = lesson_298_matches[0]
    
    print(f"\nFIRST 'lesson 297' found at position: {lesson_297_match.start()}")
    print(f"FIRST 'lesson 298' found at position: {lesson_298_match.start()}")
    print(f"Order in PDF: lesson {298 if lesson_298_match.start() < lesson_297_match.start() else 297} comes first")
    
    # If 298 comes before 297, show the overlap situation
    if lesson_298_match.start() < lesson_297_match.start():
        # 298 comes first, then 297
        # Show content from 298 to 297
        between_start = lesson_298_match.end()
        between_end = lesson_297_match.start()
        between = all_text[between_start:between_end]
        
        print(f"\nTEXT FROM lesson 298 TO lesson 297 (total {len(between)} chars):")
        between_display = between.replace('\n', '\\n')
        print(between_display[:800])
        
        # Now show the actual lesson boundaries
        print(f"\n\n=== LESSON 298 CONTENT ===")
        lesson_298_content_start = lesson_298_match.end()
        lesson_298_content_end = lesson_297_match.start()
        lesson_298_content = all_text[lesson_298_content_start:lesson_298_content_end]
        print(f"Length: {len(lesson_298_content)}")
        print(f"First 600 chars:\n{lesson_298_content[:600]}")
        
        print(f"\n\n=== LESSON 297 CONTENT ===")
        lesson_297_content_start = lesson_297_match.end()
        lesson_297_content_end = lesson_297_match.end() + 1200  # Look ahead
        lesson_297_content = all_text[lesson_297_content_start:lesson_297_content_end]
        print(f"First 1000 chars:\n{lesson_297_content[:1000]}")
