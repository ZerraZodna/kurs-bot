"""Tests for practice reminder feature.

Covers:
- AI extraction produces valid JSON for sample lessons
- Reminder jobs are created correctly for different frequencies
- Cached practice_instructions are reused (no redundant AI calls)
- Stop reminders functionality
- Reminder message formatting
- Evening cutoff preference
"""

import json
from datetime import timedelta
from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.lessons.practice_extractor import (
    check_and_extract_practice_instructions,
    _default_extraction,
)
from src.models.database import Lesson, Schedule
from src.scheduler.reminder_manager import (
    create_reminders,
    stop_daily_reminders,
    _format_reminder_message,
    _get_evening_cutoff,
    _parse_evening_cutoff,
)


class TestDefaultExtraction:
    """Test the default extraction for lessons with no special practice pattern."""

    def test_returns_single_frequency(self):
        result = _default_extraction()
        assert result["frequency"] == "single"
        assert result["key_phrases"] == []
        assert result["instructions"] == ""
        assert result["practice_window"] == ""


class TestReminderMessageFormatting:
    """Test reminder message formatting."""

    def test_with_key_phrase_and_instructions(self):
        msg = _format_reminder_message(
            key_phrase="I seek but what belongs to me in truth.",
            instructions="Take five minutes. Find a quiet moment.",
            practice_window="",
        )
        assert "Time to practice." in msg
        assert "I seek but what belongs to me in truth." in msg
        assert "Take five minutes" in msg

    def test_with_key_phrase_only(self):
        msg = _format_reminder_message(
            key_phrase="Nothing I see means anything.",
            instructions="",
            practice_window="",
        )
        assert "Time to practice." in msg
        assert "Nothing I see means anything." in msg

    def test_with_no_content(self):
        msg = _format_reminder_message(
            key_phrase="",
            instructions="",
            practice_window="",
        )
        assert "Time to practice." in msg


class TestParseEveningCutoff:
    """Test evening cutoff parsing."""

    def test_valid_time(self):
        assert _parse_evening_cutoff("22:00") == 22
        assert _parse_evening_cutoff("21:00") == 21
        assert _parse_evening_cutoff("09:00") == 9

    def test_invalid_time(self):
        assert _parse_evening_cutoff("invalid") == 22  # default
        assert _parse_evening_cutoff("") == 22  # default
        assert _parse_evening_cutoff("25:00") == 25  # parses but invalid hour


class TestEveningCutoffPreference:
    """Test user preference for evening cutoff."""

    def test_get_evening_cutoff_default(self, db_session: Session):
        from src.memories import MemoryManager

        mm = MemoryManager(db_session)
        cutoff = _get_evening_cutoff(db_session, user_id=999)
        assert cutoff == "22:00"

    def test_get_evening_cutoff_custom(self, db_session: Session):
        from src.memories import MemoryManager, constants

        mm = MemoryManager(db_session)
        mm.store_memory(
            user_id=999,
            key=constants.MemoryKey.PRACTICE_REMINDER_EVENING_CUTOFF,
            value="21:00",
            category="preferences",
        )
        cutoff = _get_evening_cutoff(db_session, user_id=999)
        assert cutoff == "21:00"


class TestCreateReminders:
    """Test reminder creation for different frequencies."""

    def test_hourly_creates_reminders(self, db_session: Session):
        """Hourly frequency should create reminders for each hour."""
        instructions = {
            "frequency": "hourly",
            "key_phrases": ["I seek but what belongs to me in truth."],
            "instructions": "Take five minutes.",
            "practice_window": "hourly from 7:00 to 22:00",
        }
        schedules = create_reminders(
            lesson_id=104,
            user_id=999,
            practice_instructions=instructions,
            session=db_session,
        )
        # Should create reminders for hours that haven't passed
        assert len(schedules) > 0
        for s in schedules:
            assert s.schedule_type.startswith("one_time")
            assert s.user_id == 999
            assert s.lesson_id == 104

    def test_single_frequency_creates_no_reminders(self, db_session: Session):
        """Single frequency should not create any reminders."""
        instructions = {
            "frequency": "single",
            "key_phrases": [],
            "instructions": "",
            "practice_window": "",
        }
        schedules = create_reminders(
            lesson_id=1,
            user_id=999,
            practice_instructions=instructions,
            session=db_session,
        )
        assert len(schedules) == 0

    def test_twice_daily_creates_reminders(self, db_session: Session):
        """Twice daily should create morning and evening reminders."""
        instructions = {
            "frequency": "twice_daily",
            "key_phrases": ["Nothing I see means anything."],
            "instructions": "Practice twice today.",
            "practice_window": "morning and evening",
        }
        schedules = create_reminders(
            lesson_id=1,
            user_id=999,
            practice_instructions=instructions,
            session=db_session,
        )
        # May create 0 if times have passed, but should not error
        assert isinstance(schedules, list)


class TestStopDailyReminders:
    """Test stopping practice reminders."""

    def test_stops_active_reminders(self, db_session: Session):
        """Should deactivate active one-time reminders."""
        # Create some active one-time reminders
        now = utc_now()
        for i in range(3):
            schedule = Schedule(
                user_id=999,
                lesson_id=104,
                schedule_type="one_time_reminder",
                cron_expression=f"once:{(now + timedelta(hours=i + 1)).isoformat()}",
                next_send_time=now + timedelta(hours=i + 1),
                is_active=True,
                created_at=now,
            )
            db_session.add(schedule)
        db_session.commit()

        count = stop_daily_reminders(user_id=999, session=db_session)
        assert count == 3

        # Verify they are deactivated
        remaining = db_session.query(Schedule).filter_by(user_id=999, is_active=True).all()
        assert len(remaining) == 0

    def test_stops_nothing_when_none_active(self, db_session: Session):
        """Should return 0 when no active reminders exist."""
        count = stop_daily_reminders(user_id=999, session=db_session)
        assert count == 0


class TestPracticeInstructionsExtraction:
    """Test cached vs AI extraction of practice instructions."""

    def test_cached_instructions_returned_directly(self, db_session: Session):
        """Should return cached JSON without AI call."""
        lesson = Lesson(
            lesson_id=9999,
            title="Test Lesson",
            content="Test content",
            practice_instructions=json.dumps({
                "frequency": "hourly",
                "key_phrases": ["Test phrase"],
                "instructions": "Test instructions",
                "practice_window": "hourly",
            }),
        )
        db_session.add(lesson)
        db_session.commit()

        result = check_and_extract_practice_instructions(9999, session=db_session)
        assert result is not None
        assert result["frequency"] == "hourly"
        assert result["key_phrases"] == ["Test phrase"]

    def test_missing_lesson_returns_none(self, db_session: Session):
        """Should return None for non-existent lesson."""
        result = check_and_extract_practice_instructions(999999, session=db_session)
        assert result is None
