from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base
from src.core.clock import utc_now


class GdprRequest(Base):
    __tablename__ = 'gdpr_requests'

    request_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    request_type = Column(String(32), nullable=False)
    status = Column(String(32), default="completed", nullable=False)
    reason = Column(Text)
    details = Column(Text)
    actor = Column(String(64), default="user", nullable=False)
    requested_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship('User', back_populates='gdpr_requests')


class GdprAuditLog(Base):
    __tablename__ = 'gdpr_audit_logs'

    audit_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    action = Column(String(64), nullable=False)
    details = Column(Text)
    actor = Column(String(64), default="system", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user = relationship('User', back_populates='gdpr_audit_logs')


class GdprVerification(Base):
    __tablename__ = 'gdpr_verifications'

    verification_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    channel = Column(String(32), nullable=False)
    request_type = Column(String(32), nullable=False)
    request_payload = Column(Text)
    code_hash = Column(String(64), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user = relationship('User', back_populates='gdpr_verifications')
