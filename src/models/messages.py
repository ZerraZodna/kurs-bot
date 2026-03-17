from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.core.clock import utc_now
from src.models.base import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

    message_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    direction = Column(String(16), nullable=False)  # inbound|outbound
    channel = Column(String(32), nullable=False)
    external_message_id = Column(String(128))
    content = Column(Text)
    status = Column(String(16), nullable=False)  # queued|sent|delivered|failed
    error_message = Column(Text)
    conversation_thread_id = Column(String(64))  # For grouping related messages
    message_role = Column(String(16), default="user")  # user|assistant for LLM context
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="message_logs")
