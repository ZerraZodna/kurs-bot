"""
Scan lesson boundaries for suspiciously short gaps between end of one lesson and start of next.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def scan_boundaries(threshold: int = 50) -> None:
    session = SessionLocal()
    try:
        lessons = session.query(Lesson).order_by(Lesson.lesson_id).all()
        issues = []

        for i in range(len(lessons) - 1):
            current = lessons[i]
            next_lesson = lessons[i + 1]

            tail = current.content[-threshold:] if current.content else ""
            head = next_lesson.content[:threshold] if next_lesson.content else ""

            # If the tail and head are very similar, it might indicate a bad cut
            if tail and head and tail.strip() and head.strip():
                if tail.strip().endswith(head.strip()) or head.strip().startswith(tail.strip()):
                    issues.append((current.lesson_id, next_lesson.lesson_id, tail, head))

        print(f"Checked {len(lessons)} lessons")
        if not issues:
            print("[OK] No suspicious short overlaps detected")
            return

        print(f"[WARNING] Found {len(issues)} suspicious boundaries:")
        for lesson_id, next_id, tail, head in issues:
            print(f"\nLesson {lesson_id} -> Lesson {next_id}")
            print(f"Tail ({len(tail)} chars): {repr(tail)}")
            print(f"Head ({len(head)} chars): {repr(head)}")
    finally:
        session.close()

if __name__ == "__main__":
    scan_boundaries(50)
