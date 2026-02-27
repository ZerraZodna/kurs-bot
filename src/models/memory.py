from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base
import datetime


class Memory(Base):
    __tablename__ = 'memories'

    memory_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    category = Column(String(64), nullable=False)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)  # JSON-friendly
    value_hash = Column(String(64))
    conflict_group_id = Column(String(64))
    source = Column(String(64), default="dialogue_engine")
    confidence = Column(Float, default=1.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    ttl_expires_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship('User', back_populates='memories')
