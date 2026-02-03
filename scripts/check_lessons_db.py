"""
Check what's currently in the lessons table in the database.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_database():
    """Check the lessons table."""
    session = SessionLocal()
    try:
        count = session.query(Lesson).count()
        print(f"📊 Total lessons in database: {count}\n")
        
        if count == 0:
            print("❌ No lessons found in database!")
            return
        
        # Get all lessons sorted by lesson_id
        lessons = session.query(Lesson).order_by(Lesson.lesson_id).all()
        
        print(f"Sample lessons:")
        for lesson in lessons[:5]:
            print(f"\n  Lesson {lesson.lesson_id}:")
            print(f"    Title: {lesson.title}")
            print(f"    Content: {lesson.content[:100]}...")
            print(f"    Duration: {lesson.duration_minutes} min")
        
        # Check for gaps
        lesson_ids = [l.lesson_id for l in lessons]
        expected_ids = set(range(1, 366))
        actual_ids = set(lesson_ids)
        
        missing = expected_ids - actual_ids
        if missing:
            print(f"\n⚠️  Missing {len(missing)} lessons:")
            print(f"   Missing IDs: {sorted(missing)}")
        else:
            print(f"\n✅ All 365 lessons are present!")
        
        # Show last few lessons
        print(f"\nLast 5 lessons:")
        for lesson in lessons[-5:]:
            print(f"\n  Lesson {lesson.lesson_id}:")
            print(f"    Title: {lesson.title}")
            print(f"    Content: {lesson.content[:100]}...")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_database()
