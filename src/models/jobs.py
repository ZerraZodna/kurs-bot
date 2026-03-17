from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from src.core.clock import utc_now
from src.models.base import Base


class BatchLock(Base):
    __tablename__ = "batch_locks"

    lock_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    channel = Column(String(32), nullable=False)  # telegram, email, etc
    locked_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # When lock expires


class JobState(Base):
    __tablename__ = "job_states"

    key = Column(String(64), primary_key=True)
    value = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
