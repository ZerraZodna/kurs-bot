from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.core.timezone import utc_now
from src.models.base import Base


class Unsubscribe(Base):
    __tablename__ = "unsubscribes"

    unsubscribe_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    channel = Column(String(32), nullable=False)
    reason = Column(Text)
    unsubscribed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    compliance_required = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="unsubscribes")


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    consent_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    scope = Column(String(64), nullable=False)
    granted = Column(Boolean, nullable=False)
    consent_version = Column(String(32))
    source = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="consent_logs")
