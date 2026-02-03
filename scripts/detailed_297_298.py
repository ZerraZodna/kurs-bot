#!/usr/bin/env python
"""Detailed analysis of lesson 297-298 boundary."""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pypdf import PdfReader

pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
reader = PdfReader(pdf_path)

# Extract all text
all_text = ""
for page_num, page in enumerate(reader.pages):
    all_text += f"\n[=== PAGE {page_num} ===]\n"
    all_text += page.extract_text() + "\n"

# Get first occurrence of each
pattern_297 = r"lesson\s+297\n"
pattern_298 = r"lesson\s+298\n"

match_297 = re.search(pattern_297, all_text, re.MULTILINE | re.IGNORECASE)
match_298 = re.search(pattern_298, all_text, re.MULTILINE | re.IGNORECASE)

if match_297 and match_298:
    pos_297 = match_297.start()
    end_297 = match_297.end()
    pos_298 = match_298.start()
    end_298 = match_298.end()
    
    print("=" * 80)
    print("LESSON 297 AND 298 IN PDF")
    print("=" * 80)
    
    # Show the section from lesson 297 to after lesson 298 title
    section_start = pos_297
    section_end = end_298 + 1500
    section = all_text[section_start:section_end]
    
    print("\nFull text from 'lesson 297' onwards (1600 chars):")
    print(repr(section))
    
    print("\n\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    print(f"\nPosition of 'lesson 297': {pos_297}")
    print(f"Position of 'lesson 298': {pos_298}")
    print(f"Distance: {pos_298 - end_297} characters between title and next lesson")
    
    # What's between them?
    between = all_text[end_297:pos_298]
    print(f"\nBETWEEN 'lesson 297\\n' and 'lesson 298\\n':")
    print(f"  Length: {len(between)} chars")
    print(f"  Content: {repr(between)}")
    
    # The issue: lesson 297 content should go between the two headers
    # But there might be page break or formatting issues
    
    print(f"\n\nThe EXPECTED structure is:")
    print(f"  1. 'lesson 297' header")
    print(f"  2. Title: \"Forgiveness is the only gift I give.\"")
    print(f"  3. Full lesson 297 content")
    print(f"  4. 'lesson 298' header")
    print(f"  5. Title: \"I love You, Father...\"")
    print(f"  6. Full lesson 298 content")
    
    print(f"\nBut the ACTUAL structure appears to be:")
    print(f"  All of lesson 297 content between the two headers")
    
    # Extract what SHOULD be lesson 297
    lesson_297_title_start = end_297
    lesson_297_title_end = all_text.find('\n', lesson_297_title_start)
    lesson_297_title = all_text[lesson_297_title_start:lesson_297_title_end]
    
    lesson_297_content_start = lesson_297_title_end + 1
    lesson_297_content_end = pos_298
    lesson_297_content = all_text[lesson_297_content_start:lesson_297_content_end]
    
    print(f"\n\nEXTRACTED LESSON 297:")
    print(f"  Title: {repr(lesson_297_title)}")
    print(f"  Content ({len(lesson_297_content)} chars):")
    print(f"  {repr(lesson_297_content[:800])}")
