"""Fluent data builders for tests.

Provides builder patterns for creating test data with clean, readable syntax.
"""

import datetime
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session

from src.models.database import Memory, Schedule, MessageLog, User, Lesson


class MemoryBuilder:
    """Fluent builder for creating test memories.
    
    Usage:
        memory = MemoryBuilder(db_session, user_id)
            .with_key("goal")
            .with_value("Learn Python")
            .with_category("fact")
            .build()
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._key = "test_key"
        self._value = "test_value"
        self._category = "fact"
        self._is_active = True
        self._archived_at: Optional[datetime.datetime] = None
        self._created_at: Optional[datetime.datetime] = None
        self._source = "test"
    
    def with_key(self, key: str) -> "MemoryBuilder":
        self._key = key
        return self
    
    def with_value(self, value: str) -> "MemoryBuilder":
        self._value = value
        return self
    
    def with_category(self, category: str) -> "MemoryBuilder":
        self._category = category
        return self
    
    def inactive(self) -> "MemoryBuilder":
        self._is_active = False
        return self
    
    def archived(self, archived_at: Optional[datetime.datetime] = None) -> "MemoryBuilder":
        self._is_active = False
        self._archived_at = archived_at or datetime.datetime.now(datetime.timezone.utc)
        return self
    
    def with_source(self, source: str) -> "MemoryBuilder":
        self._source = source
        return self
    
    def created_at(self, created_at: datetime.datetime) -> "MemoryBuilder":
        self._created_at = created_at
        return self
    
    def build(self) -> Memory:
        """Create and return the memory."""
        memory = Memory(
            user_id=self.user_id,
            key=self._key,
            value=self._value,
            category=self._category,
            is_active=self._is_active,
            archived_at=self._archived_at,
            created_at=self._created_at or datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            source=self._source,
        )
        self.db.add(memory)
        self.db.commit()
        return memory
    
    def build_many(self, count: int) -> List[Memory]:
        """Create multiple memories with the same settings."""
        memories = []
        for i in range(count):
            # Slightly modify key/value for each to avoid conflicts
            builder = MemoryBuilder(self.db, self.user_id)
            builder._key = f"{self._key}_{i}"
            builder._value = f"{self._value}_{i}"
            builder._category = self._category
            builder._is_active = self._is_active
            builder._archived_at = self._archived_at
            builder._source = self._source
            memories.append(builder.build())
        return memories


class ScheduleBuilder:
    """Fluent builder for creating test schedules.
    
    Usage:
        schedule = ScheduleBuilder(db_session, user_id)
            .daily()
            .at_time(9, 0)
            .active()
            .build()
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._schedule_type = "daily"
        self._cron_expression = "0 9 * * *"
        self._is_active = True
        self._lesson_id: Optional[int] = None
        self._next_send_time: Optional[datetime.datetime] = None
    
    def daily(self) -> "ScheduleBuilder":
        self._schedule_type = "daily"
        self._cron_expression = "0 9 * * *"
        return self
    
    def one_time(self) -> "ScheduleBuilder":
        self._schedule_type = "one_time"
        self._cron_expression = ""
        return self
    
    def at_time(self, hour: int, minute: int) -> "ScheduleBuilder":
        """Set cron expression for daily schedule."""
        self._cron_expression = f"0 {minute} {hour} * * *"
        return self
    
    def with_cron(self, cron: str) -> "ScheduleBuilder":
        self._cron_expression = cron
        return self
    
    def active(self) -> "ScheduleBuilder":
        self._is_active = True
        return self
    
    def inactive(self) -> "ScheduleBuilder":
        self._is_active = False
        return self
    
    def for_lesson(self, lesson_id: int) -> "ScheduleBuilder":
        self._lesson_id = lesson_id
        return self
    
    def send_now(self) -> "ScheduleBuilder":
        """Set next_send_time to now (for immediate execution)."""
        self._next_send_time = datetime.datetime.now(datetime.timezone.utc)
        return self
    
    def send_at(self, send_time: datetime.datetime) -> "ScheduleBuilder":
        self._next_send_time = send_time
        return self
    
    def build(self) -> Schedule:
        """Create and return the schedule."""
        schedule = Schedule(
            user_id=self.user_id,
            lesson_id=self._lesson_id,
            schedule_type=self._schedule_type,
            cron_expression=self._cron_expression,
            next_send_time=self._next_send_time or datetime.datetime.now(datetime.timezone.utc),
            is_active=self._is_active,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(schedule)
        self.db.commit()
        return schedule


class MessageBuilder:
    """Fluent builder for creating test message logs.
    
    Usage:
        message = MessageBuilder(db_session, user_id)
            .from_user("Hello bot")
            .build()
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._content = "Test message"
        self._direction = "inbound"
        self._channel: str = "telegram"
        self._external_message_id: Optional[str] = None
        self._status: str = "delivered"
    
    def from_user(self, content: str) -> "MessageBuilder":
        """Create an inbound message from user."""
        self._content = content
        self._direction = "inbound"
        return self
    
    def from_bot(self, content: str) -> "MessageBuilder":
        """Create an outbound message from bot."""
        self._content = content
        self._direction = "outbound"
        return self
    
    def via_channel(self, channel: str) -> "MessageBuilder":
        self._channel = channel
        return self
    
    def with_external_message_id(self, external_message_id: str) -> "MessageBuilder":
        self._external_message_id = external_message_id
        return self
    
    def with_status(self, status: str) -> "MessageBuilder":
        self._status = status
        return self
    
    def build(self) -> MessageLog:
        """Create and return the message log."""
        message = MessageLog(
            user_id=self.user_id,
            content=self._content,
            direction=self._direction,
            channel=self._channel,
            external_message_id=self._external_message_id,
            status=self._status,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(message)
        self.db.commit()
        return message
    
    def build_many(self, count: int, content_prefix: str = "Message") -> List[MessageLog]:
        """Create multiple messages."""
        messages = []
        for i in range(count):
            builder = MessageBuilder(self.db, self.user_id)
            builder._content = f"{content_prefix} {i+1}"
            builder._direction = self._direction
            builder._channel = self._channel
            messages.append(builder.build())
        return messages


class ConversationBuilder:
    """Builder for creating multi-turn conversations.
    
    Usage:
        conversation = ConversationBuilder(db_session, user_id)
            .user_says("Hi")
            .bot_responds("Hello!")
            .user_says("How are you?")
            .build()
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._messages: List[Dict[str, Any]] = []
    
    def user_says(self, content: str) -> "ConversationBuilder":
        self._messages.append({
            "direction": "inbound",
            "content": content,
        })
        return self
    
    def bot_responds(self, content: str) -> "ConversationBuilder":
        self._messages.append({
            "direction": "outbound",
            "content": content,
        })
        return self
    
    def build(self) -> List[MessageLog]:
        """Create all messages in the conversation."""
        messages = []
        for msg_data in self._messages:
            builder = MessageBuilder(self.db, self.user_id)
            if msg_data["direction"] == "inbound":
                builder.from_user(msg_data["content"])
            else:
                builder.from_bot(msg_data["content"])
            messages.append(builder.build())
        return messages


class LessonBuilder:
    """Fluent builder for creating test lessons.
    
    Usage:
        lesson = LessonBuilder(db_session)
            .with_id(1)
            .with_title("Lesson One")
            .with_content("Content here")
            .build()
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._lesson_id = 1
        self._title = "Test Lesson"
        self._content = "Test lesson content."
        self._created_at: Optional[datetime.datetime] = None
    
    def with_id(self, lesson_id: int) -> "LessonBuilder":
        self._lesson_id = lesson_id
        return self
    
    def with_title(self, title: str) -> "LessonBuilder":
        self._title = title
        return self
    
    def with_content(self, content: str) -> "LessonBuilder":
        self._content = content
        return self
    
    def build(self) -> Lesson:
        """Create and return the lesson."""
        lesson = Lesson(
            lesson_id=self._lesson_id,
            title=self._title,
            content=self._content,
            created_at=self._created_at or datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(lesson)
        self.db.commit()
        return lesson
    
    def build_many(self, count: int, start_id: int = 1) -> List[Lesson]:
        """Create multiple lessons."""
        lessons = []
        for i in range(count):
            builder = LessonBuilder(self.db)
            builder._lesson_id = start_id + i
            builder._title = f"{self._title} {i+1}"
            builder._content = f"{self._content} (Lesson {i+1})"
            lessons.append(builder.build())
        return lessons
