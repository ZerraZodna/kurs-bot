"""
Check the full content of the first few lessons in the database.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_database_full():
    """Check the full content of lessons."""
    session = SessionLocal()
    try:
        # Get first 5 lessons
        lessons = session.query(Lesson).order_by(Lesson.lesson_id).limit(5).all()
        
        for lesson in lessons:
            print(f"\n{'='*60}")
            print(f"LESSON {lesson.lesson_id}")
            print(f"{'='*60}")
            print(f"Title: {lesson.title}")
            print(f"\nContent ({len(lesson.content)} chars):")
            print(f"{lesson.content}")
            print(f"\nLast 200 chars: ...{lesson.content[-200:]}")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_database_full()
