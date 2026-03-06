"""Helper to ensure bundled ACIM lessons are available in the database.

Provides a single entrypoint so import logic isn't duplicated across
dialogue handlers and scheduler codepaths.
"""
import logging

logger = logging.getLogger(__name__)


def ensure_lessons_available(session) -> bool:
    """Ensure lessons exist in the DB; import from bundled script if empty.

    Returns True when lessons are available after this call (either were
    already present or were successfully imported). Returns False on error
    or if lessons could not be imported.
    """
    try:
        from src.models.database import Lesson

        count = session.query(Lesson).count()
        if count and count > 0:
            return True

        # Use the refactored import from src.lessons
        from src.lessons import main as import_main
        
        try:
            rc = import_main([])
            if rc == 0:
                # re-query to confirm import
                return bool(session.query(Lesson).count())
            logger.warning("Lesson import returned code %s", rc)
            return False
        except Exception as e:
            logger.exception("Failed to run lesson import: %s", e)
            return False

    except Exception as e:
        logger.exception("Failed to ensure lessons available: %s", e)
        return False
