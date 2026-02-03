"""
Verify Lesson 14 is now complete without page artifacts.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_lesson_14():
    """Check lesson 14 content."""
    session = SessionLocal()
    try:
        lesson14 = session.query(Lesson).filter(Lesson.lesson_id == 14).first()
        lesson15 = session.query(Lesson).filter(Lesson.lesson_id == 15).first()
        
        if lesson14:
            print("LESSON 14")
            print("="*60)
            print(f"Title: {lesson14.title}")
            print(f"Content length: {len(lesson14.content)} chars")
            print(f"\nLast 300 chars:")
            print(repr(lesson14.content[-300:]))
            
            # Check for page artifacts
            if "WORKBOOK" in lesson14.content:
                print("\n[ERROR] Contains 'WORKBOOK'")
            else:
                print("\n[OK] Does NOT contain 'WORKBOOK'")
            
            if " 24" in lesson14.content[-20:] or "\n24" in lesson14.content[-20:]:
                print("[WARNING] May contain page number at end")
            else:
                print("[OK] No page number at end")
        
        if lesson15:
            print("\n\nLESSON 15")
            print("="*60)
            print(f"Title: {lesson15.title}")
            print(f"Content length: {len(lesson15.content)} chars")
            print(f"First 200 chars:")
            print(repr(lesson15.content[:200]))
        
        # Check for overlap
        if lesson14 and lesson15:
            if "lesson 15" in lesson14.content.lower():
                print("\n[ERROR] Lesson 14 contains 'lesson 15'")
            else:
                print("\n[OK] Lesson 14 does NOT contain 'lesson 15'")
                
    finally:
        session.close()

if __name__ == "__main__":
    check_lesson_14()
