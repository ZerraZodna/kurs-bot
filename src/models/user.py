from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base
import datetime


class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    external_id = Column(String(128), nullable=False)
    channel = Column(String(32), nullable=False)
    phone_number = Column(String(32))
    email = Column(String(128))
    timezone = Column(String(64), nullable=True, default="Europe/Oslo")
    lesson = Column(Integer, nullable=True)
    first_name = Column(String(64))
    last_name = Column(String(64))
    opted_in = Column(Boolean, default=True, nullable=False)
    processing_restricted = Column(Boolean, default=False, nullable=False)
    restriction_reason = Column(Text)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime(timezone=True))

    # Relationships
    memories = relationship('Memory', back_populates='user')
    schedules = relationship('Schedule', back_populates='user')
    message_logs = relationship('MessageLog', back_populates='user')
    unsubscribes = relationship('Unsubscribe', back_populates='user')
    consent_logs = relationship('ConsentLog', back_populates='user')
    gdpr_requests = relationship('GdprRequest', back_populates='user')
    gdpr_audit_logs = relationship('GdprAuditLog', back_populates='user')
    gdpr_verifications = relationship('GdprVerification', back_populates='user')
