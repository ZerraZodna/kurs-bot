#!/usr/bin/env python
"""Verify lessons 297 and 298 in the database."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

session = SessionLocal()
lesson_297 = session.query(Lesson).filter(Lesson.lesson_id == 297).first()
lesson_298 = session.query(Lesson).filter(Lesson.lesson_id == 298).first()

print("=" * 80)
print("VERIFICATION: LESSON 297")
print("=" * 80)
if lesson_297:
    print(f"Title: {lesson_297.title}")
    print(f"Content length: {len(lesson_297.content)}")
    print(f"First 400 chars:\n{lesson_297.content[:400]}")
    print(f"\nLast 200 chars:\n{lesson_297.content[-200:]}")
    if len(lesson_297.content) > 100:
        print("\n✅ PASS: Has full content")
    else:
        print("\n❌ FAIL: Missing content")
else:
    print("❌ FAIL: Not found")

print("\n\n" + "=" * 80)
print("VERIFICATION: LESSON 298")
print("=" * 80)
if lesson_298:
    print(f"Title: {lesson_298.title}")
    print(f"Content length: {len(lesson_298.content)}")
    print(f"First 400 chars:\n{lesson_298.content[:400]}")
    print(f"\nLast 200 chars:\n{lesson_298.content[-200:]}")
    if len(lesson_298.content) > 100:
        print("\n✅ PASS: Has full content")
    else:
        print("\n❌ FAIL: Missing content")
else:
    print("❌ FAIL: Not found")

session.close()
