from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base
import datetime


class Lesson(Base):
    __tablename__ = 'lessons'

    lesson_id = Column(Integer, primary_key=True)
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    difficulty_level = Column(String(32))
    duration_minutes = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Relationships
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

    # Relationships
    user = relationship('User', back_populates='schedules')
    lesson = relationship('Lesson', back_populates='schedules')
