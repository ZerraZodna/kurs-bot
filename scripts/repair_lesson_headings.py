import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Lesson


def looks_like_heading_text(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    words = s.split()
    if s.startswith(('“', '"', '*')) or s.endswith(('”', '"')):
        return True
    if len(words) > 8:
        return True
    return False


def main():
    session = SessionLocal()
    try:
        for lid in range(361, 366):
            lesson = session.query(Lesson).filter(Lesson.lesson_id == lid).first()
            if not lesson:
                print(f"Lesson {lid} not found")
                continue

            if looks_like_heading_text(lesson.title):
                print(f"Repairing Lesson {lid}: moving title into content")
                new_content = (lesson.title + '\n' + lesson.content) if lesson.content else lesson.title
                lesson.content = new_content
                lesson.title = f"Lesson {lid}"
                session.add(lesson)
        session.commit()
        print("Repair completed and committed")
    except Exception as e:
        session.rollback()
        print("Error:", e)
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
