"""Database writer for lessons.

Handles importing parsed lessons into the database.
"""
from __future__ import annotations

import datetime
import logging
from typing import List, Optional

from src.models.database import SessionLocal, Lesson


logger = logging.getLogger(__name__)


class LessonWriter:
    """Writes parsed lessons to the database."""
    
    def __init__(self, clear_existing: bool = False):
        """Initialize writer.
        
        Args:
            clear_existing: If True, delete existing lessons before import.
        """
        self.clear_existing = clear_existing
    
    def write(self, lessons: List[tuple[int, str, str]]) -> int:
        """Write lessons to database.
        
        Args:
            lessons: List of (lesson_id, title, content) tuples.
            
        Returns:
            Number of lessons successfully imported.
        """
        added = 0
        
        with SessionLocal() as session:
            if self.clear_existing:
                deleted = session.query(Lesson).delete()
                session.commit()
                logger.info(f"Deleted {deleted} existing lessons")
            
            for lesson_id, title, content in lessons:
                # Check if already exists
                existing = session.query(Lesson).filter(
                    Lesson.lesson_id == lesson_id
                ).first()
                
                if existing:
                    logger.debug(f"Lesson {lesson_id} already exists, skipping")
                    continue
                
                # Create new lesson
                lesson = Lesson(
                    lesson_id=lesson_id,
                    title=(title or '')[:128],
                    content=content,
                    difficulty_level='beginner',
                    duration_minutes=15,
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                )
                
                session.add(lesson)
                
                try:
                    session.flush()
                    added += 1
                    
                    # Commit in batches for performance
                    if added % 50 == 0:
                        session.commit()
                        logger.info(f"Imported {added} lessons...")
                        
                except Exception as e:
                    session.rollback()
                    logger.warning(f"Failed to import lesson {lesson_id}: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Total imported: {added} lessons")
        return added
    
    def verify(self, expected_count: int) -> bool:
        """Verify the database contains expected number of lessons.
        
        Args:
            expected_count: Expected number of lessons.
            
        Returns:
            True if verification passes.
        """
        with SessionLocal() as session:
            count = session.query(Lesson).count()
            logger.info(f"Database contains {count} lessons (expected {expected_count})")
            return count >= expected_count


def import_to_db(
    lessons: List[tuple[int, str, str]],
    clear: bool = False,
    verify: bool = True,
    limit: Optional[int] = None,
) -> int:
    """Convenience function to import lessons to database.
    
    Args:
        lessons: List of (lesson_id, title, content) tuples.
        clear: If True, delete existing lessons first.
        verify: If True, verify count after import.
        limit: Optional limit on number of lessons to import.
        
    Returns:
        Number of lessons imported.
    """
    if limit is not None:
        lessons = lessons[:limit]
    
    writer = LessonWriter(clear_existing=clear)
    added = writer.write(lessons)
    
    if verify:
        expected = len(lessons)
        if not writer.verify(expected):
            logger.warning(f"Verification failed: expected {expected}, check database")
    
    return added


def verify_db_count(expected: int) -> bool:
    """Verify database contains expected number of lessons.
    
    Args:
        expected: Expected lesson count.
        
    Returns:
        True if count matches.
    """
    writer = LessonWriter()
    return writer.verify(expected)

