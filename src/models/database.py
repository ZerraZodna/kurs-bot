from contextlib import contextmanager
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from .base import Base, engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session(session: Session | None = None):
    """Context manager for DB sessions. Uses provided session or creates/closes new one."""
    if session is not None:
        yield session
    else:
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()


def init_db():
    """Initialize database schema.
    
    Idempotent - safe to call multiple times.
    Creates all tables if they don't exist.
    """
    # Check if tables already exist
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            # Tables already exist - nothing to do
            return
    except Exception:
        # If inspection fails (e.g., connection error), just try to create tables
        pass
    
    # Create all tables
    Base.metadata.create_all(bind=engine)


# Re-export all models from individual modules for backward compatibility
from .consent import ConsentLog, Unsubscribe
from .gdpr import GdprAuditLog, GdprRequest, GdprVerification
from .jobs import BatchLock, JobState
from .memory import Memory
from .messages import MessageLog
from .schedule import Lesson, Schedule
from .templates import PromptTemplate
from .user import User

# TriggerEmbedding removed in Phase 3 - embedding-based trigger matching replaced by function calling


if __name__ == "__main__":
    init_db()
    print("Initialized DB at", engine.url)
