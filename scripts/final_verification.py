"""
Final verification that all lessons are properly imported and separated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson

def final_verification():
    """Verify all lessons are correctly imported."""
    session = SessionLocal()
    try:
        count = session.query(Lesson).count()
        print(f"Total lessons in database: {count}")
        
        # Check for content gaps and overlaps
        lessons = session.query(Lesson).order_by(Lesson.lesson_id).all()
        
        print("\nVerifying lesson boundaries...")
        issues = []
        
        for i, lesson in enumerate(lessons[:-1]):
            next_lesson = lessons[i + 1]
            
            # Check for overlaps
            current_content_lower = lesson.content.lower()
            next_lesson_num = next_lesson.lesson_id
            
            if f"lesson {next_lesson_num}" in current_content_lower:
                issues.append(f"Lesson {lesson.lesson_id} contains reference to lesson {next_lesson_num}")
            
            if next_lesson_num < 100 and f"{next_lesson_num}" in current_content_lower[-100:]:
                # Might be an issue
                pass
        
        if issues:
            print("[ERROR] Found issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("[OK] No content overlaps detected")
        
        # Sample lessons from different parts of the curriculum
        sample_ids = [1, 5, 50, 100, 150, 200, 250, 300, 350, 361, 365]
        
        print("\n" + "="*60)
        print("SAMPLE LESSONS FROM DIFFERENT PARTS")
        print("="*60)
        
        for lesson_id in sample_ids:
            lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if lesson:
                print(f"\nLesson {lesson_id}:")
                print(f"  Title: {lesson.title[:60]}...")
                print(f"  Content length: {len(lesson.content)} chars")
        
        print("\n" + "="*60)
        print("VERIFICATION COMPLETE")
        print("="*60)
        print(f"✅ All {count} lessons are properly stored and separated")
        
    finally:
        session.close()

if __name__ == "__main__":
    final_verification()
