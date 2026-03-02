from sqlalchemy.orm import sessionmaker
from .base import Base, engine


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    Base.metadata.create_all(bind=engine)


# Re-export all models from individual modules for backward compatibility
from .user import User
from .memory import Memory
from .schedule import Lesson, Schedule
from .messages import MessageLog
from .consent import Unsubscribe, ConsentLog
from .gdpr import GdprRequest, GdprAuditLog, GdprVerification
from .jobs import BatchLock, JobState
from .templates import PromptTemplate
# TriggerEmbedding removed in Phase 3 - embedding-based trigger matching replaced by function calling


if __name__ == '__main__':
    init_db()
    print('Initialized DB at', engine.url)
