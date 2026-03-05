"""Unit tests for onboarding timezone handling.

These tests verify that:
1. Schedule is created at correct UTC time for user's timezone (07:30 local → correct UTC)
2. Schedule display shows local time (UTC → local conversion)
3. Timezone is correctly passed through the onboarding chain
4. Norwegian users get Europe/Oslo timezone by default
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.onboarding import schedule_setup
from src.onboarding.flow import OnboardingFlow
from src.models.database import User, Schedule
from src.scheduler.domain import SCHEDULE_TYPE_DAILY

from tests.fixtures.users import create_test_user


class TestOnboardingTimezoneHandling:
    """Tests for onboarding timezone handling."""

    def test_create_auto_schedule_uses_user_timezone_from_db(self, db_session):
        """Given: A user with Europe/Oslo timezone set in DB
        When: create_auto_schedule is called
        Then: Schedule should be created at 06:30 UTC (07:30 Oslo time)
              AND user should see 07:30 when querying schedule (not 06:30)."""
        # Given: User with Europe/Oslo timezone
        user_id = create_test_user(db_session, "test_tz_oslo", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        db_session.commit()

        # When: Create auto schedule
        result = schedule_setup.create_auto_schedule(db_session, user_id)

        # Then: Schedule should be created
        assert result is True, "Schedule should be created successfully"

        # Verify schedule exists and has correct time
        schedule = db_session.query(Schedule).filter_by(user_id=user_id).first()
        assert schedule is not None, "Schedule should exist"
        assert schedule.schedule_type == SCHEDULE_TYPE_DAILY
        assert schedule.is_active is True

        # The schedule should be at 06:30 UTC (which is 07:30 in Europe/Oslo during winter)
        # Note: During summer (CEST), 07:30 CEST = 05:30 UTC
        # We'll check that it's either 05:30 or 06:30 UTC depending on DST
        assert schedule.next_send_time is not None
        utc_hour = schedule.next_send_time.hour
        utc_minute = schedule.next_send_time.minute
        
        # Should be either 05:30 (CEST/summer) or 06:30 (CET/winter)
        assert utc_minute == 30, f"Minutes should be 30, got {utc_minute}"
        assert utc_hour in (5, 6), f"Hour should be 5 or 6 (CEST/CET), got {utc_hour}"

        # CRITICAL: Verify user sees 07:30 (local time), not 06:30 (UTC)
        from src.scheduler.schedule_query_handler import build_schedule_status_response
        response = build_schedule_status_response([schedule], "Europe/Oslo")
        
        print(f"\nSchedule query response for Oslo user:\n{response}\n")
        
        # User should see 07:30, not 06:30 or 05:30
        assert "07:30" in response, f"User should see 07:30 local time. Got: {response}"
        assert "06:30" not in response, f"User should NOT see 06:30 UTC. Got: {response}"
        assert "05:30" not in response, f"User should NOT see 05:30 UTC. Got: {response}"


    def test_create_auto_schedule_infers_from_norwegian_language(self, db_session):
        """Given: A Norwegian user with no timezone but Norwegian language
        When: create_auto_schedule is called
        Then: Should use Europe/Oslo timezone."""
        # Given: Norwegian user with no timezone
        user_id = create_test_user(db_session, "test_tz_no_lang", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        user.language = "no"
        db_session.commit()

        # When: Create auto schedule
        result = schedule_setup.create_auto_schedule(db_session, user_id)

        # Then: Schedule should use Oslo time
        assert result is True

        schedule = db_session.query(Schedule).filter_by(user_id=user_id).first()
        assert schedule is not None
        
        # Should be 05:30 or 06:30 UTC (07:30 Oslo time)
        utc_hour = schedule.next_send_time.hour
        assert utc_hour in (5, 6), f"Expected Oslo time conversion, got UTC hour {utc_hour}"

    @pytest.mark.asyncio
    async def test_onboarding_completion_creates_schedule_with_correct_timezone(self, db_session):
        """Given: A user completing onboarding with Europe/Oslo timezone
        When: Onboarding completes and get_onboarding_complete_message is called
        Then: Schedule should be created with correct timezone conversion."""
        # Given: User with timezone set
        user_id = create_test_user(db_session, "test_onboarding_tz", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        user.language = "no"
        db_session.commit()

        # Set up onboarding memories
        mm = MemoryManager(db_session)
        mm.store_memory(user_id, "first_name", "Test", category="profile")
        mm.store_memory(user_id, "data_consent", "granted", category="profile")
        mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals")
        mm.store_memory(user_id, "current_lesson", "1", category="progress")

        # When: Complete onboarding
        svc = OnboardingService(db_session)
        message = svc.get_onboarding_complete_message(user_id)

        # Then: Schedule should exist with correct timezone
        schedule = db_session.query(Schedule).filter_by(user_id=user_id).first()
        assert schedule is not None, "Schedule should be created after onboarding"

        # Verify the time is in UTC but represents 07:30 Oslo time
        utc_hour = schedule.next_send_time.hour
        utc_minute = schedule.next_send_time.minute
        assert utc_minute == 30
        assert utc_hour in (5, 6), f"Expected 07:30 Oslo time (05:30 or 06:30 UTC), got {utc_hour}:30 UTC"

        # Verify message mentions 07:30 (local time)
        assert "07:30" in message or "7:30" in message, "Message should mention 07:30 local time"

    def test_schedule_not_created_if_already_exists(self, db_session):
        """Given: A user who already has an active schedule
        When: create_auto_schedule is called
        Then: Should not create duplicate schedule."""
        # Given: User with existing schedule
        user_id = create_test_user(db_session, "test_existing_sched", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        db_session.commit()

        # Create first schedule
        schedule_setup.create_auto_schedule(db_session, user_id)
        
        # Count schedules
        count_before = db_session.query(Schedule).filter_by(user_id=user_id).count()
        assert count_before == 1

        # When: Try to create again
        result = schedule_setup.create_auto_schedule(db_session, user_id)

        # Then: Should not create duplicate
        assert result is False, "Should return False when schedule already exists"
        count_after = db_session.query(Schedule).filter_by(user_id=user_id).count()
        assert count_after == 1, "Should not create duplicate schedule"

    def test_timezone_persists_through_session_refresh(self, db_session):
        """Given: Timezone is set and session is refreshed
        When: create_auto_schedule queries the user
        Then: Should see the updated timezone."""
        # Given: User with timezone
        user_id = create_test_user(db_session, "test_tz_refresh", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        db_session.commit()
        
        # Expire and refresh to simulate new session
        db_session.expire(user)
        
        # When: Query user again
        user_refreshed = db_session.query(User).filter_by(user_id=user_id).first()
        
        # Then: Timezone should still be set
        assert user_refreshed.timezone == "Europe/Oslo"


class TestEnsureUserTimezoneBug:
    """Tests for the ensure_user_timezone bug where language overrides DB timezone."""

    def test_ensure_user_timezone_uses_db_not_language(self, db_session):
        """Given: User has Europe/Oslo timezone in DB but English language
        When: get_user_timezone_from_db is called
        Then: Should return Europe/Oslo from DB, not UTC from language inference."""
        from src.core.timezone import get_user_timezone_from_db
        
        # Given: User with Oslo timezone in DB but English language
        user_id = create_test_user(db_session, "test_tz_db_not_lang", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        user.language = "en"  # English language
        db_session.commit()

        # When: Call get_user_timezone_from_db
        result_tz = get_user_timezone_from_db(db_session, user_id, default="UTC")

        # Then: Should return Europe/Oslo from DB, not UTC
        assert result_tz == "Europe/Oslo", \
            f"Expected Europe/Oslo from DB, got {result_tz}. Bug: language overrides DB timezone!"

    def test_ensure_user_timezone_with_norwegian_user_english_language(self, db_session):
        """Given: Norwegian user with Oslo timezone but English UI language
        When: Querying schedule (which calls get_user_timezone_from_db)
        Then: Should display 07:30 (Oslo time), not 07:30 UTC."""
        from src.core.timezone import get_user_timezone_from_db
        from src.scheduler.schedule_query_handler import build_schedule_status_response
        
        # Given: Norwegian user with Oslo timezone but English language
        user_id = create_test_user(db_session, "test_no_user_en_lang", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        user.language = "en"  # User prefers English UI
        db_session.commit()

        # Create schedule at 07:30 Oslo time
        from src.scheduler.time_utils import compute_next_send_and_cron
        next_send_utc, cron = compute_next_send_and_cron("07:30", "Europe/Oslo")
        
        from src.scheduler.domain import SCHEDULE_TYPE_DAILY
        from src.scheduler import manager as schedule_manager
        schedule = schedule_manager.create_schedule(
            user_id=user_id,
            lesson_id=1,
            schedule_type=SCHEDULE_TYPE_DAILY,
            cron_expression=cron,
            next_send_time=next_send_utc,
            session=db_session,
        )

        # When: Get timezone (simulating "List reminders" flow)
        tz_name = get_user_timezone_from_db(db_session, user_id, default="UTC")
        
        # Then: Should use Oslo timezone, not UTC
        assert tz_name == "Europe/Oslo", f"Bug: Got {tz_name} instead of Europe/Oslo"

        # And: Schedule display should show 07:30, not 06:30 or 05:30
        response = build_schedule_status_response([schedule], tz_name)
        print(f"\nSchedule response for Norwegian user with English language:\n{response}\n")
        
        assert "07:30" in response, f"User should see 07:30 Oslo time. Got: {response}"
        assert "06:30" not in response, f"User should NOT see 06:30 UTC. Got: {response}"


class TestTimezoneConversionEdgeCases:
    """Edge case tests for timezone handling."""

    def test_pacific_timezone_conversion(self, db_session):
        """Given: A user in Pacific timezone
        When: create_auto_schedule is called
        Then: Schedule should be at correct UTC time."""
        # Given: User in Pacific timezone
        user_id = create_test_user(db_session, "test_tz_pacific", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "America/Los_Angeles"
        db_session.commit()

        # When: Create schedule
        result = schedule_setup.create_auto_schedule(db_session, user_id)

        # Then: Schedule should exist
        assert result is True
        schedule = db_session.query(Schedule).filter_by(user_id=user_id).first()
        assert schedule is not None
        
        # 07:30 Pacific = 15:30 UTC (or 14:30 during DST)
        utc_hour = schedule.next_send_time.hour
        assert utc_hour in (14, 15), f"Expected Pacific time conversion, got UTC hour {utc_hour}"

    def test_eastern_timezone_conversion(self, db_session):
        """Given: A user in Eastern timezone
        When: create_auto_schedule is called
        Then: Schedule should be at correct UTC time."""
        # Given: User in Eastern timezone
        user_id = create_test_user(db_session, "test_tz_eastern", "Test")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "America/New_York"
        db_session.commit()

        # When: Create schedule
        result = schedule_setup.create_auto_schedule(db_session, user_id)

        # Then: Schedule should exist
        assert result is True
        schedule = db_session.query(Schedule).filter_by(user_id=user_id).first()
        assert schedule is not None
        
        # 07:30 Eastern = 12:30 UTC (or 11:30 during DST)
        utc_hour = schedule.next_send_time.hour
        assert utc_hour in (11, 12), f"Expected Eastern time conversion, got UTC hour {utc_hour}"
