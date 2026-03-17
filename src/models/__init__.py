# Re-export all models for backward compatibility
from .consent import ConsentLog, Unsubscribe
from .gdpr import GdprAuditLog, GdprRequest, GdprVerification
from .jobs import BatchLock, JobState
from .memory import Memory
from .messages import MessageLog
from .schedule import Lesson, Schedule
from .templates import PromptTemplate
from .user import User

__all__ = [
    "User", "Memory", "Lesson", "Schedule", "MessageLog",
    "Unsubscribe", "ConsentLog", "GdprRequest", "GdprAuditLog", "GdprVerification",
    "BatchLock", "JobState", "PromptTemplate"
]
