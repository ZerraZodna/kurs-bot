from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.core.clock import utc_now
from src.models.base import Base


class Memory(Base):
    __tablename__ = "memories"

    memory_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category = Column(String(64), nullable=False)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)  # JSON-friendly
    value_hash = Column(String(64))
    conflict_group_id = Column(String(64))
    source = Column(String(64), default="dialogue_engine")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    ttl_expires_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="memories")
