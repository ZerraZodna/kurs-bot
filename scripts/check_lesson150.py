"""
Debug Lesson 150 to see why it's so short.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_lesson_150():
    """Check lesson 150."""
    session = SessionLocal()
    try:
        lesson150 = session.query(Lesson).filter(Lesson.lesson_id == 150).first()
        lesson149 = session.query(Lesson).filter(Lesson.lesson_id == 149).first()
        lesson151 = session.query(Lesson).filter(Lesson.lesson_id == 151).first()
        
        print("LESSON 149")
        print("="*60)
        if lesson149:
            print(f"Title: {lesson149.title}")
            print(f"Content length: {len(lesson149.content)}")
            print(f"Last 150 chars:\n{repr(lesson149.content[-150:])}\n")
        
        print("LESSON 150")
        print("="*60)
        if lesson150:
            print(f"Title: {lesson150.title}")
            print(f"Content: {repr(lesson150.content)}")
            print(f"Length: {len(lesson150.content)}")
        
        print("\nLESSON 151")
        print("="*60)
        if lesson151:
            print(f"Title: {lesson151.title}")
            print(f"Content length: {len(lesson151.content)}")
            print(f"First 150 chars:\n{repr(lesson151.content[:150:])}\n")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_lesson_150()
