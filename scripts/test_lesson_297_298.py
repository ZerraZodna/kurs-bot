#!/usr/bin/env python
"""Test the fixed lesson parsing logic."""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pypdf import PdfReader
from scripts.import_acim_lessons import parse_lessons_from_text

pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
reader = PdfReader(pdf_path)

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"

# Parse lessons
lessons = parse_lessons_from_text(text)

# Find lessons 297 and 298
lesson_297 = None
lesson_298 = None

for lesson in lessons:
    if lesson['lesson_id'] == 297:
        lesson_297 = lesson
    elif lesson['lesson_id'] == 298:
        lesson_298 = lesson

print("=" * 80)
print("TEST: LESSON 297")
print("=" * 80)
if lesson_297:
    print(f"Title: {lesson_297['title']}")
    print(f"Content length: {len(lesson_297['content'])}")
    print(f"First 300 chars:\n{lesson_297['content'][:300]}")
    print(f"\nLast 200 chars:\n{lesson_297['content'][-200:]}")
    
    # Check if it has the full content (should be > 100 chars, not just the title)
    if len(lesson_297['content']) > 100:
        print("\n✅ PASS: Lesson 297 has full content")
    else:
        print("\n❌ FAIL: Lesson 297 is missing content")
else:
    print("❌ FAIL: Lesson 297 not found")

print("\n\n" + "=" * 80)
print("TEST: LESSON 298")
print("=" * 80)
if lesson_298:
    print(f"Title: {lesson_298['title']}")
    print(f"Content length: {len(lesson_298['content'])}")
    print(f"First 300 chars:\n{lesson_298['content'][:300]}")
    print(f"\nLast 200 chars:\n{lesson_298['content'][-200:]}")
    
    if len(lesson_298['content']) > 100:
        print("\n✅ PASS: Lesson 298 has full content")
    else:
        print("\n❌ FAIL: Lesson 298 is missing content")
else:
    print("❌ FAIL: Lesson 298 not found")

# Also check lessons around 297
print("\n\n" + "=" * 80)
print("CONTEXT: LESSONS AROUND 297")
print("=" * 80)
for lesson in lessons:
    if 295 <= lesson['lesson_id'] <= 300:
        content_length = len(lesson['content'])
        print(f"Lesson {lesson['lesson_id']}: {lesson['title'][:50]:<50} | {content_length:>5} chars")
