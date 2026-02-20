"""Helper to ensure bundled ACIM lessons are available in the database.

Provides a single entrypoint so import logic isn't duplicated across
dialogue handlers and scheduler codepaths.
"""
from pathlib import Path
import importlib.util
import logging
from typing import Optional

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

        # Attempt to find and run the bundled import script
        repo_root = Path(__file__).resolve().parents[3]
        script_path = repo_root / 'scripts' / 'utils' / 'import_acim_lessons.py'
        if not script_path.exists():
            logger.warning("import_acim_lessons.py not found at %s", script_path)
            return False

        try:
            spec = importlib.util.spec_from_file_location("import_acim_lessons", str(script_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rc = mod.main([])
            if rc == 0:
                # re-query to confirm import
                return bool(session.query(Lesson).count())
            logger.warning("import_acim_lessons returned code %s", rc)
            return False
        except Exception as e:
            logger.exception("Failed to run import_acim_lessons: %s", e)
            return False

    except Exception as e:
        logger.exception("Failed to ensure lessons available: %s", e)
        return False
