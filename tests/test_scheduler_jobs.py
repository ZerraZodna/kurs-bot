from datetime import datetime, timedelta, timezone

from src.scheduler import jobs


class _FakeSchedule:
    def __init__(self, schedule_id, schedule_type, cron_expression=None, next_send_time=None):
        self.schedule_id = schedule_id
        self.schedule_type = schedule_type
        self.cron_expression = cron_expression
        self.next_send_time = next_send_time


def test_init_sync_and_remove_job():
    # init scheduler
    sched = jobs.init_scheduler()
    assert sched is not None

    # create a one-time schedule
    run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    s1 = _FakeSchedule(9999, "one_time_reminder", next_send_time=run_at)
    jobs.sync_job_for_schedule(s1)
    job = sched.get_job(f"schedule_{s1.schedule_id}")
    assert job is not None

    # remove job
    jobs.remove_job_for_schedule(s1.schedule_id)
    assert sched.get_job(f"schedule_{s1.schedule_id}") is None

    # cron schedule
    s2 = _FakeSchedule(10000, "daily", cron_expression="0 0 * * *")
    jobs.sync_job_for_schedule(s2)
    job2 = sched.get_job(f"schedule_{s2.schedule_id}")
    assert job2 is not None

    # cleanup
    jobs.remove_job_for_schedule(s2.schedule_id)
    jobs.shutdown_scheduler()
