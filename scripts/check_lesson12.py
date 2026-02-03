"""
Debug Lesson 12 to see why it's cut off.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_lesson_12():
    """Check lesson 12 and surrounding lessons."""
    session = SessionLocal()
    try:
        lesson11 = session.query(Lesson).filter(Lesson.lesson_id == 11).first()
        lesson12 = session.query(Lesson).filter(Lesson.lesson_id == 12).first()
        lesson13 = session.query(Lesson).filter(Lesson.lesson_id == 13).first()
        
        print("LESSON 11")
        print("="*60)
        if lesson11:
            print(f"Title: {lesson11.title}")
            print(f"Content length: {len(lesson11.content)} chars")
            print(f"Last 200 chars:")
            print(repr(lesson11.content[-200:]))
        
        print("\n\nLESSON 12")
        print("="*60)
        if lesson12:
            print(f"Title: {lesson12.title}")
            print(f"Content length: {len(lesson12.content)} chars")
            print(f"\nFull content:")
            print(lesson12.content)
            print(f"\n\nLast 300 chars:")
            print(repr(lesson12.content[-300:]))
        
        print("\n\nLESSON 13")
        print("="*60)
        if lesson13:
            print(f"Title: {lesson13.title}")
            print(f"Content length: {len(lesson13.content)} chars")
            print(f"First 200 chars:")
            print(repr(lesson13.content[:200]))
        
    finally:
        session.close()

if __name__ == "__main__":
    check_lesson_12()
