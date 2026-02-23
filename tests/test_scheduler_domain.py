from src.scheduler import jobs
from src.scheduler.domain import (
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_ONE_TIME_REMINDER,
    is_daily_schedule_type,
    is_daily_schedule_family,
    is_one_time_schedule_type,
    job_id_for_schedule,
)


def test_schedule_type_predicates_characterization():
    assert is_daily_schedule_type(SCHEDULE_TYPE_DAILY) is True
    assert is_daily_schedule_type("daily_custom") is False
    assert is_daily_schedule_type(None) is False

    assert is_daily_schedule_family(SCHEDULE_TYPE_DAILY) is True
    assert is_daily_schedule_family("daily_custom") is True
    assert is_daily_schedule_family("weekly") is False
    assert is_daily_schedule_family(None) is False

    assert is_one_time_schedule_type(SCHEDULE_TYPE_ONE_TIME_REMINDER) is True
    assert is_one_time_schedule_type("one_time_custom") is True
    assert is_one_time_schedule_type("daily") is False
    assert is_one_time_schedule_type(None) is False


def test_job_id_helper_matches_jobs_module():
    assert job_id_for_schedule(42) == "schedule_42"
    assert jobs.job_id_for_schedule(42) == "schedule_42"
