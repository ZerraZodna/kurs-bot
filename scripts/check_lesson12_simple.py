"""
Check Lesson 12 - simplified.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_lesson_12_simple():
    """Check lesson 12."""
    session = SessionLocal()
    try:
        lesson12 = session.query(Lesson).filter(Lesson.lesson_id == 12).first()
        
        if lesson12:
            print("LESSON 12")
            print("="*60)
            print(f"Title length: {len(lesson12.title)}")
            print(f"Content length: {len(lesson12.content)} chars")
            
            # Check for the duplicate phrase
            count = lesson12.content.count("a meaningless world upset you")
            print(f"\nOccurrences of 'a meaningless world upset you': {count}")
            
            if count > 1:
                print(f"[ERROR] Content has {count} occurrences (should be 1 or 2 max)")
                # Show where they are
                idx1 = lesson12.content.find("a meaningless world upset you")
                if idx1 != -1:
                    idx2 = lesson12.content.find("a meaningless world upset you", idx1 + 1)
                    print(f"  First occurrence at position: {idx1}")
                    if idx2 != -1:
                        print(f"  Second occurrence at position: {idx2}")
            else:
                print(f"[OK] Content appears correctly")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_lesson_12_simple()
