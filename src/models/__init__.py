# Re-export all models for backward compatibility
from .user import User
from .memory import Memory
from .schedule import Lesson, Schedule
from .messages import MessageLog
from .consent import Unsubscribe, ConsentLog
from .gdpr import GdprRequest, GdprAuditLog, GdprVerification
from .jobs import BatchLock, JobState
from .templates import PromptTemplate
# TriggerEmbedding removed in Phase 3 - embedding-based trigger matching replaced by function calling

__all__ = [
    'User', 'Memory', 'Lesson', 'Schedule', 'MessageLog',
    'Unsubscribe', 'ConsentLog', 'GdprRequest', 'GdprAuditLog', 'GdprVerification',
    'BatchLock', 'JobState', 'PromptTemplate'
]
