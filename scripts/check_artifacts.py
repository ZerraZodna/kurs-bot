"""
Verify multiple lessons to ensure no page artifacts remain.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def check_multiple_lessons():
    """Check several lessons for page artifacts."""
    session = SessionLocal()
    try:
        # Check lessons that likely span pages
        test_lessons = [1, 5, 10, 14, 20, 50, 100, 150, 200, 250, 300, 350, 360, 365]
        
        print("CHECKING LESSONS FOR PAGE ARTIFACTS")
        print("="*60)
        
        issues = []
        
        for lesson_id in test_lessons:
            lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            
            if not lesson:
                print(f"Lesson {lesson_id}: NOT FOUND")
                continue
            
            # Check for artifacts
            has_workbook = "WORKBOOK" in lesson.content
            has_part_i = "PART I" in lesson.content
            
            # Check for orphaned numbers that look like page numbers
            last_100 = lesson.content[-100:]
            has_page_num = any(last_100.endswith(str(i)) for i in range(1, 500))
            
            status = "OK"
            if has_workbook or has_part_i or has_page_num:
                status = "ERROR"
                issues.append(f"Lesson {lesson_id}")
                
            print(f"Lesson {lesson_id:3d}: {status:5s} | {len(lesson.content):4d} chars | {lesson.title[:40]}")
            
            if status == "ERROR":
                if has_workbook:
                    print(f"           -> Contains WORKBOOK")
                if has_part_i:
                    print(f"           -> Contains PART I")
                if has_page_num:
                    print(f"           -> Last 100 chars: {repr(last_100)}")
        
        print("\n" + "="*60)
        if issues:
            print(f"[ERROR] Found issues in {len(issues)} lessons: {issues}")
        else:
            print("[OK] All tested lessons are clean!")
        
    finally:
        session.close()

if __name__ == "__main__":
    check_multiple_lessons()
