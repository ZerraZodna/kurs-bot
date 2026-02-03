"""
Check Lesson 5 to verify it's now complete.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_lesson_5():
    """Check lesson 5 content."""
    session = SessionLocal()
    try:
        lesson5 = session.query(Lesson).filter(Lesson.lesson_id == 5).first()
        lesson6 = session.query(Lesson).filter(Lesson.lesson_id == 6).first()
        
        if lesson5:
            print("LESSON 5")
            print("="*60)
            print(f"Title: {lesson5.title}")
            print(f"Content length: {len(lesson5.content)} chars")
            print(f"\nFull content:")
            print(lesson5.content)
            print(f"\nLast 200 chars:")
            print(repr(lesson5.content[-200:]))
        
        if lesson6:
            print("\n\nLESSON 6")
            print("="*60)
            print(f"Title: {lesson6.title}")
            print(f"Content length: {len(lesson6.content)} chars")
            print(f"\nFirst 200 chars:")
            print(repr(lesson6.content[:200]))
        
        # Check for overlap
        if lesson5 and lesson6:
            if "lesson 6" in lesson5.content.lower():
                print("\n[ERROR] Lesson 5 contains 'lesson 6'")
            else:
                print("\n[OK] Lesson 5 does NOT contain 'lesson 6'")
                
    finally:
        session.close()

if __name__ == "__main__":
    check_lesson_5()
