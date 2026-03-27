#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure repo root is on path for src imports
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.core.timezone import get_user_timezone_from_db
from src.models.database import Memory, Schedule, SessionLocal, User, init_db
from src.scheduler import api as scheduler_api
from src.scheduler import jobs as schedule_jobs
from src.scheduler import manager as schedule_manager
from src.scheduler.time_utils import compute_next_send_and_cron


def dump_user_state(db, user_id):
    print("\\n=== Inspecting user " + str(user_id) + " state ===")
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("User not found")
        return
    print(
        "User:",
        {
            "user_id": user.user_id,
            "external_id": user.external_id,
            "timezone": user.timezone,
            "first_name": user.first_name,
            "lesson": getattr(user, "lesson", None),
        },
    )

    print("\\nSchedules:")
    schedules = db.query(Schedule).filter_by(user_id=user_id).all()
    for s in schedules:
        status = "✅ ACTIVE" if s.is_active else "⏸️ INACTIVE"
        next_str = s.next_send_time.isoformat() if s.next_send_time else "None"
        lesson_title = s.lesson.title if s.lesson else "None"
        print(
            "  "
            + status
            + " ["
            + s.schedule_type
            + "] id="
            + str(s.schedule_id)
            + ", cron="
            + repr(s.cron_expression)
            + ", next="
            + next_str
            + ", lesson="
            + repr(lesson_title)
        )

    print("\\nSchedule memories:")
    relevant_keys = ["schedule_message", "preferred_daily_time", "schedule_request_pending"]
    sm = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.key.in_(relevant_keys))
        .order_by(Memory.created_at.desc())
        .limit(10)
        .all()
    )
    for m in sm:
        print("  [" + m.category + "] " + m.key + ": " + str(m.value)[:100] + "...")
    print("")


def direct_create_hourly(db, user_id):
    tz_name = get_user_timezone_from_db(db, user_id)
    print("Direct creating hourly cron schedule for " + tz_name + " tz...")

    time_str = "09:00"
    next_send, _ = compute_next_send_and_cron(time_str, tz_name)
    hourly_cron = "0 */1 9-17 * * *"

    schedule = schedule_manager.create_schedule(
        user_id=user_id,
        lesson_id=None,
        schedule_type="hourly_lessons",
        cron_expression=hourly_cron,
        next_send_time=next_send,
        session=db,
    )
    schedule_jobs.sync_job_for_schedule(schedule)
    print(
        "✓ Created hourly schedule id="
        + str(schedule.schedule_id)
        + ", cron="
        + repr(hourly_cron)
        + ", next="
        + schedule.next_send_time.isoformat()
    )
    print("APScheduler job synced - will fire every hour 9-17 local time sending lesson extract!")
    return schedule


def run_hourly_setup(user_id):
    db = SessionLocal()
    try:
        print("Initializing DB...")
        init_db()

        dump_user_state(db, user_id)

        count = scheduler_api.deactivate_user_schedules(user_id, session=db)
        print("Cleared " + str(count) + " prior schedules.")

        print("\\nSkipping LLM (stream issue) -> direct hourly schedule")
        schedule = direct_create_hourly(db, user_id)

        print("\\n🏁 Final state:")
        dump_user_state(db, user_id)
        print("\\n🚀 Task complete! Hourly lesson extracts (Lesson 1 extracts) scheduled 9am-5pm Oslo time.")
        print("Cron: " + repr("0 */1 9-17 * * *"))
        print("\\nLive test (simulate=True first):")
        print(
            'python -c "from src.scheduler.api import execute_scheduled_task; print(execute_scheduled_task('
            + str(schedule.schedule_id)
            + ', simulate=True))"'
        )
        print("\\nReal send:")
        print(
            'python -c "from src.scheduler.api import execute_scheduled_task; execute_scheduled_task('
            + str(schedule.schedule_id)
            + ')"'
        )

    finally:
        db.close()


if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_hourly_setup(user_id)
