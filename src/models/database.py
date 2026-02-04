
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, func, LargeBinary, event
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import DateTime
import datetime

# Use Settings from config.py for database URL
from src.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=10, max_overflow=20,
    connect_args={"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

# SQLite connection pragmas
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    external_id = Column(String(128), nullable=False)
    channel = Column(String(32), nullable=False)
    phone_number = Column(String(32))
    email = Column(String(128))
    first_name = Column(String(64))
    last_name = Column(String(64))
    opted_in = Column(Boolean, default=True, nullable=False)
    processing_restricted = Column(Boolean, default=False, nullable=False)
    restriction_reason = Column(Text)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime(timezone=True))
    memories = relationship('Memory', back_populates='user')
    schedules = relationship('Schedule', back_populates='user')
    message_logs = relationship('MessageLog', back_populates='user')
    unsubscribes = relationship('Unsubscribe', back_populates='user')
    consent_logs = relationship('ConsentLog', back_populates='user')
    gdpr_requests = relationship('GdprRequest', back_populates='user')
    gdpr_audit_logs = relationship('GdprAuditLog', back_populates='user')

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
    # Embedding fields for semantic search
    embedding = Column(LargeBinary, nullable=True)  # Stores 384-dim vector as bytes
    embedding_version = Column(Integer, default=1)  # Track embedding model version
    embedding_generated_at = Column(DateTime(timezone=True), nullable=True)  # When embedding was generated
    user = relationship('User', back_populates='memories')

class Lesson(Base):
    __tablename__ = 'lessons'
    lesson_id = Column(Integer, primary_key=True)
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    difficulty_level = Column(String(32))
    duration_minutes = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    schedules = relationship('Schedule', back_populates='lesson')

class Schedule(Base):
    __tablename__ = 'schedules'
    schedule_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    lesson_id = Column(Integer, ForeignKey('lessons.lesson_id'))
    schedule_type = Column(String(32), nullable=False)  # one_time|daily|weekly|interval_reminder
    cron_expression = Column(String(64), nullable=False)
    next_send_time = Column(DateTime(timezone=True))
    last_sent_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    user = relationship('User', back_populates='schedules')
    lesson = relationship('Lesson', back_populates='schedules')

class MessageLog(Base):
    __tablename__ = 'message_logs'
    message_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    direction = Column(String(16), nullable=False)  # inbound|outbound
    channel = Column(String(32), nullable=False)
    external_message_id = Column(String(128))
    content = Column(Text)
    status = Column(String(16), nullable=False)  # queued|sent|delivered|failed
    error_message = Column(Text)
    conversation_thread_id = Column(String(64))  # For grouping related messages
    message_role = Column(String(16), default="user")  # user|assistant for LLM context
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    processed_at = Column(DateTime(timezone=True))
    user = relationship('User', back_populates='message_logs')

class Unsubscribe(Base):
    __tablename__ = 'unsubscribes'
    unsubscribe_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    channel = Column(String(32), nullable=False)
    reason = Column(Text)
    unsubscribed_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    compliance_required = Column(Boolean, default=False, nullable=False)
    user = relationship('User', back_populates='unsubscribes')


class ConsentLog(Base):
    __tablename__ = 'consent_logs'
    consent_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    scope = Column(String(64), nullable=False)
    granted = Column(Boolean, nullable=False)
    consent_version = Column(String(32))
    source = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    user = relationship('User', back_populates='consent_logs')


class GdprRequest(Base):
    __tablename__ = 'gdpr_requests'
    request_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    request_type = Column(String(32), nullable=False)
    status = Column(String(32), default="completed", nullable=False)
    reason = Column(Text)
    details = Column(Text)
    actor = Column(String(64), default="user", nullable=False)
    requested_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    processed_at = Column(DateTime(timezone=True))
    user = relationship('User', back_populates='gdpr_requests')


class GdprAuditLog(Base):
    __tablename__ = 'gdpr_audit_logs'
    audit_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    action = Column(String(64), nullable=False)
    details = Column(Text)
    actor = Column(String(64), default="system", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    user = relationship('User', back_populates='gdpr_audit_logs')

class BatchLock(Base):
    __tablename__ = 'batch_locks'
    lock_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    channel = Column(String(32), nullable=False)  # telegram, email, etc
    locked_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # When lock expires
    
def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    init_db()
    print('Initialized DB at', DATABASE_URL)
